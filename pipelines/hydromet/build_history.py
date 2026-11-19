"""Build `data/features/hydromet_daily.parquet` from Open-Meteo.

Fetches, per chunk of dates and per batch of 20 grid cells:
- ERA5 (model `era5`, lead 0): rain, temperature, soil moisture 0–7 and 7–28 cm.
- Archived forecasts (ECMWF, GFS, ICON at lead 0–3), from March 2024.

Chunks run in priority order (monsoon seasons first). Every response is cached
on disk, so a stopped run resumes where it left off; when the free daily quota
runs out the script stops cleanly and says so. The parquet is rebuilt from the
cache on every run, using the chunks that are complete.

Usage:
    python -m pipelines.hydromet.build_history              # core: Jun–Sep 2019–2025
    python -m pipelines.hydromet.build_history --scope all  # every month, 2019 to now
    python -m pipelines.hydromet.build_history --status
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.app.config import get_settings
from backend.app.hydromet.client import DailyLimitReached, OpenMeteoClient, RatePacer
from backend.app.hydromet.features import build_climatology
from backend.app.hydromet.grid import build_grid, check_weights, load_grid, unique_cells, write_grid
from backend.app.hydromet.service import (
    PREVIOUS_RUNS_START,
    era5_features,
    fetch_era5_cells,
    fetch_previous_run_cells,
    previous_run_features,
)

log = logging.getLogger("build_history")

FIRST_YEAR = 2019
ERA5_LAG_DAYS = 6  # ERA5 on Open-Meteo is about 5 days behind


@dataclass(frozen=True)
class Chunk:
    kind: str  # "era5" | "previous"
    start: dt.date
    end: dt.date
    priority: int

    @property
    def name(self) -> str:
        return f"{self.kind}:{self.start}:{self.end}"


def plan_chunks(today: dt.date, scope: str) -> list[Chunk]:
    era5_end = today - dt.timedelta(days=ERA5_LAG_DAYS)
    prev_end = today - dt.timedelta(days=1)
    chunks: list[Chunk] = []

    def add(kind: str, start: dt.date, end: dt.date, priority: int, last: dt.date) -> None:
        end = min(end, last)
        if kind == "previous":
            start = max(start, PREVIOUS_RUNS_START)
        if start <= end:
            chunks.append(Chunk(kind, start, end, priority))

    for year in range(FIRST_YEAR, today.year + 1):
        core = year < 2026
        # Monsoon with a lead-in for the 7-day antecedent rain.
        add("era5", dt.date(year, 5, 20), dt.date(year, 10, 10), 1 if core else 3, era5_end)
        add("previous", dt.date(year, 6, 1), dt.date(year, 9, 30), 2 if core else 3, prev_end)
        if scope == "all":
            add("era5", dt.date(year, 1, 1), dt.date(year, 5, 19), 4, era5_end)
            add("era5", dt.date(year, 10, 11), dt.date(year, 12, 31), 4, era5_end)
            add("previous", dt.date(year, 3, 1), dt.date(year, 5, 31), 5, prev_end)
            add("previous", dt.date(year, 10, 1), dt.date(year, 12, 31), 5, prev_end)
            add("previous", dt.date(year, 1, 1), dt.date(year, 2, 28), 5, prev_end)
    return sorted(chunks, key=lambda c: (c.priority, c.kind, c.start))


def _state_path(features: Path) -> Path:
    return features / "_hydromet_chunks.json"


def load_done(features: Path) -> set[str]:
    path = _state_path(features)
    return set(json.loads(path.read_text())) if path.is_file() else set()


def save_done(features: Path, done: set[str]) -> None:
    path = _state_path(features)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(done), indent=1))
    tmp.replace(path)


def fetch_chunk(client: OpenMeteoClient, chunk: Chunk, cells) -> pd.DataFrame:
    if chunk.kind == "era5":
        return fetch_era5_cells(client, cells, chunk.start, chunk.end)
    return fetch_previous_run_cells(client, cells, chunk.start, chunk.end)


def build_tables(client: OpenMeteoClient, chunks: list[Chunk], grid, cells) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Re-read completed chunks from the cache and build the feature tables."""

    era5_cells = [fetch_chunk(client, c, cells) for c in chunks if c.kind == "era5"]
    prev_cells = [fetch_chunk(client, c, cells) for c in chunks if c.kind == "previous"]
    era5_cell = pd.concat(era5_cells, ignore_index=True).drop_duplicates(["cell", "date"])
    era5 = era5_features(era5_cell, grid)
    climatology = build_climatology(era5)
    era5 = era5_features(era5_cell, grid, climatology)
    frames = [era5]
    if prev_cells:
        prev_cell = pd.concat(prev_cells, ignore_index=True).drop_duplicates(["cell", "date", "model", "lead_days"])
        frames.append(previous_run_features(prev_cell, grid, era5, climatology))
    return pd.concat(frames, ignore_index=True), climatology


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    data = settings.data_dir
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["core", "all"], default="core")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--build-only", action="store_true", help="skip fetching; build from cached chunks")
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--per-day", type=float, default=9500.0, help="local daily budget (charged calls)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    features = data / "features"
    grid_path = data / "reference" / "tehsil_grid.csv"
    if not grid_path.is_file():
        write_grid(build_grid(data / "reference" / "tehsils.geojson"), grid_path)
    grid = load_grid(grid_path)
    check_weights(grid)
    cells = unique_cells(grid)

    chunks = plan_chunks(args.today, args.scope)
    done = load_done(features)
    if args.status:
        for c in chunks:
            print(f"{'done' if c.name in done else 'todo'}  p{c.priority}  {c.name}")
        print(f"{sum(c.name in done for c in chunks)}/{len(chunks)} chunks done")
        return 0

    cache = data / "cache" / "openmeteo"
    pacer = RatePacer(per_day=args.per_day, state_path=cache / "_pacer.json")
    client = OpenMeteoClient(cache, pacer=pacer)
    stopped = None
    for chunk in chunks:
        if chunk.name in done or args.build_only:
            continue
        started = time.time()
        try:
            fetch_chunk(client, chunk, cells)
        except DailyLimitReached as exc:
            stopped = str(exc)
            log.warning("daily limit reached at %s: %s", chunk.name, exc)
            break
        done.add(chunk.name)
        save_done(features, done)
        log.info("done %s in %.0f s (%d network calls so far)", chunk.name, time.time() - started, client.calls)

    complete = [c for c in chunks if c.name in done]
    if not any(c.kind == "era5" for c in complete):
        print("No ERA5 chunk complete yet.")
        return 2
    table, climatology = build_tables(client, complete, grid, cells)
    features.mkdir(parents=True, exist_ok=True)
    table.to_parquet(features / "hydromet_daily.parquet", index=False)
    climatology.to_parquet(features / "t2m_climatology.parquet", index=False)
    summary = {
        "rows": len(table),
        "tehsils": int(table["tehsil_id"].nunique()),
        "chunks_done": f"{len(complete)}/{len(chunks)}",
        "by_model": {f"{m}_{l}": int(n) for (m, l), n in table.groupby(["model", "lead_days"]).size().items()},
        "stopped": stopped,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
