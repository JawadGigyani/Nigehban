"""Model features: one place that turns hydromet rows + tehsil statics into the model matrix.

Used by training (ERA5 rows) and by inference (forecast rows per weather model),
so both see exactly the same columns.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIN_FEATURES = [
    "precip_sum", "precip_cell_max", "precip_max_1h", "precip_3d", "precip_7d_antecedent",
    "soil_moisture_0_7", "soil_moisture_7_28", "t2m_max", "t2m_anomaly",
]
SEASON_FEATURES = ["doy_sin", "doy_cos"]
STATIC_FEATURES = [
    "mean_slope", "p90_slope", "log_catchment_km2", "drainage_density", "share_low_hand",
    "log_population", "log_population_low_hand", "log_high_villages",
]
ALL_FEATURES = RAIN_FEATURES + SEASON_FEATURES + STATIC_FEATURES
# The model's features, chosen on held-out seasons and districts (reports/risk_model.md):
# with under 100 positive days, a small rain-centred set generalises best.
FEATURES = ["log_precip_cell_max", "log_precip_3d", "log_precip_max_1h", "log_precip_7d_antecedent",
            "soil_moisture_0_7", "log_population", "log_high_villages"]
RAIN_ONLY_FEATURES = FEATURES[:5]
# More rain or wetter ground never lowers the risk (keeps the model sensible with few events).
MONOTONE = {f: 1 for f in ["precip_sum", "precip_cell_max", "precip_max_1h", "precip_3d",
                           "precip_7d_antecedent", "soil_moisture_0_7", "soil_moisture_7_28",
                           "log_precip_sum", "log_precip_cell_max", "log_precip_max_1h", "log_precip_3d",
                           "log_precip_7d_antecedent"]}

# Plain-language names for drivers shown to people.
FEATURE_LABELS = {
    "precip_sum": "rain on the day",
    "precip_cell_max": "rain in the wettest part of the tehsil",
    "precip_max_1h": "heaviest hourly rain",
    "precip_3d": "rain over 3 days",
    "precip_7d_antecedent": "rain in the week before",
    "soil_moisture_0_7": "wet topsoil",
    "soil_moisture_7_28": "wet deeper soil",
    "t2m_max": "temperature",
    "t2m_anomaly": "temperature above normal",
    "doy_sin": "time of the monsoon",
    "doy_cos": "time of the monsoon",
    "mean_slope": "steep slopes",
    "p90_slope": "very steep slopes",
    "log_catchment_km2": "large river catchment",
    "drainage_density": "many streams",
    "share_low_hand": "much low-lying land by streams",
    "log_population": "population",
    "log_population_low_hand": "people living on low ground",
    "log_high_villages": "villages on low ground by rivers",
}


def load_static(data_dir: Path) -> pd.DataFrame:
    """Tehsil statics from M3 with the derived columns the model uses."""

    static = pd.read_parquet(data_dir / "features" / "tehsil_static.parquet")
    villages = pd.read_csv(data_dir / "reference" / "village_exposure.csv")
    high = villages[villages["exposure_band"] == "high"].groupby("tehsil_id").size()
    out = static[["tehsil_id", "mean_slope", "p90_slope", "drainage_density", "share_low_hand"]].copy()
    out["log_catchment_km2"] = np.log1p(static["catchment_area_km2"])
    out["log_population"] = np.log1p(static["population"].fillna(0))
    out["log_population_low_hand"] = np.log1p(static["population_low_hand"].fillna(0))
    out["log_high_villages"] = np.log1p(out["tehsil_id"].map(high).fillna(0))
    return out


def build_matrix(hydromet: pd.DataFrame, static: pd.DataFrame) -> pd.DataFrame:
    """Join hydromet rows with statics and add season features. Keeps the key columns."""

    frame = hydromet.merge(static, on="tehsil_id", how="inner")
    doy = pd.to_datetime(frame["date"]).dt.day_of_year
    frame["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    frame["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return add_log_features(frame)


LOG_SOURCES = ["precip_sum", "precip_cell_max", "precip_max_1h", "precip_3d", "precip_7d_antecedent"]


def add_log_features(frame: pd.DataFrame) -> pd.DataFrame:
    """log(1 + rain) columns: rain is very skewed, and linear models need it on a log scale."""

    out = frame.copy()
    for column in LOG_SOURCES:
        out[f"log_{column}"] = np.log1p(out[column].clip(lower=0))
    return out
