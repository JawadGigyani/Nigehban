"""Extract flood incidents from PDMA reports with an LLM (LangChain).

For every cached report, each district row in the summary table is put in one
of four groups:
- flood_like (flash flood, flood, cloudburst, drowning, nullah, stream, river):
  its incident text is redacted and sent to the LLM, which fills a fixed form;
- landslide, collapse (roof/house/wall collapse in rain): built later from the
  summary table alone (district level), no LLM call;
- unrelated (electrocution, fire, traffic...): skipped.

Every LLM answer is cached in `data/interim/pdma_llm/` (one JSON file per
report and district, keyed by a hash of the redacted text), so reruns are free
and an interrupted run continues where it stopped. Only redacted text leaves
the machine, and nothing but the structured answer is stored.

Usage:
    python -m pipelines.pdma.extract --dry-run          # count work, no LLM calls
    python -m pipelines.pdma.extract [--limit N] [--sleep 3]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import re
import sys
import time
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.config import get_settings
from backend.app.geo import AdminNames
from pipelines.pdma.parse_dsr import ParsedReport, SummaryRow, load_report
from pipelines.pdma.redact import has_name_markers, safe_redact

logger = logging.getLogger("pdma.extract")

FLOOD_LIKE = re.compile(
    r"flash|flood|cloud\s*-?\s*burst|drown|torrent|nullah|nala\b|khwar|stream|swept|river|inundat",
    re.IGNORECASE,
)
LANDSLIDE = re.compile(r"land\s*-?\s*slid|mud\s*slide|rock\s*fall|glacier|avalanche|GLOF", re.IGNORECASE)
COLLAPSE = re.compile(r"roof|house|wall|room|building|structure", re.IGNORECASE)
WEATHER = re.compile(r"rain|snow|storm|wind|weather|flood|monsoon", re.IGNORECASE)

PROMPT_VERSION = "v1"


# ---- The form the LLM fills -------------------------------------------------

EventTypeLit = Literal[
    "flash_flood", "flood", "cloudburst", "drowning", "landslide", "roof_collapse", "other"
]


class ExtractedIncident(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: EventTypeLit
    event_date: str | None = Field(description="YYYY-MM-DD, the day the incident happened")
    tehsil: str | None = Field(description="Tehsil name if stated, else null")
    villages: list[str] = Field(description="Village, town or locality names only. Never people.")
    place_role: Literal["incident", "residence", "unclear"]
    water_body: str | None = Field(description="River, stream, nullah or khwar named, else null")
    deaths: int | None
    injured: int | None
    houses_damaged: int | None
    confidence: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_update: bool = Field(description="True if the text continues or updates an earlier report")
    incidents: list[ExtractedIncident]


SYSTEM_PROMPT = """You extract flood incidents from Pakistani disaster situation reports (PDMA Khyber Pakhtunkhwa).
Fill the form exactly. Rules:
- NEVER output a person's name. "[person]" marks removed names. Villages are place names only.
- One incident per distinct event (place, date and type). A list of damaged houses in one place is one incident.
- event_type: flash_flood (flash flood, torrent, nullah/khwar flood, flood water in a stream); flood (river flood, inundation, flood water in fields or houses); cloudburst (only if a cloudburst is mentioned); drowning (drowned in a river, stream, nullah, khwar or flood water; NOT pools, wells, dams or lakes, which are "other"); landslide; roof_collapse (roof, house, room or wall collapse); other.
- event_date: the day it happened. Use a stated date ("On 14-09-2022" means 2022-09-14). "Last night" or "yesterday" means the day before the report date. If no date is given, use the report date.
- tehsil: only if the text names a tehsil (e.g. "Tehsil Matta"), else null.
- place_role: "incident" if the places are where it happened; "residence" if they only appear as where a victim lived ("resident of X"); "unclear" otherwise.
- deaths, injured, houses_damaged: numbers for this incident if stated, else null.
- is_update: true if the text says "in continuation", "update", or refers to an earlier report.
- confidence: how sure you are about type, date and place together (0 to 1)."""


def build_user_prompt(task: Task) -> str:
    row = task.row
    return (
        f"Report date: {task.report_date.isoformat()}\n"
        f"District: {task.district_raw}\n"
        f"Summary table: nature={row.nature!r}, cause={row.cause!r}, deaths={row.deaths}, "
        f"injured={row.injured}, houses_damaged={row.houses_damaged}\n"
        f"Incident text:\n{task.text}"
    )


# ---- Tasks -------------------------------------------------------------------

@dataclass(frozen=True)
class Task:
    dsrid: int
    report_date: dt.date
    district_raw: str
    district_slug: str | None
    row: SummaryRow
    text: str  # redacted

    @property
    def text_hash(self) -> str:
        payload = f"{PROMPT_VERSION}|{self.report_date}|{self.district_raw}|{self.text}"
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @property
    def cache_name(self) -> str:
        slug = self.district_slug or re.sub(r"\W+", "_", self.district_raw.lower())
        return f"{self.dsrid:05d}_{slug}_{self.text_hash}.json"


def categorise(row: SummaryRow, texts: list[str]) -> str:
    blob = f"{row.nature} {row.cause} " + " ".join(texts)
    if FLOOD_LIKE.search(blob):
        return "flood_like"
    if LANDSLIDE.search(blob):
        return "landslide"
    if COLLAPSE.search(row.cause) and WEATHER.search(f"{row.nature} {row.cause}"):
        return "collapse"
    return "unrelated"


def iter_reports(raw_dir: Path, start: int = 0, end: int = 10**9) -> Iterator[ParsedReport]:
    for path in sorted(raw_dir.glob("*.html.gz")):
        dsrid = int(path.name.split(".")[0])
        if start <= dsrid <= end:
            yield load_report(path)


def build_tasks(reports, names: AdminNames) -> tuple[list[Task], Counter]:
    tasks: list[Task] = []
    counts: Counter = Counter()
    for report in reports:
        if report.report_date is None:
            counts["no_date"] += 1
            continue
        for row in report.summary:
            texts = report.details.get(row.district_raw, [])
            group = categorise(row, texts)
            counts[group] += 1
            if group != "flood_like":
                continue
            text = safe_redact(" ".join(texts)) if texts else ""
            assert not has_name_markers(text)
            tasks.append(Task(
                dsrid=report.dsrid, report_date=report.report_date,
                district_raw=row.district_raw,
                district_slug=names.resolve_district(row.district_raw),
                row=row, text=text or "(no incident text)",
            ))
    return tasks, counts


# ---- Running ------------------------------------------------------------------

def run(tasks: list[Task], cache_dir: Path, service, *, sleep_s: float, limit: int | None) -> Counter:
    cache_dir.mkdir(parents=True, exist_ok=True)
    counts: Counter = Counter()
    done_calls = 0
    for task in tasks:
        path = cache_dir / task.cache_name
        if path.exists():
            counts["cached"] += 1
            continue
        if limit is not None and done_calls >= limit:
            counts["left"] += 1
            continue
        started = time.monotonic()
        try:
            result = service.complete_structured(SYSTEM_PROMPT, build_user_prompt(task), ExtractionResult)
        except Exception as exc:  # keep going; failed tasks are retried next run
            counts["failed"] += 1
            logger.warning("DSRID %d %s failed: %s", task.dsrid, task.district_raw, type(exc).__name__)
            time.sleep(sleep_s * 3)
            continue
        record = {
            "dsrid": task.dsrid,
            "report_date": task.report_date.isoformat(),
            "district_raw": task.district_raw,
            "district_slug": task.district_slug,
            "summary": {"nature": task.row.nature, "cause": task.row.cause, "deaths": task.row.deaths,
                        "injured": task.row.injured, "houses_damaged": task.row.houses_damaged},
            "prompt_version": PROMPT_VERSION,
            "result": result.model_dump(mode="json"),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        counts["extracted"] += 1
        done_calls += 1
        if done_calls % 20 == 0:
            logger.info("Extracted %d (cached %d, failed %d)", counts["extracted"], counts["cached"], counts["failed"])
        wait = sleep_s - (time.monotonic() - started)
        if wait > 0:
            time.sleep(wait)
    return counts


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_pdma_dir)
    parser.add_argument("--cache-dir", type=Path, default=settings.data_dir / "interim" / "pdma_llm")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=10**9)
    parser.add_argument("--limit", type=int, default=None, help="max new LLM calls this run")
    parser.add_argument("--sleep", type=float, default=3.0, help="min seconds per call")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    for noisy in ("httpx", "openai", "langchain"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    names = AdminNames.from_dir(settings.data_dir / "reference")
    tasks, groups = build_tasks(iter_reports(args.raw_dir, args.start, args.end), names)
    cached = sum((args.cache_dir / t.cache_name).exists() for t in tasks)
    logger.info("Rows by group: %s | LLM tasks %d (cached %d, to do %d)",
                dict(groups), len(tasks), cached, len(tasks) - cached)
    if args.dry_run:
        return 0

    from backend.app.llm import LLMService

    service = LLMService.from_settings(settings)
    logger.info("LLM providers: %s", [p.value for p in service.providers])
    counts = run(tasks, args.cache_dir, service, sleep_s=args.sleep, limit=args.limit)
    logger.info("Finished: %s", dict(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
