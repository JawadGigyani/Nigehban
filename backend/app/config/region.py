"""Region configuration: candidate districts and the data bounding box.

The data stage covers every candidate district so the pilot choice stays open.
The pilot districts are chosen at gate G1 (after the PDMA event dataset), from
the number of usable events per district. Until then `PILOT_DISTRICTS` is empty
and code should use `active_districts()`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def contains(self, lat: float, lon: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lon <= self.east


@dataclass(frozen=True)
class District:
    name: str
    slug: str
    is_ardc: bool = False  # merged district under the ARDC framework


CANDIDATE_DISTRICTS: tuple[District, ...] = (
    District("Swat", "swat"),
    District("Buner", "buner"),
    District("Shangla", "shangla"),
    District("Upper Dir", "upper_dir"),
    District("Lower Dir", "lower_dir"),
    District("Bajaur", "bajaur", is_ardc=True),
    District("Malakand", "malakand"),
    District("Mansehra", "mansehra"),
    District("Battagram", "battagram"),
)

# Districts whose events are extracted and stored but not used for training.
OUT_OF_SCOPE_DISTRICTS: tuple[District, ...] = (
    District("Chitral", "chitral"),  # glacial floods; phase 2
)

# Set at gate G1. Empty means "all candidates".
PILOT_DISTRICTS: tuple[str, ...] = ()

# Covers all candidate districts with a small margin. Confirmed against the
# tehsil polygons in M4a.
CANDIDATE_BBOX = BoundingBox(south=34.1, west=71.1, north=36.0, east=73.8)


def active_districts() -> tuple[District, ...]:
    if not PILOT_DISTRICTS:
        return CANDIDATE_DISTRICTS
    return tuple(d for d in CANDIDATE_DISTRICTS if d.slug in PILOT_DISTRICTS)


def district_by_slug(slug: str) -> District:
    for district in CANDIDATE_DISTRICTS + OUT_OF_SCOPE_DISTRICTS:
        if district.slug == slug:
            return district
    raise KeyError(slug)


def make_tehsil_id(district_slug: str, tehsil_slug: str) -> str:
    """Build the stable tehsil identifier used across every contract."""

    return f"{district_slug}__{tehsil_slug}"
