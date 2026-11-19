"""Fixed Urdu names for districts and tehsils (data/reference/urdu_names.csv).

The LLM must use these instead of transliterating on its own (it misspelled
tehsils and once named the wrong district). Rows marked `check` still need a
native speaker's confirmation.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parents[3] / "data" / "reference" / "urdu_names.csv"


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    if not PATH.is_file():
        return {}
    with PATH.open(encoding="utf-8-sig", newline="") as fh:  # BOM-tolerant (Excel)
        return {r["id"]: r["name_ur"] for r in csv.DictReader(fh)}


def tehsil_ur(tehsil_id: str) -> str | None:
    return _names().get(tehsil_id)


def district_ur(tehsil_id: str) -> str | None:
    return _names().get(tehsil_id.split("__")[0])


def place_ur(tehsil_id: str) -> str | None:
    """'گاگرہ، بونیر' (tehsil, district), or None if unknown."""

    t, d = tehsil_ur(tehsil_id), district_ur(tehsil_id)
    if not t:
        return None
    return t if not d or d == t else f"{t}، {d}"
