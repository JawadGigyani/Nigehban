"""Write `reports/m2_hydromet_qa.md`: coverage, planning checks, forecast vs ERA5, live timing.

    python -m pipelines.hydromet.qa
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.config import get_settings
from backend.app.config.region import CANDIDATE_DISTRICTS
from backend.app.hydromet import HydrometService

D = dt.date


def _num(v: float) -> str:
    """Keep small numbers readable: 1234 -> 1234, 12.34 -> 12.3, 0.0123 -> 0.0123."""

    a = abs(v)
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        return f"{v:.1f}"
    if a >= 0.1 or a == 0:
        return f"{v:.2f}"
    return f"{v:.3g}"


def _md(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in frame.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else (_num(v) if isinstance(v, float) else str(v))
                                       for v in row) + " |")
    return "\n".join(lines)


def planning_checks(table: pd.DataFrame) -> pd.DataFrame:
    cases = [("buner__daggar", D(2025, 8, 15), "Buner cloudburst (Pir Baba / Daggar)"),
             ("swat__babuzai", D(2025, 6, 27), "Swat River flood, Babuzai"),
             ("swat__babuzai", D(2025, 6, 26), "day before, Babuzai")]
    rows = []
    for tehsil_id, day, label in cases:
        part = table[(table["tehsil_id"] == tehsil_id) & (table["date"] == day)]
        for r in part.sort_values(["model", "lead_days"]).itertuples(index=False):
            rows.append({"case": label, "date": str(day), "source": r.model, "lead (days)": r.lead_days,
                         "tehsil mean (mm)": r.precip_sum, "wettest cell (mm)": r.precip_cell_max,
                         "3-day (mm)": r.precip_3d, "7 days before (mm)": r.precip_7d_antecedent})
    return pd.DataFrame(rows)


def forecast_gap(table: pd.DataFrame) -> pd.DataFrame:
    era5 = table[table["model"] == "era5"][["tehsil_id", "date", "precip_sum"]].rename(columns={"precip_sum": "obs"})
    fc = table[table["model"] != "era5"].merge(era5, on=["tehsil_id", "date"])
    fc = fc[pd.to_datetime(fc["date"]).dt.month.between(6, 9)]
    rows = []
    for (model, lead), g in fc.groupby(["model", "lead_days"]):
        g = g.dropna(subset=["precip_sum", "obs"])
        wet = g[g["obs"] >= 20]
        rows.append({"model": model, "lead": lead, "days x tehsils": len(g),
                     "bias (mm)": (g["precip_sum"] - g["obs"]).mean(),
                     "MAE (mm)": (g["precip_sum"] - g["obs"]).abs().mean(),
                     "correlation": np.corrcoef(g["precip_sum"], g["obs"])[0, 1] if len(g) > 2 else np.nan,
                     "ERA5 >= 20 mm days": len(wet),
                     "caught (fc >= 10 mm)": f"{(wet['precip_sum'] >= 10).mean():.0%}" if len(wet) else ""})
    return pd.DataFrame(rows)


def event_signal(table: pd.DataFrame, events_path: Path) -> pd.DataFrame | None:
    if not events_path.is_file():
        return None
    events = pd.read_parquet(events_path)
    events = events[events["is_positive"] & events["tehsil_id"].notna()]
    era5 = table[table["model"] == "era5"]
    hits = era5.merge(events[["tehsil_id", "date"]].drop_duplicates(), on=["tehsil_id", "date"])
    jjas = era5[pd.to_datetime(era5["date"]).dt.month.between(6, 9)]
    rows = []
    for label, part in (("event days (tehsil-level positives)", hits), ("all Jun–Sep tehsil-days", jjas)):
        rows.append({"rows": label, "n": len(part), "mean rain (mm)": part["precip_sum"].mean(),
                     "median 3-day (mm)": part["precip_3d"].median(),
                     "share with 3-day >= 20 mm": f"{(part['precip_3d'] >= 20).mean():.0%}",
                     "mean soil moisture 0–7 cm": part["soil_moisture_0_7"].mean()})
    return pd.DataFrame(rows)


def main() -> int:
    settings = get_settings()
    data = settings.data_dir
    table = pd.read_parquet(data / "features" / "hydromet_daily.parquet")
    candidates = {d.slug for d in CANDIDATE_DISTRICTS}
    era5 = table[table["model"] == "era5"]
    jjas = era5[pd.to_datetime(era5["date"]).dt.month.between(6, 9)]
    years = sorted(pd.to_datetime(jjas["date"]).dt.year.unique())
    cand = jjas[jjas["tehsil_id"].str.split("__").str[0].isin(candidates)]
    per_tehsil_year = cand.groupby(["tehsil_id", pd.to_datetime(cand["date"]).dt.year]).size()
    coverage = pd.DataFrame(table.groupby(["model", "lead_days"]).agg(
        rows=("date", "size"), first=("date", "min"), last=("date", "max"),
        missing_rain=("precip_sum", lambda s: f"{s.isna().mean():.1%}"),
        missing_soil=("soil_moisture_0_7", lambda s: f"{s.isna().mean():.1%}"))).reset_index()

    service = HydrometService.from_data_dir(data)
    started = time.time()
    live = service.live_features()
    live_s = time.time() - started

    gate = (len(years) >= 7 and per_tehsil_year.min() >= 122
            and cand["tehsil_id"].nunique() == len({t for t in table["tehsil_id"]
                                                  if t.split("__")[0] in candidates})
            and live_s < 30)
    signal = event_signal(table, data / "events" / "flood_events.parquet")
    text = f"""# M2 hydromet QA

Generated {dt.date.today()} by `python -m pipelines.hydromet.qa`.

## Done-when check

| Check | Result |
|---|---|
| ERA5 history Jun–Sep, years | {years[0]}–{years[-1]} ({len(years)} seasons) |
| Candidate tehsils covered | {cand['tehsil_id'].nunique()} (every season complete: {per_tehsil_year.min() >= 122}) |
| All tehsils in the table | {table['tehsil_id'].nunique()} |
| Live call, all tehsils x 3 models x lead 0–3 | {live_s:.1f} s, {len(live)} rows (target < 30 s) |
| Buner 15 Aug 2025, ERA5 (planning check about 44 mm) | see below |
| Buner 15 Aug 2025, ECMWF 1 day ahead (planning check about 34 mm) | see below |
| **M2 gate** | **{'passed' if gate else 'NOT passed'}** |

## How features are made

- Grid: the 0.25° cells overlapping each tehsil, weighted by area share
  (`data/reference/tehsil_grid.csv`, 80 cells for 53 tehsils).
- Daily = local day (Asia/Karachi). `precip_sum` is the tehsil mean,
  `precip_cell_max` the wettest cell, `precip_max_1h` the wettest hour in any cell.
- `precip_3d` = the day and the 2 days before; `precip_7d_antecedent` = the 7 days before.
- Forecast rows use only what was known at issue time: days before the issue
  date come from ERA5, later days from the same forecast.
- Soil moisture (0–7 and 7–28 cm) is ERA5. For archived forecasts it is ERA5 on
  the day before the issue date. Live: ECMWF's own value (GFS and ICON do not
  provide these layers, so they use ECMWF's).
- `t2m_anomaly` = daily max temperature minus the 2019–2025 ERA5 mean for that
  tehsil and time of year (±15 days). Months outside the history have no anomaly.

## Coverage

{_md(coverage)}

## Planning checks (tehsil values)

{_md(planning_checks(table))}

## Forecast vs ERA5, Jun–Sep (archived forecasts, 2024 onward)

{_md(forecast_gap(table))}

Forecasts are compared with ERA5, which is itself smooth over a 0.25° cell, so
both understate rain in the wettest valleys. "Caught" = forecast of at least
10 mm on days when ERA5 had at least 20 mm in the tehsil.

## Does rain line up with events?

{_md(signal) if signal is not None else 'No event table found.'}

## Limits and open items

- **IMERG (satellite rain):** not tested yet. It needs a Google Earth Engine
  project tied to a Google account. `pipelines/hydromet/imerg_colab_test.py`
  runs the access test in Colab. Per the plan, ERA5 plus forecasts are enough
  for the MVP if it fails.
- **GloFAS (river discharge):** the client works (`OpenMeteoClient.flood`). It
  snaps to the nearest 0.05° cell, which is often beside the main channel (a
  test near Mingora returned about 200 m³/s during the Aug 2022 flood). Picking
  the right cell per river is M6, so `glofas_discharge` is empty for now.
- ERA5 is 0.25° (about 25 km): small tehsils get one cell, and short
  convective bursts are smoothed. The wettest-cell column helps a little.
- Archived forecasts start in March 2024, so the forecast-vs-ERA5 gap rests on
  two or three seasons.
"""
    out = Path("reports") / "m2_hydromet_qa.md"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}; gate {'passed' if gate else 'NOT passed'}; live {live_s:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
