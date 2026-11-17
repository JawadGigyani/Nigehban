from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable

from pydantic import Field

from backend.app.contracts._base import Contract
from backend.app.contracts.enums import HydrometModel, RiskLevel


class RiskDriver(Contract):
    """One feature that pushed the risk up or down, for explanations."""

    feature: str = Field(min_length=1)
    value: float
    contribution: float  # model contribution on the log-odds scale


class TehsilRiskForecast(Contract):
    tehsil_id: str = Field(min_length=1)
    issued_at: datetime
    valid_date: date
    lead_days: int = Field(ge=0, le=3)
    probability: float = Field(ge=0, le=1)
    level: RiskLevel  # from the model and fixed thresholds, never from the LLM
    drivers: tuple[RiskDriver, ...] = ()
    models_used: tuple[HydrometModel, ...] = ()
    glofas_flag: bool = False
    stale: bool = False  # inputs older than expected


@runtime_checkable
class RiskProvider(Protocol):
    """Source of tehsil risk. `as_of` replays a past moment (replay mode)."""

    def get_tehsil_risk(
        self,
        tehsil_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> list[TehsilRiskForecast]: ...

    def get_risk_for_point(
        self, lat: float, lon: float, as_of: datetime | None = None
    ) -> list[TehsilRiskForecast]: ...
