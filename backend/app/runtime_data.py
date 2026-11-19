"""Runtime data the deployed backend needs but GitHub does not hold (about 140 MB).

Shipped as a private Hugging Face dataset repo (`NIGEHBAN_RUNTIME_DATA_REPO`, read with
`HF_TOKEN`) and downloaded into data/ at startup when files are missing.
Build and upload it with `python -m pipelines.deploy.bundle_runtime_data --upload <repo>`.

No private data is included: no PDMA reports, extractions, events or labels.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

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


def ensure_runtime_data(data_dir: Path) -> list[str]:
    """Download the bundle when files are missing and a repo is configured. Returns what is still missing."""

    missing = missing_files(data_dir)
    repo = os.getenv("NIGEHBAN_RUNTIME_DATA_REPO")
    if not missing or not repo:
        return missing
    try:
        from huggingface_hub import snapshot_download

        log.info("downloading runtime data from %s (%d files missing)", repo, len(missing))
        snapshot_download(repo_id=repo, repo_type="dataset", local_dir=str(data_dir), token=os.getenv("HF_TOKEN"))
    except Exception as exc:  # keep serving: the board shows what is degraded
        log.error("runtime data download failed: %s", exc)
    return missing_files(data_dir)
