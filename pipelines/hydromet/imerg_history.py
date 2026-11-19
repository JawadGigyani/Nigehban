"""IMERG daily rain per tehsil for Jun–Sep 2019–2025 (Final run) and a comparison with ERA5.

    python -m pipelines.hydromet.imerg_history            # fetch (cached, resumable) + table + report
    python -m pipelines.hydromet.imerg_history --check    # one day only, to test access

Writes data/features/imerg_daily.parquet and reports/imerg_vs_era5.md: does satellite rain
line up with PDMA flood days better than ERA5?
"""

from __future__ import annotations

import argparse
import datetime as dt
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.config import get_settings
from backend.app.hydromet.imerg import ImergClient, ImergError, tehsil_values, tehsil_weights

YEARS = range(2019, 2026)


def days() -> list[dt.date]:
    out = []
    for year in YEARS:
        d = dt.date(year, 6, 1)
        while d <= dt.date(year, 9, 30):
            out.append(d)
            d += dt.timedelta(days=1)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    data = settings.data_dir
    client = ImergClient.from_settings(settings)
    weights = tehsil_weights(data / "reference" / "tehsils.geojson")
    if args.check:
        grid = client.day(dt.date(2025, 8, 15), "final")
        vals = tehsil_values(grid, weights)
        print({k: v for k, v in vals.items() if k.startswith("buner")})
        return 0

    rows, todo = [], days()
    for n, day in enumerate(todo, start=1):
        for attempt in range(3):
            try:
                grid = client.day(day, "final")
                break
            except ImergError as exc:
                if "refused" in str(exc):
                    raise
                time.sleep(5 * (attempt + 1))
        else:
            continue
        if grid is None:
            continue
        for tehsil_id, (mean, cell_max) in tehsil_values(grid, weights).items():
            rows.append({"tehsil_id": tehsil_id, "date": day, "imerg_precip": mean, "imerg_cell_max": cell_max})
        if n % 50 == 0:
            print(f"{n}/{len(todo)} days", flush=True)
    table = pd.DataFrame(rows)
    table.to_parquet(data / "features" / "imerg_daily.parquet", index=False)
    write_report(table, data)
    print(f"{len(table)} tehsil-days -> data/features/imerg_daily.parquet")
    return 0


def write_report(imerg: pd.DataFrame, data: Path) -> None:
    from sklearn.metrics import average_precision_score, roc_auc_score

    from pipelines.hydromet.qa import _md
    from pipelines.risk.train import build_dataset

    frame, _ = build_dataset(data)
    frame = frame.merge(imerg, on=["tehsil_id", "date"], how="inner")
    m = frame["train"]
    y = frame.loc[m, "y"].to_numpy()
    rows = []
    for col, label in [("precip_sum", "ERA5 tehsil mean"), ("precip_cell_max", "ERA5 wettest cell"),
                       ("imerg_precip", "IMERG tehsil mean"), ("imerg_cell_max", "IMERG wettest cell")]:
        x = frame.loc[m, col].fillna(0).to_numpy()
        rows.append({"rain source": label, "ROC-AUC": roc_auc_score(y, x), "PR-AUC": average_precision_score(y, x),
                     "mean on flood days (mm)": float(x[y == 1].mean()), "mean other days (mm)": float(x[y == 0].mean())})
    corr = frame[["precip_sum", "imerg_precip"]].corr().iloc[0, 1]
    buner = imerg[(imerg["date"] == dt.date(2025, 8, 15)) & imerg["tehsil_id"].str.startswith("buner")]
    text = f"""# IMERG vs ERA5 on PDMA flood days

Generated {dt.date.today()} by `python -m pipelines.hydromet.imerg_history`. IMERG Final (daily, 0.1°),
Jun–Sep 2019–2025, {len(imerg):,} tehsil-days. Each rain value alone, as a flood-day signal
(tehsil-level PDMA events, same rows as the M5 training table).

{_md(pd.DataFrame(rows))}

Daily correlation between ERA5 and IMERG tehsil means: {corr:.2f}.

Buner, 15 Aug 2025 (IMERG):

{_md(buner)}
"""
    Path("reports/imerg_vs_era5.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
