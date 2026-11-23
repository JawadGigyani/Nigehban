from __future__ import annotations

from enum import Enum


class Language(str, Enum):
    EN = "en"
    UR = "ur"  # Urdu in Nastaliq script (default for citizens)
    UR_ROMAN = "ur_roman"  # Roman Urdu (user setting)


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"

    @property
    def rank(self) -> int:
        return _RISK_ORDER.index(self)


_RISK_ORDER = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.VERY_HIGH]


class EventType(str, Enum):
    FLASH_FLOOD = "flash_flood"
    FLOOD = "flood"
    CLOUDBURST = "cloudburst"
    DROWNING = "drowning"  # only drowning in a stream, river or flood water
    LANDSLIDE = "landslide"
    ROOF_COLLAPSE = "roof_collapse"
    OTHER = "other"


# The single place that decides which events count as training positives.
POSITIVE_EVENT_TYPES: frozenset[EventType] = frozenset(
    {EventType.FLASH_FLOOD, EventType.FLOOD, EventType.CLOUDBURST, EventType.DROWNING}
)


def is_positive(event_type: EventType | str) -> bool:
    return EventType(event_type) in POSITIVE_EVENT_TYPES


class GeocodeLevel(str, Enum):
    VILLAGE = "village"
    TEHSIL = "tehsil"
    DISTRICT = "district"


class HydrometModel(str, Enum):
    ERA5 = "era5"
    ECMWF = "ecmwf"
    GFS = "gfs"
    ICON = "icon"
    IMERG = "imerg"


class ExposureBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ChannelName(str, Enum):
    CONSOLE = "console"
    WEB_INBOX = "web_inbox"
    # SMS, WhatsApp, browser push or a mobile app can be added here (see alerts/channels.py).
