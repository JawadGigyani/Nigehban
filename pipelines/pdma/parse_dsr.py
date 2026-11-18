"""Parse a cached PDMA daily situation report into structured rows.

Each report has (checked on 2019, 2021 and 2022 samples):
- a summary table: DISTRICT | NATURE OF INCIDENT | CAUSE OF INCIDENT | deaths
  (male, female, child, total) | injured (male, female, child, total) | cattle |
  houses (fully, partially, total) | schools (...) | others (...);
- an "INCIDENTS DETAIL" table: DISTRICT | DETAIL OF INCIDENT | RESPONSE | SOURCE.

Rows are found by their header text, not by table position. The detail text
contains victims' names; callers must pass it through `redact.redact_names`
before it leaves this machine, and must never store it.
"""

from __future__ import annotations

import datetime as dt
import gzip
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from pipelines.pdma.fetch_dsr import parse_report_date


@dataclass(frozen=True)
class SummaryRow:
    district_raw: str
    nature: str
    cause: str
    deaths: int | None
    injured: int | None
    houses_damaged: int | None  # fully + partially


@dataclass
class ParsedReport:
    dsrid: int
    report_date: dt.date | None
    summary: list[SummaryRow] = field(default_factory=list)
    details: dict[str, list[str]] = field(default_factory=dict)  # district_raw -> texts


def _cells(tr: Tag) -> list[str]:
    return [" ".join(c.get_text(" ", strip=True).split()) for c in tr.find_all(["td", "th"])]


def _int(text: str) -> int | None:
    text = text.strip()
    return int(text) if text.isdigit() else None


def _find_table(soup: BeautifulSoup, first_cells: tuple[str, ...]) -> Tag | None:
    for table in soup.find_all("table"):
        first = table.find("tr")
        if first is None:
            continue
        cells = [c.upper() for c in _cells(first)]
        if tuple(cells[: len(first_cells)]) == first_cells:
            return table
    return None


def parse_summary(table: Tag) -> list[SummaryRow]:
    rows: list[SummaryRow] = []
    for tr in table.find_all("tr"):
        cells = _cells(tr)
        if len(cells) < 15 or not cells[0] or cells[0].upper() in {"DISTRICT", "TOTAL(S)", "TOTAL"}:
            continue
        if _int(cells[3]) is None:  # header sub-rows have no numbers
            continue
        fully, partially = _int(cells[12]), _int(cells[13])
        houses = None if fully is None and partially is None else (fully or 0) + (partially or 0)
        rows.append(SummaryRow(
            district_raw=cells[0], nature=cells[1], cause=cells[2],
            deaths=_int(cells[6]), injured=_int(cells[10]), houses_damaged=houses,
        ))
    return rows


def parse_details(table: Tag) -> dict[str, list[str]]:
    details: dict[str, list[str]] = {}
    for tr in table.find_all("tr")[1:]:
        cells = _cells(tr)
        if len(cells) < 2 or not cells[0] or not cells[1]:
            continue
        details.setdefault(cells[0], []).append(cells[1])
    return details


def parse_report(html: str, dsrid: int) -> ParsedReport:
    soup = BeautifulSoup(html, "lxml")
    report = ParsedReport(dsrid=dsrid, report_date=parse_report_date(html))
    summary = _find_table(soup, ("DISTRICT", "NATURE OF INCIDENT"))
    if summary is not None:
        report.summary = parse_summary(summary)
    detail = _find_table(soup, ("DISTRICT", "DETAIL OF INCIDENT"))
    if detail is not None:
        report.details = parse_details(detail)
    return report


def load_report(path: Path) -> ParsedReport:
    dsrid = int(path.name.split(".")[0])
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return parse_report(fh.read(), dsrid)
