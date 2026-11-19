"""Rescue 1122 district control rooms (official directory, rescuekp.gov.pk/site/page/10)."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "data" / "reference" / "rescue1122_district_contacts.csv"


@lru_cache(maxsize=1)
def _rows() -> dict[str, dict]:
    if not PATH.is_file():
        return {}
    with PATH.open(encoding="utf-8-sig", newline="") as fh:
        return {r["district_slug"]: r for r in csv.DictReader(fh)}


def district_contact(tehsil_id: str) -> dict | None:
    return _rows().get(tehsil_id.split("__")[0])


def contact_evidence(tehsil_id: str):
    """EvidenceItem with the district's Rescue 1122 control room, or None."""

    from backend.app.agent.evidence import EvidenceItem

    row = district_contact(tehsil_id)
    if row is None:
        return None
    return EvidenceItem(f"contact:rescue1122:{row['district_slug']}", "contact",
                        f"Rescue 1122 {row['district']} control room: {row['control_room']} "
                        f"(district office {row['district_office']}); emergency number 1122.",
                        f"Rescue 1122 KP telephone directory ({row['district']})")
