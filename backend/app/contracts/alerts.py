"""API-facing contracts for subscriptions and alerts.

Database rows live in `backend.app.db.models`. Contact addresses never appear
in a read model; they are stored encrypted.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from backend.app.contracts._base import Contract
from backend.app.contracts.enums import ChannelName, Language, RiskLevel


class SubscriptionCreate(Contract):
    channel: ChannelName
    address: str = Field(min_length=1, max_length=2048)  # web inbox: the browser's random device id
    language: Language = Language.UR
    tehsil_ids: tuple[str, ...] = ()
    village_ids: tuple[str, ...] = ()


class Subscription(Contract):
    id: str
    channel: ChannelName
    language: Language
    tehsil_ids: tuple[str, ...]
    village_ids: tuple[str, ...]
    created_at: datetime
    active: bool


class Alert(Contract):
    id: str
    tehsil_id: str = Field(min_length=1)
    level: RiskLevel
    valid_date: date
    issued_at: datetime
    reason_codes: tuple[str, ...] = ()
    message_ur: str
    message_en: str
    message_ur_roman: str = ""
    lead_days: int = Field(default=0, ge=0, le=3)
    citations: tuple[str, ...] = ()
    sent_to_count: int = Field(default=0, ge=0)
