"""Hydromet service: daily tehsil features from ERA5, archived forecasts and live forecasts.

- `era5_features`: analysis rows (model `era5`, lead 0) for training.
- `previous_run_features`: archived ECMWF / GFS / ICON forecasts at lead 0–3
  (from March 2024) for the backtest and the replay switch.
- `live_features`: today's forecasts at lead 0–3, with antecedent rain from each
  model's own last 7 days. One request covers every tehsil.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from backend.app.hydromet.client import FORECAST_MODELS, OpenMeteoClient
from backend.app.hydromet.features import (
    add_anomaly,
    add_rolling,
    cells_to_tehsils,
    finalise,
    forecast_rolling,
    hourly_to_daily,
)
from backend.app.hydromet.grid import Cell, CellWeight, load_grid, unique_cells

log = logging.getLogger(__name__)

ERA5_HOURLY = ["precipitation", "temperature_2m", "soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm"]
LIVE_HOURLY = ["precipitation", "temperature_2m", "soil_moisture_0_to_7cm", "soil_moisture_7_to_28cm"]
PREVIOUS_HOURLY = ["precipitation", "precipitation_previous_day1", "precipitation_previous_day2",
                   "precipitation_previous_day3", "temperature_2m"]
PREVIOUS_RUNS_START = dt.date(2024, 3, 1)


def _batches(cells: Sequence[Cell], size: int) -> list[list[Cell]]:
    return [list(cells[i:i + size]) for i in range(0, len(cells), size)]


# ---- cell-level fetchers ------------------------------------------------------------------

def fetch_era5_cells(client: OpenMeteoClient, cells: Sequence[Cell], start: dt.date, end: dt.date,
                     batch: int = 20) -> pd.DataFrame:
    frames = []
    for group in _batches(cells, batch):
        payloads = client.archive(group, start, end, ERA5_HOURLY)
        for cell, payload in zip(group, payloads, strict=True):
            frames.append(hourly_to_daily(payload, cell.key))
    return pd.concat(frames, ignore_index=True)


def fetch_previous_run_cells(client: OpenMeteoClient, cells: Sequence[Cell], start: dt.date,
                             end: dt.date, batch: int = 20) -> pd.DataFrame:
    """Cell rows with columns model, lead_days. Lead 0 also carries temperature."""

    frames = []
    for group in _batches(cells, batch):
        payloads = client.previous_runs(group, start, end, PREVIOUS_HOURLY, list(FORECAST_MODELS.values()))
        for cell, payload in zip(group, payloads, strict=True):
            for model, om_name in FORECAST_MODELS.items():
                for lead in range(4):
                    source = "precipitation" if lead == 0 else f"precipitation_previous_day{lead}"
                    rename = {"precipitation": source}
                    if lead:
                        rename["temperature_2m"] = "__none__"
                    daily = hourly_to_daily(payload, cell.key, suffix=om_name, rename=rename)
                    daily = daily.drop(columns=["soil_moisture_0_7", "soil_moisture_7_28"], errors="ignore")
                    daily["model"], daily["lead_days"] = model, lead
                    frames.append(daily)
    return pd.concat(frames, ignore_index=True)


def fetch_live_cells(client: OpenMeteoClient, cells: Sequence[Cell], batch: int = 40,
                     past_days: int = 7, forecast_days: int = 4) -> pd.DataFrame:
    frames = []
    for group in _batches(cells, batch):
        payloads = client.forecast(group, LIVE_HOURLY, list(FORECAST_MODELS.values()),
                                   forecast_days=forecast_days, past_days=past_days)
        for cell, payload in zip(group, payloads, strict=True):
            for model, om_name in FORECAST_MODELS.items():
                daily = hourly_to_daily(payload, cell.key, suffix=om_name)
                daily["model"] = model
                frames.append(daily)
    return pd.concat(frames, ignore_index=True)


# ---- tehsil-level builders ----------------------------------------------------------------

def era5_features(cell_daily: pd.DataFrame, grid: Sequence[CellWeight],
                  climatology: pd.DataFrame | None = None) -> pd.DataFrame:
    tehsil = cells_to_tehsils(cell_daily, grid)
    tehsil = add_rolling(tehsil)
    if climatology is not None:
        tehsil = add_anomaly(tehsil, climatology)
    tehsil["model"], tehsil["lead_days"] = "era5", 0
    return finalise(tehsil)


def previous_run_features(cell_daily: pd.DataFrame, grid: Sequence[CellWeight], era5: pd.DataFrame,
                          climatology: pd.DataFrame | None = None) -> pd.DataFrame:
    """`era5` is the tehsil-level ERA5 table; it supplies the days before each issue
    date and the soil moisture known at issue time (the day before)."""

    tehsil = cells_to_tehsils(cell_daily, grid, keys=["model", "lead_days"])
    # Temperature is only fetched at lead 0; reuse it for the other leads.
    temp = tehsil[tehsil["lead_days"] == 0][["tehsil_id", "date", "model", "t2m_max"]]
    tehsil = tehsil.drop(columns=["t2m_max"]).merge(temp, on=["tehsil_id", "date", "model"], how="left")
    tehsil = forecast_rolling(era5[["tehsil_id", "date", "precip_sum"]], tehsil)
    tehsil["issue_date"] = [d - dt.timedelta(days=int(n)) for d, n in zip(tehsil["date"], tehsil["lead_days"])]
    soil = era5[["tehsil_id", "date", "soil_moisture_0_7", "soil_moisture_7_28"]].copy()
    soil["issue_date"] = soil["date"] + dt.timedelta(days=1)
    tehsil = tehsil.merge(soil.drop(columns=["date"]), on=["tehsil_id", "issue_date"], how="left")
    if climatology is not None:
        tehsil = add_anomaly(tehsil, climatology)
    return finalise(tehsil.drop(columns=["issue_date"]))


def live_tehsil_features(cell_daily: pd.DataFrame, grid: Sequence[CellWeight], issue: dt.date,
                         climatology: pd.DataFrame | None = None, max_lead: int = 3) -> pd.DataFrame:
    tehsil = cells_to_tehsils(cell_daily, grid, keys=["model"])
    tehsil = tehsil[tehsil["date"] <= issue + dt.timedelta(days=max_lead)]
    frames = []
    for model, part in tehsil.groupby("model"):
        past = part[part["date"] < issue]
        future = part[part["date"] >= issue].copy()
        future["lead_days"] = [(d - issue).days for d in future["date"]]
        frames.append(forecast_rolling(past[["tehsil_id", "date", "precip_sum"]], future))
    out = pd.concat(frames, ignore_index=True)
    # Models without soil moisture borrow ECMWF's value for the same tehsil and day.
    ecmwf = out[out["model"] == "ecmwf"].set_index(["tehsil_id", "date"])
    for column in ("soil_moisture_0_7", "soil_moisture_7_28"):
        if column in out:
            fallback = out.set_index(["tehsil_id", "date"]).index.map(ecmwf[column].to_dict())
            out[column] = out[column].fillna(pd.Series(fallback, index=out.index))
    if climatology is not None:
        out = add_anomaly(out, climatology)
    return finalise(out)


class HydrometService:
    """Live and replay features for every tehsil."""

    def __init__(self, client: OpenMeteoClient, grid: Sequence[CellWeight],
                 climatology: pd.DataFrame | None = None, era5_history: pd.DataFrame | None = None) -> None:
        self.client = client
        self.grid = list(grid)
        self.cells = unique_cells(self.grid)
        self.climatology = climatology
        self.era5_history = era5_history

    @classmethod
    def from_data_dir(cls, data_dir: Path, client: OpenMeteoClient | None = None) -> HydrometService:
        grid = load_grid(data_dir / "reference" / "tehsil_grid.csv")
        features = data_dir / "features"
        clim = features / "t2m_climatology.parquet"
        hist = features / "hydromet_daily.parquet"
        client = client or OpenMeteoClient(data_dir / "cache" / "openmeteo")
        era5 = None
        if hist.is_file():
            frame = pd.read_parquet(hist)
            era5 = frame[frame["model"] == "era5"]
        return cls(client, grid, pd.read_parquet(clim) if clim.is_file() else None, era5)

    def live_features(self, issue: dt.date | None = None) -> pd.DataFrame:
        issue = issue or dt.datetime.now(dt.timezone(dt.timedelta(hours=5))).date()
        cells = fetch_live_cells(self.client, self.cells)
        return live_tehsil_features(cells, self.grid, issue, self.climatology)

    def replay_features(self, issue: dt.date, max_lead: int = 3) -> pd.DataFrame:
        """Forecasts as they were issued on `issue` (archived runs), for the replay switch."""

        if issue < PREVIOUS_RUNS_START:
            raise ValueError(f"Archived forecasts start on {PREVIOUS_RUNS_START}")
        if self.era5_history is None:
            raise RuntimeError("Replay needs the ERA5 history (run pipelines.hydromet.build_history)")
        end = issue + dt.timedelta(days=max_lead)
        cells = fetch_previous_run_cells(self.client, self.cells, issue - dt.timedelta(days=1), end)
        rows = previous_run_features(cells, self.grid, self.era5_history, self.climatology)
        issued = [d - dt.timedelta(days=int(n)) for d, n in zip(rows["date"], rows["lead_days"])]
        return rows[[i == issue for i in issued]].reset_index(drop=True)
