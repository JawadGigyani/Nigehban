"""Data files the backend needs at runtime, built by the pipelines (see docs/DATA.md).

`/health` reports any that are missing as "degraded". These files are large and gitignored; none of
them hold private data (no PDMA reports, extractions, events or labels).
"""

from __future__ import annotations

from pathlib import Path

# Paths relative to data/. Directories end with "/".
RUNTIME_FILES = [
    "features/hydromet_daily.parquet",
    "features/t2m_climatology.parquet",
    "features/tehsil_static.parquet",
    "interim/terrain/hand.tif",
    "interim/terrain/stream_upstream_km2.tif",
    "interim/terrain/swat30/hand.tif",
    "interim/terrain/swat30/stream_upstream_km2.tif",
    "raw/osm/riverside_spots_overpass.json.gz",
    "cache/osm_roads/",
    "cache/openmeteo/",  # archived forecasts behind the replay switch; live entries refresh themselves
]
REQUIRED = [p for p in RUNTIME_FILES if not p.endswith("/")]


def missing_files(data_dir: Path) -> list[str]:
    return [p for p in REQUIRED if not (data_dir / p).exists()]
