"""Database tables (SQLModel). SQLite locally, Postgres when deployed."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class SubscriptionRow(SQLModel, table=True):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("channel", "address_hash", name="uq_sub_channel_address"),)

    id: str = Field(default_factory=_uuid, primary_key=True)
    channel: str = Field(index=True)
    address_encrypted: str  # Fernet token; decrypt only to send
    address_hash: str = Field(index=True)  # keyed HMAC for lookup and dedupe
    language: str = "ur"
    tehsil_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    village_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: dt.datetime = Field(default_factory=_now)
    active: bool = True


class AlertRow(SQLModel, table=True):
    __tablename__ = "alerts"
    # One alert per tehsil, level and valid date (cooldown); a higher level is a new row.
    __table_args__ = (
        UniqueConstraint("tehsil_id", "level", "valid_date", name="uq_alert_tehsil_level_date"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    tehsil_id: str = Field(index=True)
    level: str
    valid_date: dt.date = Field(index=True)
    issued_at: dt.datetime = Field(default_factory=_now)
    reason_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    message_ur: str = ""
    message_en: str = ""
    message_ur_roman: str = ""
    lead_days: int = 0  # how far ahead the alert was issued
    audio_key: str = ""  # Urdu voice file (data/audio/<key>.mp3), empty when voice is off
    citations: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    sent_to_count: int = 0
    replay: bool = False  # produced in replay mode, not live


class DeliveryRow(SQLModel, table=True):
    __tablename__ = "deliveries"

    id: str = Field(default_factory=_uuid, primary_key=True)
    alert_id: str = Field(foreign_key="alerts.id", index=True)
    subscription_id: str = Field(foreign_key="subscriptions.id", index=True)
    channel: str
    ok: bool
    provider_message_id: str | None = None
    error: str | None = None
    created_at: dt.datetime = Field(default_factory=_now)
