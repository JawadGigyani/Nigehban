"""Use the 30 m village bands where a 30 m run exists (Swat), 90 m elsewhere.

Tehsil statics stay at 90 m everywhere so the model sees comparable values.

    python -m pipelines.terrain.merge_detail --tag swat30 --district swat
"""

from __future__ import annotations

import argparse

import pandas as pd

from backend.app.config import get_settings


def merge(base: pd.DataFrame, detail: pd.DataFrame, district: str, tag: str) -> pd.DataFrame:
    base = base.copy()
    if "dem" not in base.columns:
        base["dem"] = "glo90"
    keep = ~base["tehsil_id"].str.startswith(f"{district}__")
    detail = detail[detail["tehsil_id"].str.startswith(f"{district}__")].copy()
    detail["dem"] = tag
    return pd.concat([base[keep], detail[base.columns]], ignore_index=True).sort_values(
        ["tehsil_id", "village_id"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    data = get_settings().data_dir
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="swat30")
    parser.add_argument("--district", default="swat")
    args = parser.parse_args(argv)
    path = data / "reference" / "village_exposure.csv"
    base = pd.read_csv(path)
    detail = pd.read_csv(data / "interim" / "terrain" / args.tag / "village_exposure.csv")
    out = merge(base, detail, args.district, args.tag)
    out.to_csv(path, index=False)
    print(out.groupby("dem")["exposure_band"].value_counts().unstack().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
