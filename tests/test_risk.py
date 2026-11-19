"""M5 risk model: alert scoring, levels, drivers, and the shipped artifact."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.app.contracts import RiskLevel, TehsilRiskForecast
from backend.app.risk.features import FEATURES, add_log_features
from backend.app.risk.service import ARTIFACT_DIR, RiskModel, RiskService, describe_driver
from pipelines.risk.train import alert_scores

D = dt.date


def _frame(days: int = 10, tehsils=("a__x", "a__y")) -> pd.DataFrame:
    rows = [{"tehsil_id": t, "date": D(2025, 7, 1) + dt.timedelta(days=i), "year": 2025, "near_event": False}
            for t in tehsils for i in range(days)]
    return pd.DataFrame(rows)


def test_alert_scoring_hits_and_false_alert_runs():
    frame = _frame()
    events = pd.DataFrame({"tehsil_id": ["a__x"], "date": [D(2025, 7, 5)]})
    near = (frame["tehsil_id"] == "a__x") & frame["date"].between(D(2025, 7, 4), D(2025, 7, 6))
    frame.loc[near, "near_event"] = True
    score = np.zeros(len(frame))
    score[(frame["tehsil_id"] == "a__x") & (frame["date"] == D(2025, 7, 6))] = 1  # day after: a hit
    y_rows = frame["tehsil_id"] == "a__y"
    score[y_rows & frame["date"].isin([D(2025, 7, 2), D(2025, 7, 3)])] = 1  # one run of 2 days
    score[y_rows & (frame["date"] == D(2025, 7, 8))] = 1  # a second run
    r = alert_scores(frame, score, 0.5, events)
    assert r["hits"] == 1 and r["hit_rate"] == 1.0
    assert r["false_alerts_per_tehsil_season"] == 2 / 2  # 2 runs over 2 tehsil-seasons


def test_log_features():
    out = add_log_features(pd.DataFrame({c: [0.0, np.e - 1] for c in
                                         ["precip_sum", "precip_cell_max", "precip_max_1h", "precip_3d",
                                          "precip_7d_antecedent"]}))
    assert out["log_precip_3d"].tolist() == pytest.approx([0.0, 1.0])


class _Toy:
    """Probability rises with rain in the wettest cell only."""

    def predict_proba(self, x):
        z = -6 + 2.0 * x["log_precip_cell_max"].to_numpy()
        p = 1 / (1 + np.exp(-z))
        return np.c_[1 - p, p]


def _toy_model() -> RiskModel:
    meta = {"features": FEATURES, "feature_medians": {f: 0.0 for f in FEATURES},
            "calibration": {"a": 1.0, "b": 0.0},
            "levels": {"moderate": {"probability": 0.05}, "high": {"probability": 0.2},
                       "very_high": {"probability": 0.6}}}
    return RiskModel(_Toy(), meta)


def test_levels_and_drivers():
    model = _toy_model()
    assert model.level(0.01) is RiskLevel.LOW and model.level(0.1) is RiskLevel.MODERATE
    assert model.level(0.3) is RiskLevel.HIGH and model.level(0.9) is RiskLevel.VERY_HIGH
    frame = pd.DataFrame([{f: 0.0 for f in FEATURES} | {"log_precip_cell_max": np.log1p(60),
                                                        "precip_cell_max": 60.0}])
    (drivers,) = model.drivers(frame)
    assert drivers[0].feature == "precip_cell_max" and drivers[0].value == 60.0
    assert describe_driver(drivers[0]) == "rain in the wettest part of the tehsil: 60 mm"


def test_service_scores_forecast_rows():
    static = pd.DataFrame({"tehsil_id": ["swat__babuzai"], "log_population": [12.0], "log_high_villages": [3.0],
                           "mean_slope": [20.0], "p90_slope": [30.0], "drainage_density": [0.6],
                           "share_low_hand": [0.04], "log_catchment_km2": [8.0], "log_population_low_hand": [9.0]})
    rows = []
    for model in ("ecmwf", "gfs", "icon"):
        for lead in range(4):
            rain = 80.0 if lead == 1 else 1.0
            rows.append({"tehsil_id": "swat__babuzai", "date": D(2025, 8, 14) + dt.timedelta(days=lead),
                         "model": model, "lead_days": lead, "precip_sum": rain, "precip_cell_max": rain,
                         "precip_max_1h": rain / 8, "precip_3d": rain + 2, "precip_7d_antecedent": 10.0,
                         "soil_moisture_0_7": 0.3, "soil_moisture_7_28": 0.3, "t2m_max": 30.0,
                         "t2m_anomaly": 0.0})
    service = RiskService(hydromet=None, model=_toy_model(), static=static)
    out = service.score(pd.DataFrame(rows), dt.datetime(2025, 8, 14, tzinfo=dt.timezone.utc))
    assert len(out) == 4 and all(isinstance(f, TehsilRiskForecast) for f in out)
    by_lead = {f.lead_days: f for f in out}
    assert by_lead[1].level.rank > by_lead[0].level.rank
    assert len(by_lead[1].models_used) == 3


@pytest.mark.skipif(not (ARTIFACT_DIR / "meta.json").is_file(), reason="model not trained yet")
def test_shipped_artifact_is_consistent():
    meta = json.loads((ARTIFACT_DIR / "meta.json").read_text(encoding="utf-8"))
    assert meta["features"] == FEATURES
    levels = meta["levels"]
    assert levels["moderate"]["probability"] < levels["high"]["probability"] < levels["very_high"]["probability"]
    model = RiskModel.load()
    frame = pd.DataFrame([meta["feature_medians"]])
    assert 0 <= model.predict(frame)[0] <= 1


def test_lead_specific_levels_override_era5_levels():
    model = _toy_model()
    model.lead_thresholds = {1: {RiskLevel.MODERATE: 0.01, RiskLevel.HIGH: 0.02, RiskLevel.VERY_HIGH: 0.03}}
    assert model.level(0.025) is RiskLevel.LOW  # ERA5 levels (moderate at 0.05) without a lead
    assert model.level(0.025, lead_days=1) is RiskLevel.HIGH
    assert model.level(0.025, lead_days=0) is RiskLevel.HIGH  # lead 0 uses lead 1
    assert model.level(0.025, lead_days=3) is RiskLevel.LOW  # no lead-3 entry: ERA5 levels
