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
    name: str  # the spelling PDMA uses
    slug: str
    is_ardc: bool = False  # merged district under the ARDC framework
    cod_name: str | None = None  # spelling in OCHA COD-AB, when different


CANDIDATE_DISTRICTS: tuple[District, ...] = (
    District("Swat", "swat"),
    District("Buner", "buner"),
    District("Shangla", "shangla"),
    District("Upper Dir", "upper_dir"),
    District("Lower Dir", "lower_dir"),
    District("Bajaur", "bajaur", is_ardc=True),
    District("Malakand", "malakand"),
    District("Mansehra", "mansehra"),
    District("Battagram", "battagram", cod_name="Batagram"),
)

# Districts whose events are extracted and stored but not used for training.
OUT_OF_SCOPE_DISTRICTS: tuple[District, ...] = (
    District("Upper Chitral", "upper_chitral", cod_name="Chitral Upper"),  # glacial; phase 2
    District("Lower Chitral", "lower_chitral", cod_name="Chitral Lower"),  # glacial; phase 2
)

# Set at gate G1. Empty means "all candidates".
PILOT_DISTRICTS: tuple[str, ...] = ()

# Bounds of the in-scope tehsil polygons (71.173-74.127 E, 34.150-35.899 N,
# from COD-AB in M4a) plus about 5 km. Mansehra reaches 74.13 E.
CANDIDATE_BBOX = BoundingBox(south=34.10, west=71.12, north=35.95, east=74.18)

# Every kept tehsil, including out-of-scope Chitral (up to 36.91 N).
REGION_BBOX = BoundingBox(south=34.10, west=71.12, north=36.95, east=74.18)


def active_districts() -> tuple[District, ...]:
    if not PILOT_DISTRICTS:
        return CANDIDATE_DISTRICTS
    return tuple(d for d in CANDIDATE_DISTRICTS if d.slug in PILOT_DISTRICTS)


def district_by_slug(slug: str) -> District:
    for district in CANDIDATE_DISTRICTS + OUT_OF_SCOPE_DISTRICTS:
        if district.slug == slug:
            return district
    raise KeyError(slug)


def slugify(name: str) -> str:
    """Lowercase ASCII slug: 'Matta Kharirai' -> 'matta_kharirai'."""

    out, prev_us = [], False
    for ch in name.strip().lower():
        if ch.isascii() and ch.isalnum():
            out.append(ch)
            prev_us = False
        elif not prev_us:
            out.append("_")
            prev_us = True
    return "".join(out).strip("_")


def make_tehsil_id(district_slug: str, tehsil_slug: str) -> str:
    """Build the stable tehsil identifier used across every contract."""

    return f"{district_slug}__{tehsil_slug}"
