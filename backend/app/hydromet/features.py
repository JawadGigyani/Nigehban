"""Turn Open-Meteo hourly responses into daily tehsil features (`HydrometDaily` rows).

Steps:
1. `hourly_to_daily`: one location's hourly series -> local-day values per cell
   (rain total, wettest hour, max temperature, mean soil moisture).
2. `cells_to_tehsils`: area-weighted mean over the tehsil's grid cells, plus the
   wettest cell (`precip_cell_max`) and the wettest hour in any cell.
3. `add_rolling`: rain over the last 3 days (`precip_3d`, includes the day) and
   the 7 days before (`precip_7d_antecedent`, excludes the day).
4. `add_anomaly`: max temperature minus the tehsil's ERA5 climatology for that
   time of year.

Forecast rows (lead 1–3) are built so they only use what was known when the
forecast was issued: days before the issue date come from the analysis (ERA5),
days from the issue date onward come from the forecast at the matching lead.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

from backend.app.hydromet.grid import CellWeight

DAILY_COLUMNS = ["precip_sum", "precip_max_1h", "t2m_max", "soil_moisture_0_7", "soil_moisture_7_28"]

# Open-Meteo hourly variable -> (daily column, aggregation)
HOURLY_VARIABLES = {
    "precipitation": ("precip_sum", "sum"),
    "temperature_2m": ("t2m_max", "max"),
    "soil_moisture_0_to_7cm": ("soil_moisture_0_7", "mean"),
    "soil_moisture_7_to_28cm": ("soil_moisture_7_28", "mean"),
}


def _series(hourly: dict, name: str, suffix: str | None) -> list | None:
    if suffix and f"{name}_{suffix}" in hourly:
        return hourly[f"{name}_{suffix}"]
    return hourly.get(name)


def hourly_to_daily(payload: dict, cell_key: str, *, suffix: str | None = None,
                    rename: dict[str, str] | None = None) -> pd.DataFrame:
    """Daily values for one location. `rename` maps an Open-Meteo variable to one
    of HOURLY_VARIABLES (used for `precipitation_previous_day2` -> `precipitation`)."""

    hourly = payload["hourly"]
    times = pd.to_datetime(pd.Series(hourly["time"]))
    frame = pd.DataFrame({"date": times.dt.date})
    names = dict(rename or {})
    for name in HOURLY_VARIABLES:
        names.setdefault(name, name)
    for target, source in names.items():
        values = _series(hourly, source, suffix)
        if values is not None:
            frame[target] = pd.to_numeric(pd.Series(values), errors="coerce")
    grouped = frame.groupby("date")
    out = pd.DataFrame(index=grouped.size().index)
    if "precipitation" in frame:
        counts = grouped["precipitation"].count()
        out["precip_sum"] = grouped["precipitation"].sum(min_count=1).where(counts >= 20)
        out["precip_max_1h"] = grouped["precipitation"].max().where(counts >= 20)
    for name, (column, how) in HOURLY_VARIABLES.items():
        if name == "precipitation" or name not in frame:
            continue
        out[column] = getattr(grouped[name], how)()
    out = out.reset_index()
    out.insert(0, "cell", cell_key)
    return out


def cells_to_tehsils(cell_daily: pd.DataFrame, grid: Sequence[CellWeight],
                     keys: Sequence[str] = ()) -> pd.DataFrame:
    """Aggregate cell values to tehsils. `keys` are extra grouping columns (model, lead_days)."""

    weights = pd.DataFrame({"tehsil_id": [g.tehsil_id for g in grid],
                            "cell": [g.cell.key for g in grid],
                            "weight": [g.weight for g in grid]})
    merged = weights.merge(cell_daily, on="cell", how="inner")
    group = ["tehsil_id", "date", *keys]
    parts = {}
    for column in ("precip_sum", "t2m_max", "soil_moisture_0_7", "soil_moisture_7_28"):
        if column not in merged:
            continue
        valid = merged[column].notna()
        wv = (merged[column] * merged["weight"]).where(valid)
        w = merged["weight"].where(valid)
        num = wv.groupby([merged[k] for k in group]).sum(min_count=1)
        den = w.groupby([merged[k] for k in group]).sum(min_count=1)
        parts[column] = num / den
    grouped = merged.groupby(group)
    if "precip_sum" in merged:
        parts["precip_cell_max"] = grouped["precip_sum"].max()
    if "precip_max_1h" in merged:
        parts["precip_max_1h"] = grouped["precip_max_1h"].max()
    return pd.DataFrame(parts).reset_index()


def add_rolling(frame: pd.DataFrame, keys: Sequence[str] = ()) -> pd.DataFrame:
    """Rolling rain sums over a continuous daily series per tehsil (and keys)."""

    frame = frame.sort_values(["tehsil_id", *keys, "date"]).copy()
    out = []
    for _, part in frame.groupby(["tehsil_id", *keys], sort=False):
        series = part.set_index(pd.to_datetime(part["date"]))["precip_sum"].asfreq("D")
        last3 = series.rolling(3, min_periods=3).sum()
        prev7 = series.shift(1).rolling(7, min_periods=7).sum()
        part = part.copy()
        idx = pd.to_datetime(part["date"])
        part["precip_3d"] = last3.reindex(idx).to_numpy()
        part["precip_7d_antecedent"] = prev7.reindex(idx).to_numpy()
        out.append(part)
    return pd.concat(out, ignore_index=True) if out else frame


def forecast_rolling(analysis: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    """Rolling sums for forecast rows using only what was known at issue time.

    `analysis`: tehsil_id, date, precip_sum (ERA5 or the model's own past days).
    `forecast`: tehsil_id, date, model, lead_days, precip_sum.
    For a row with target date d and lead L the issue date is d - L. Days before
    the issue date come from `analysis`; later days use the same issue's forecast.
    """

    a = analysis.set_index(["tehsil_id", "date"])["precip_sum"].to_dict()
    f = forecast.set_index(["tehsil_id", "model", "date", "lead_days"])["precip_sum"].to_dict()
    p3, p7 = [], []
    for row in forecast.itertuples(index=False):
        issue = row.date - dt.timedelta(days=int(row.lead_days))

        def value(day: dt.date) -> float | None:
            if day < issue:
                return a.get((row.tehsil_id, day))
            return f.get((row.tehsil_id, row.model, day, (day - issue).days))

        last3 = [value(row.date - dt.timedelta(days=k)) for k in range(3)]
        prev7 = [value(row.date - dt.timedelta(days=k)) for k in range(1, 8)]
        p3.append(_total(last3))
        p7.append(_total(prev7))
    out = forecast.copy()
    out["precip_3d"] = p3
    out["precip_7d_antecedent"] = p7
    return out


def _total(values: Iterable[float | None]) -> float | None:
    values = list(values)
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in values):
        return None
    return float(sum(values))


def build_climatology(era5: pd.DataFrame, window_days: int = 15) -> pd.DataFrame:
    """Mean daily max temperature per tehsil and day of year (±window, all years)."""

    frame = era5[["tehsil_id", "date", "t2m_max"]].dropna().copy()
    frame["doy"] = pd.to_datetime(frame["date"]).dt.day_of_year.clip(upper=365)
    daily = frame.groupby(["tehsil_id", "doy"])["t2m_max"].agg(["sum", "count"]).reset_index()
    rows = []
    for tehsil_id, part in daily.groupby("tehsil_id"):
        s = part.set_index("doy")[["sum", "count"]].reindex(range(1, 366), fill_value=0)
        sums, counts = s["sum"].to_numpy(), s["count"].to_numpy()
        for doy in range(1, 366):
            idx = [(doy - 1 + k) % 365 for k in range(-window_days, window_days + 1)]
            n = counts[idx].sum()
            if n >= 20:
                rows.append((tehsil_id, doy, round(float(sums[idx].sum() / n), 3)))
    return pd.DataFrame(rows, columns=["tehsil_id", "doy", "t2m_clim"])


def add_anomaly(frame: pd.DataFrame, climatology: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["doy"] = pd.to_datetime(out["date"]).dt.day_of_year.clip(upper=365)
    out = out.merge(climatology, on=["tehsil_id", "doy"], how="left")
    out["t2m_anomaly"] = out["t2m_max"] - out["t2m_clim"]
    return out.drop(columns=["doy", "t2m_clim"])


OUTPUT_COLUMNS = [
    "tehsil_id", "date", "model", "lead_days", "precip_sum", "precip_cell_max", "precip_max_1h",
    "precip_3d", "precip_7d_antecedent", "soil_moisture_0_7", "soil_moisture_7_28",
    "t2m_max", "t2m_anomaly", "glofas_discharge",
]


def finalise(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in OUTPUT_COLUMNS:
        if column not in out:
            out[column] = np.nan
    out = out[OUTPUT_COLUMNS]
    for column in OUTPUT_COLUMNS[4:]:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float64").round(3)
    for column in ("precip_sum", "precip_cell_max", "precip_max_1h", "precip_3d", "precip_7d_antecedent"):
        out[column] = out[column].clip(lower=0)
    out["lead_days"] = out["lead_days"].astype("int8")
    return out.sort_values(["tehsil_id", "model", "lead_days", "date"]).reset_index(drop=True)
