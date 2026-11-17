"""Polite, resumable downloader for PDMA KP Daily Situation Reports.

Fetches `ViewDSR.aspx?DSRID=<n>` one page at a time with a fixed pause
between requests, and caches each real report as gzip HTML under
`data/raw/pdma_dsr/`. Every ID tried is logged to `_index.jsonl` (report or
empty or error) so a rerun skips what is done and retries only errors.

Raw pages contain victims' names. They stay in the private, gitignored raw
folder and are never printed; only place, date and event fields are extracted
later (M1).

Usage:
    python -m pipelines.pdma.fetch_dsr --start 1 --end 8200
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import logging
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from backend.app.config import get_settings

logger = logging.getLogger("pdma.fetch")

# A real report carries "Date: dd/mm/yyyy" near the header. Empty IDs return a
# short page with a blank "Date:" or none at all.
_DATE_RE = re.compile(r"Date:\s*(?:<[^>]*>\s*)*(\d{1,2})/(\d{1,2})/(\d{4})")

INDEX_NAME = "_index.jsonl"

_RETRY_STATUSES = frozenset({429, 502, 503, 504})


@dataclass(frozen=True)
class IndexEntry:
    dsrid: int
    status: str  # "report" | "empty" | "error"
    bytes: int
    report_date: str | None
    http_status: int | None
    fetched_at: str
    error: str | None = None


def parse_report_date(html: str) -> dt.date | None:
    match = _DATE_RE.search(html)
    if not match:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def cache_path(cache_dir: Path, dsrid: int) -> Path:
    return cache_dir / f"{dsrid:05d}.html.gz"


def load_index(cache_dir: Path) -> dict[int, IndexEntry]:
    """Latest entry per ID (later lines win, so a retried error is replaced)."""

    entries: dict[int, IndexEntry] = {}
    index = cache_dir / INDEX_NAME
    if not index.exists():
        return entries
    with index.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = IndexEntry(**json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
            entries[entry.dsrid] = entry
    return entries


def _append_index(cache_dir: Path, entry: IndexEntry) -> None:
    with (cache_dir / INDEX_NAME).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")


Fetcher = Callable[[int], httpx.Response]


def make_http_fetcher(base_url: str, user_agent: str, timeout_s: float = 30.0) -> Fetcher:
    client = httpx.Client(
        headers={"User-Agent": user_agent},
        timeout=timeout_s,
        follow_redirects=True,
    )

    def fetch(dsrid: int) -> httpx.Response:
        return client.get(base_url, params={"DSRID": dsrid})

    return fetch


def fetch_one(
    dsrid: int,
    fetcher: Fetcher,
    cache_dir: Path,
    *,
    attempts: int = 3,
    backoff_s: float = 10.0,
    sleep: Callable[[float], None] = time.sleep,
) -> IndexEntry:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    last_error: str | None = None
    status_code: int | None = None

    for attempt in range(attempts):
        try:
            response = fetcher(dsrid)
            status_code = response.status_code
            # The site answers missing IDs with HTTP 500 and a short error page,
            # so a 500 is treated as a page (empty unless it has a report date).
            # Only throttling and gateway errors are retried.
            if status_code in _RETRY_STATUSES:
                raise httpx.HTTPStatusError(
                    f"server returned {status_code}", request=response.request, response=response
                )
            html = response.text
            report_date = parse_report_date(html)
            if report_date is None:
                return IndexEntry(dsrid, "empty", len(response.content), None, status_code, now)
            with gzip.open(cache_path(cache_dir, dsrid), "wt", encoding="utf-8") as fh:
                fh.write(html)
            return IndexEntry(
                dsrid, "report", len(response.content), report_date.isoformat(), status_code, now
            )
        except (httpx.HTTPError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < attempts:
                sleep(backoff_s * (attempt + 1))

    return IndexEntry(dsrid, "error", 0, None, status_code, now, last_error)


def run(
    start: int,
    end: int,
    cache_dir: Path,
    fetcher: Fetcher,
    *,
    interval_s: float,
    retry_errors: bool = True,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, int]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    done = load_index(cache_dir)
    counts = {"report": 0, "empty": 0, "error": 0, "skipped": 0}
    last_request = -float("inf")

    for dsrid in range(start, end + 1):
        previous = done.get(dsrid)
        if previous and (previous.status != "error" or not retry_errors):
            counts["skipped"] += 1
            continue

        wait = interval_s - (clock() - last_request)
        if wait > 0:
            sleep(wait)
        last_request = clock()

        entry = fetch_one(dsrid, fetcher, cache_dir, sleep=sleep)
        _append_index(cache_dir, entry)
        counts[entry.status] += 1

        if entry.status == "error":
            logger.warning("DSRID %d failed: %s", dsrid, entry.error)
        total = sum(counts.values()) - counts["skipped"]
        if total % 50 == 0 or dsrid == end:
            logger.info(
                "DSRID %d | reports %d, empty %d, errors %d, skipped %d",
                dsrid, counts["report"], counts["empty"], counts["error"], counts["skipped"],
            )
    return counts


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=8200)
    parser.add_argument("--interval", type=float, default=settings.pdma_request_interval_s)
    parser.add_argument("--cache-dir", type=Path, default=settings.raw_pdma_dir)
    parser.add_argument("--no-retry-errors", action="store_true")
    args = parser.parse_args(argv)

    if args.interval < 1.0:
        parser.error("--interval must be at least 1 second (be polite to PDMA).")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    fetcher = make_http_fetcher(settings.pdma_base_url, settings.pdma_user_agent)
    counts = run(
        args.start,
        args.end,
        args.cache_dir,
        fetcher,
        interval_s=args.interval,
        retry_errors=not args.no_retry_errors,
    )
    logger.info("Finished: %s", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
