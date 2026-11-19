"""Risk inference: calibrated probability, level and drivers per tehsil, lead 0–3.

- Each weather model's forecast (ECMWF, GFS, ICON) goes through the same model;
  the calibrated probabilities are averaged across weather models.
- Levels come only from the probability and the fixed thresholds in meta.json.
- Drivers: how much the log-odds would drop if one input were at its typical
  (median) value; the largest increases are reported. Works for any model type.
"""

from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.app.contracts import RiskDriver, RiskLevel, TehsilRiskForecast
from backend.app.contracts.enums import HydrometModel
from backend.app.risk.features import FEATURE_LABELS, build_matrix, load_static

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts" / "v1"
PKT = dt.timezone(dt.timedelta(hours=5))
# Drivers people can act on or understand; terrain is constant, so it is shown last.
_DRIVER_ORDER_HINT = ("precip", "soil", "t2m")


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class RiskModel:
    def __init__(self, model, meta: dict) -> None:
        self.model = model
        self.meta = meta
        self.features: list[str] = meta["features"]
        self.medians: dict[str, float] = meta["feature_medians"]
        cal = meta["calibration"]
        self._a, self._b = cal["a"], cal["b"]
        self.thresholds = {RiskLevel(k): v["probability"] for k, v in meta["levels"].items()}
        # Forecast-tuned thresholds per lead (M7); used for forecast inputs when present.
        self.lead_thresholds: dict[int, dict[RiskLevel, float]] = {
            int(lead): {RiskLevel(k): v for k, v in levels.items()}
            for lead, levels in meta.get("forecast_levels", {}).items()}

    @classmethod
    def load(cls, directory: Path = ARTIFACT_DIR) -> RiskModel:
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        forecast_levels = directory / "forecast_levels.json"
        if forecast_levels.is_file():
            meta["forecast_levels"] = json.loads(forecast_levels.read_text(encoding="utf-8"))["levels"]
        return cls(joblib.load(directory / "model.joblib"), meta)

    @property
    def is_fallback(self) -> bool:
        return bool(self.meta.get("fallback"))

    def raw(self, frame: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(frame[self.features])[:, 1]

    def calibrate(self, raw: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-(self._a * _logit(raw) + self._b)))

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.calibrate(self.raw(frame))

    def level(self, probability: float, lead_days: int | None = None) -> RiskLevel:
        """Level from fixed thresholds. With a lead day, the forecast-tuned thresholds apply."""

        thresholds = self.thresholds
        if lead_days is not None and self.lead_thresholds:
            thresholds = self.lead_thresholds.get(max(lead_days, 1), thresholds)
        for level in (RiskLevel.VERY_HIGH, RiskLevel.HIGH, RiskLevel.MODERATE):
            if probability >= thresholds[level]:
                return level
        return RiskLevel.LOW

    def drivers(self, frame: pd.DataFrame, top_k: int = 4) -> list[list[RiskDriver]]:
        """Top features pushing each row's risk up (log-odds change versus the median)."""

        base = _logit(self.raw(frame))
        deltas = {}
        for f in self.features:
            changed = frame[self.features].copy()
            changed[f] = self.medians[f]
            deltas[f] = base - _logit(self.model.predict_proba(changed)[:, 1])
        out = []
        for i in range(len(frame)):
            ranked = sorted(((f, d[i]) for f, d in deltas.items() if d[i] > 0.05), key=lambda x: -x[1])
            drivers = []
            for f, c in ranked[:top_k]:
                raw = f[4:] if f.startswith("log_") and f[4:] in frame.columns else f  # show mm, not log(mm)
                drivers.append(RiskDriver(feature=raw, value=round(float(frame.iloc[i][raw]), 3),
                                          contribution=round(float(c), 3)))
            out.append(drivers)
        return out


def describe_driver(driver: RiskDriver) -> str:
    """Short English phrase for a driver, e.g. 'rain over 3 days: 62 mm'."""

    label = FEATURE_LABELS.get(driver.feature, driver.feature)
    if driver.feature.startswith(("log_", "doy_")) or driver.feature in {"share_low_hand", "drainage_density"}:
        return label
    if driver.feature.startswith("precip"):
        return f"{label}: {driver.value:.0f} mm"
    if driver.feature.startswith("soil"):
        return f"{label} ({driver.value:.2f} m³/m³)"
    return f"{label}: {driver.value:.1f}"


class RiskService:
    """Implements the RiskProvider protocol over the hydromet service."""

    def __init__(self, hydromet, model: RiskModel, static: pd.DataFrame, locator=None, rivers=None) -> None:
        self.hydromet = hydromet
        self.model = model
        self.static = static
        self.locator = locator
        self.rivers = rivers  # RiverMonitor or None
        self._cache: dict[tuple[dt.date, bool], list[TehsilRiskForecast]] = {}

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> RiskService:
        from backend.app.geo.locator import TehsilLocator
        from backend.app.hydromet import HydrometService

        from backend.app.config import get_settings
        from backend.app.hydromet.rivers import RiverMonitor

        hydromet = HydrometService.from_data_dir(data_dir)
        rivers = RiverMonitor.from_data_dir(data_dir, hydromet.client,
                                            get_settings().river_flag_return_period)
        return cls(hydromet, RiskModel.load(), load_static(data_dir),
                   TehsilLocator.from_geojson(data_dir / "reference" / "tehsils.geojson"), rivers)

    # ---- core ------------------------------------------------------------------------------

    def score(self, hydromet_rows: pd.DataFrame, issued_at: dt.datetime,
              river_flags: dict | None = None) -> list[TehsilRiskForecast]:
        frame = build_matrix(hydromet_rows, self.static)
        if frame.empty:
            return []
        frame["p"] = self.model.predict(frame)
        keys = ["tehsil_id", "date", "lead_days"]
        shown = sorted(set(self.model.features) | {f[4:] for f in self.model.features if f.startswith("log_")})
        shown = [f for f in shown if f in frame.columns]
        mean_features = frame.groupby(keys)[shown].mean().reset_index()
        agg = frame.groupby(keys).agg(p=("p", "mean"), models=("model", lambda s: tuple(sorted(set(s)))))
        mean_features = mean_features.merge(agg.reset_index(), on=keys)
        drivers = self.model.drivers(mean_features)
        out = []
        for row, drv in zip(mean_features.itertuples(index=False), drivers, strict=True):
            p = float(row.p)
            out.append(TehsilRiskForecast(
                tehsil_id=row.tehsil_id, issued_at=issued_at, valid_date=row.date, lead_days=int(row.lead_days),
                probability=round(p, 4), level=self.model.level(p, int(row.lead_days)), drivers=tuple(drv),
                models_used=tuple(HydrometModel(m) for m in row.models),
                glofas_flag=(row.tehsil_id, row.date) in (river_flags or {})))
        return out

    def forecast(self, issue: dt.date | None = None, replay: bool = False) -> list[TehsilRiskForecast]:
        """All tehsils, lead 0–3. `replay=True` uses the forecasts archived on `issue`."""

        issue = issue or dt.datetime.now(PKT).date()
        key = (issue, replay)
        if key not in self._cache:
            if replay:
                rows = self.hydromet.replay_features(issue)
                issued_at = dt.datetime.combine(issue, dt.time(0, 0), PKT)
            else:
                rows = self.hydromet.live_features(issue)
                issued_at = dt.datetime.now(PKT)
            self._cache[key] = self.score(rows, issued_at, self.river_flags(issue, replay))
        return self._cache[key]

    def river_flags(self, issue: dt.date, replay: bool) -> dict:
        """(tehsil_id, date) -> RiverReading at or above the flag level, for lead 0–3."""

        if self.rivers is None:
            return {}
        try:
            if replay:  # no archived GloFAS forecasts: use the reanalysis for those days
                readings = self.rivers.history(issue, issue + dt.timedelta(days=3))
            else:
                readings = self.rivers.forecast()
        except Exception:  # the river signal is secondary; never block the risk outlook
            return {}
        return self.rivers.tehsil_flags(readings)

    def river_readings(self, issue: dt.date | None = None, replay: bool = False) -> list:
        """Raw readings for the board (all points, lead 0–3)."""

        if self.rivers is None:
            return []
        issue = issue or dt.datetime.now(PKT).date()
        return self.rivers.history(issue, issue + dt.timedelta(days=3)) if replay else self.rivers.forecast()

    # ---- RiskProvider ----------------------------------------------------------------------

    def get_tehsil_risk(self, tehsil_id: str, start: dt.date, end: dt.date,
                        as_of: dt.datetime | None = None) -> list[TehsilRiskForecast]:
        issue = as_of.astimezone(PKT).date() if as_of else None
        replay = issue is not None and issue < dt.datetime.now(PKT).date()
        return [f for f in self.forecast(issue, replay)
                if f.tehsil_id == tehsil_id and start <= f.valid_date <= end]

    def get_risk_for_point(self, lat: float, lon: float,
                           as_of: dt.datetime | None = None) -> list[TehsilRiskForecast]:
        region = self.locator.locate(lat, lon) if self.locator else None
        if region is None:
            return []
        issue = as_of.astimezone(PKT).date() if as_of else dt.datetime.now(PKT).date()
        return self.get_tehsil_risk(region.tehsil_id, issue, issue + dt.timedelta(days=3), as_of)


@lru_cache(maxsize=1)
def get_risk_service() -> RiskService:
    from backend.app.config import get_settings

    return RiskService.from_data_dir(get_settings().data_dir)
