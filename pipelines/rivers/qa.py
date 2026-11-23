"""Write reports/rivers_glofas.md: river points, chosen cells, return levels, and how GloFAS saw known floods.

    python -m pipelines.rivers.qa
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from backend.app.config import get_settings
from backend.app.hydromet.client import OpenMeteoClient, RatePacer
from pipelines.hydromet.qa import _md

CHECK_DAYS = [dt.date(2022, 8, 26), dt.date(2022, 8, 27), dt.date(2025, 6, 27), dt.date(2025, 8, 15)]


def main() -> int:
    data = get_settings().data_dir
    ref = data / "reference"
    thresholds = json.loads((ref / "river_points_thresholds.json").read_text(encoding="utf-8"))
    cells = json.loads((ref / "river_points_cells.json").read_text(encoding="utf-8"))
    peaks = pd.read_csv(ref / "river_yearly_peaks.csv", index_col="year")
    points = pd.read_csv(ref / "river_points.csv").set_index("point_id")
    # Cache only: these requests were made by build_thresholds.
    client = OpenMeteoClient(data / "cache" / "openmeteo", pacer=RatePacer(per_minute=1e9, per_hour=1e9, per_day=1e9))

    rows, days = [], []
    for p in thresholds["points"]:
        pid = p["point_id"]
        rank_2022 = int(peaks[pid].rank(ascending=False)[2022]) if 2022 in peaks.index else None
        rows.append({"point": p["name"], "tehsils": points.loc[pid, "tehsils"].replace(";", ", "),
                     "cell moved (km)": cells[pid]["offset_km"], "q2": p["q2"], "q5": p["q5"], "q20": p["q20"],
                     "2022 peak": float(peaks.loc[2022, pid]), "2022 rank of 29": rank_2022})
        for d in CHECK_DAYS:
            item = client.flood([p["lat"]], [p["lon"]], dt.date(d.year, 4, 1), dt.date(d.year, 10, 31))[0]
            series = dict(zip(item["daily"]["time"], item["daily"]["river_discharge"], strict=True))
            value = series.get(d.isoformat())
            days.append({"point": pid, "date": str(d), "discharge": value,
                         "vs 2-year flow": f"{value / p['q2']:.0%}" if value else ""})
    assert client.calls == 0, "qa must only read the cache"
    text = f"""# M6 GloFAS river levels

Generated {dt.date.today()} by `python -m pipelines.rivers.qa`. Source: Copernicus GloFAS via the
Open-Meteo Flood API (CC BY 4.0). Method: {thresholds['method']}.

## River points

{_md(pd.DataFrame(rows))}

"Cell moved" is the distance from the named place to the chosen GloFAS cell: the cell with the most
water within 0.1° (about 11 km), which tends to sit a little downstream.

## How GloFAS saw known floods

{_md(pd.DataFrame(days).pivot(index="point", columns="date", values="vs 2-year flow").reset_index())}

Values are the day's GloFAS flow as a share of the 2-year flow.

## Finding

GloFAS does not see the floods that matter here. The Aug 2022 Swat flood, which destroyed parts of
Kalam, Bahrain and Mingora, ranks low among GloFAS's 29 yearly peaks at every Swat point, and on the
two 2025 demo days the river flows are ordinary. In the M7 backtest the river flag added no caught
events in any season. It stays in the system as a secondary signal (it almost never fires), and the
alert rule remains "model high or above, or river flag".

Better river input for later: the observed gauge flows in the Flood Forecasting Division's daily
bulletins (for example Swat at Chakdara and Munda) during the monsoon.
"""
    Path("reports/rivers_glofas.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
