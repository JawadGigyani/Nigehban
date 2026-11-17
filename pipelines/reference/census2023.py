"""Parse PBS Census 2023 Table 1 (Khyber Pakhtunkhwa, tehsil sheet).

Source: https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_kp_districts.xlsx
Writes `data/reference/census2023_kp_tehsils.csv` with one row per tehsil:
district, tehsil, unit_type, area_km2, pop_2023, pop_2017, urban_share.

The sheet lists each unit as "<NAME> DISTRICT" or "<NAME> TEHSIL" followed by
RURAL and URBAN rows. Some districts list "<NAME> SUB-DIVISION" units instead
of (or beside) tehsils; those are kept with unit_type "sub_division". Only the
unit rows (all-area totals) are kept. Census units do not always match the
COD-AB tehsil polygons (some are split, some merged), so this file is used for
name aliases and population checks, not as the risk unit.

Usage: python -m pipelines.reference.census2023
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from backend.app.config import get_settings

SOURCE_URL = "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_kp_districts.xlsx"
SHEET = "KP Teh"
UNIT_SUFFIXES = (" DISTRICT", " TEHSIL", " SUB-DIVISION", " SUBDIVISION")

# Column positions in Table 1 (0-based), checked against the sheet header.
COL_NAME, COL_AREA, COL_POP, COL_URBAN, COL_POP2017 = 0, 1, 2, 8, 10


def _title(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split())


def _num(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(number) else number


def parse_rows(rows: list[list]) -> list[dict]:
    out: list[dict] = []
    district: str | None = None
    for row in rows:
        cell = row[COL_NAME]
        raw = " ".join(str(cell).split()) if isinstance(cell, str) else ""
        upper = raw.upper()
        suffix = next((s for s in UNIT_SUFFIXES if upper.endswith(s)), None)
        if suffix is None:
            continue
        name = _title(raw[: -len(suffix)].strip())
        if suffix == " DISTRICT":
            district = name
            continue
        if district is None:
            continue
        urban = _num(row[COL_URBAN])
        pop = _num(row[COL_POP])
        pop2017 = _num(row[COL_POP2017])
        out.append({
            "district": district,
            "tehsil": name,
            "unit_type": "tehsil" if suffix == " TEHSIL" else "sub_division",
            "area_km2": _num(row[COL_AREA]),
            "pop_2023": int(pop) if pop is not None else None,
            "pop_2017": int(pop2017) if pop2017 is not None else None,
            "urban_share": round(urban / 100.0, 4) if urban is not None else None,
        })
    return out


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path,
                        default=settings.data_dir / "raw" / "census2023" / "table_1_kp_districts.xlsx")
    parser.add_argument("--out", type=Path,
                        default=settings.data_dir / "reference" / "census2023_kp_tehsils.csv")
    args = parser.parse_args(argv)

    frame = pd.read_excel(args.xlsx, sheet_name=SHEET, header=None)
    rows = parse_rows(frame.values.tolist())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    districts = {r["district"] for r in rows}
    print(f"Wrote {len(rows)} tehsils in {len(districts)} districts to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
