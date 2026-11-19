"""Contracts for the offline data files (one row per model instance).

File locations are listed in `data/contracts/README.md`.
"""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from backend.app.contracts._base import Contract
from backend.app.contracts.enums import (
    EventType,
    ExposureBand,
    GeocodeLevel,
    HydrometModel,
    is_positive,
)

Latitude = Field(ge=-90, le=90)
Longitude = Field(ge=-180, le=180)


class TehsilRegion(Contract):
    """Properties of one feature in `data/reference/tehsils.geojson`."""

    tehsil_id: str = Field(min_length=1)
    district: str = Field(min_length=1)
    tehsil: str = Field(min_length=1)
    centroid_lat: float = Latitude
    centroid_lon: float = Longitude
    is_ardc: bool = False
    pcode: str | None = None  # OCHA COD-AB P-code
    area_km2: float | None = Field(default=None, ge=0)
    in_scope: bool = True  # False for districts kept only for geocoding (e.g. Chitral)


class FloodEvent(Contract):
    """One row of `data/events/flood_events.parquet`. Never holds personal names."""

    event_id: str = Field(min_length=1)
    date: dt.date  # day the event happened
    report_date: dt.date  # date printed on the PDMA report
    district: str = Field(min_length=1)
    tehsil: str | None = None
    tehsil_id: str | None = None
    village: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    geocode_level: GeocodeLevel
    event_type: EventType
    deaths: int | None = Field(default=None, ge=0)
    houses_damaged: int | None = Field(default=None, ge=0)
    source_dsrid: int = Field(ge=1)
    extract_confidence: float = Field(ge=0, le=1)
    place_role: str | None = None  # "incident" | "residence" | "unclear" (where the place came from)
    water_body: str | None = None  # river or stream named in the report
    n_reports: int = Field(default=1, ge=1)  # reports merged into this event

    @property
    def is_positive(self) -> bool:
        return is_positive(self.event_type)


class HydrometDaily(Contract):
    """One row of `data/features/hydromet_daily.parquet`.

    `lead_days` is 0 for analysis data (ERA5, IMERG) and 0–3 for forecasts.
    """

    tehsil_id: str = Field(min_length=1)
    date: dt.date
    model: HydrometModel
    lead_days: int = Field(ge=0, le=3)
    precip_sum: float = Field(ge=0)  # area mean over the tehsil (mm)
    precip_cell_max: float | None = Field(default=None, ge=0)  # wettest grid cell in the tehsil (mm)
    precip_max_1h: float | None = Field(default=None, ge=0)
    precip_3d: float | None = Field(default=None, ge=0)
    precip_7d_antecedent: float | None = Field(default=None, ge=0)
    soil_moisture_0_7: float | None = Field(default=None, ge=0, le=1)  # m³/m³
    soil_moisture_7_28: float | None = Field(default=None, ge=0, le=1)  # m³/m³
    t2m_max: float | None = None
    t2m_anomaly: float | None = None
    glofas_discharge: float | None = Field(default=None, ge=0)


class TehsilStatic(Contract):
    """One row of `data/features/tehsil_static.parquet`."""

    tehsil_id: str = Field(min_length=1)
    mean_slope: float = Field(ge=0)
    p90_slope: float = Field(ge=0)
    catchment_area_km2: float = Field(ge=0)
    drainage_density: float = Field(ge=0)
    share_low_hand: float = Field(ge=0, le=1)
    population: float | None = Field(default=None, ge=0)
    population_low_hand: float | None = Field(default=None, ge=0)


class VillageExposure(Contract):
    """One row of `data/reference/village_exposure.csv`. Bands only, never depths."""

    village_id: str = Field(min_length=1)
    hand_m: float  # height above the nearest stream at the village point (m)
    hand_min_m: float | None = None  # lowest HAND within about 180 m (what the band uses)
    exposure_band: ExposureBand
    dist_to_stream_m: float = Field(ge=0)
    upstream_area_km2: float | None = Field(default=None, ge=0)  # catchment of the nearest stream
    tehsil_id: str | None = None


class RiverPointThresholds(Contract):
    point_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    lat: float = Latitude
    lon: float = Longitude
    q2: float = Field(ge=0)
    q5: float = Field(ge=0)
    q10: float = Field(ge=0)
    q20: float = Field(ge=0)
    years_used: int = Field(ge=1)


class RiverThresholds(Contract):
    """Whole of `data/reference/river_points_thresholds.json`."""

    source: str = "GloFAS via Open-Meteo Flood API"
    method: str = Field(min_length=1)
    points: tuple[RiverPointThresholds, ...]
