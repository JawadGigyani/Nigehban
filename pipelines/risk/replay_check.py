"""Replay the demo days with archived forecasts and write reports/replay_check.md.

    python -m pipelines.risk.replay_check
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from backend.app.config import get_settings
from backend.app.risk.service import RiskService, describe_driver
from pipelines.hydromet.qa import _md

NOTES = """

## Reading these results

- **Levels used here were tuned on the 2024-2025 forecasts, which include these days**, so these
  replays are flattering. The fair test is the cross-season backtest in reports/backtest.md
  (each season's levels tuned on the other season).
- **Buner day (15 Aug 2025):** most flooded tehsils were at high 1-3 days ahead. The forecasts
  showed heavy rain across Swat, Buner and Mansehra.
- **Swat day (27 Jun 2025):** missed (moderate at best, 2 days ahead in Babuzai). Every forecast
  had only 10-14 mm for these tehsils, against about 57 mm that fell. The GloFAS river flag did not
  fire either: GloFAS showed an ordinary flow at Mingora that day.
- Probabilities look small because floods are rare (about 0.2% of tehsil-days); "high" means
  roughly 3-5 times the usual chance. The board and alerts show levels, not raw probabilities.
"""

CASES = [
    ("Buner cloudburst", dt.date(2025, 8, 15), ["buner__", "swat__", "shangla__", "bajaur__", "mansehra__"]),
    ("Swat River flood", dt.date(2025, 6, 27), ["swat__"]),
]


def main() -> int:
    data = get_settings().data_dir
    service = RiskService.from_data_dir(data)
    events = pd.read_parquet(data / "events" / "flood_events.parquet")
    events = events[events["is_positive"]]
    sections = []
    for title, day, prefixes in CASES:
        flooded = set(events[(events["date"] == day) & events["tehsil_id"].notna()]["tehsil_id"])
        rows = []
        for lead in (1, 2, 3):
            issue = day - dt.timedelta(days=lead)
            for f in service.forecast(issue, replay=True):
                if f.valid_date != day or not f.tehsil_id.startswith(tuple(prefixes)):
                    continue
                rows.append({"issued": str(issue), "lead (days)": lead, "tehsil": f.tehsil_id,
                             "PDMA flood that day": "yes" if f.tehsil_id in flooded else "",
                             "level": f.level.value, "probability": f.probability,
                             "top reasons": "; ".join(describe_driver(d) for d in f.drivers[:3])})
        table = pd.DataFrame(rows).sort_values(["lead (days)", "probability"], ascending=[True, False])
        caught = table[(table["PDMA flood that day"] == "yes") & table["level"].isin(["high", "very_high"])]
        sections.append(f"## {title}, {day}\n\nTehsils with a PDMA flood report that day: "
                        f"{', '.join(sorted(flooded)) or 'none at tehsil level'}.\n"
                        f"Flooded tehsils at high or above: {sorted(set(caught['tehsil'] + ' (lead ' + caught['lead (days)'].astype(str) + ')'))}\n\n"
                        + _md(table))
    text = (f"# M5 replay check\n\nGenerated {dt.date.today()} by `python -m pipelines.risk.replay_check`. "
            "Forecasts as they were issued 1–3 days before each demo day (Open-Meteo archived runs, "
            "ECMWF + GFS + ICON averaged), scored by the shipped model with the forecast-tuned levels.\n\n"
            + "\n\n".join(sections) + NOTES)
    Path("reports/replay_check.md").write_text(text, encoding="utf-8")
    print(text[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
