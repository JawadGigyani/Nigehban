"""Match place names as PDMA, the census and maps spell them.

Names arrive in many spellings ("Bala Kot", "Balakot", "Dir Upper",
"Upper Dir", "Khwaza Khela"). `name_key` reduces a name to a comparison key;
`AdminNames` resolves district and tehsil names through the alias tables in
`data/reference/` with an exact key match first and a fuzzy match second. An
alias can point to more than one tehsil (a census unit that covers two COD-AB
tehsils), so tehsil lookups return a list.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

# Words that describe the unit rather than name it.
_GENERIC = {
    "tehsil", "teh", "district", "distt", "dist", "subdivision", "sub", "division",
    "city", "town", "village", "vil", "area", "the", "of",
}
_PUNCT = re.compile(r"[^a-z0-9\s]")


def name_key(name: str) -> str:
    """Comparison key: ASCII, lowercase, no punctuation, spaces or generic words.

    'Bala Kot', 'Balakot' and 'Balakot Tehsil' give the same key. Word order is
    kept, so reordered names ('Dir Upper') need an alias row.
    """

    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = text.replace("(u)", " upper ").replace("(l)", " lower ")
    text = _PUNCT.sub(" ", text)
    tokens = [t for t in text.split() if t not in _GENERIC]
    return "".join(tokens)


@dataclass(frozen=True)
class TehsilMatch:
    tehsil_id: str
    district_slug: str
    score: float  # 100 = exact key match
    method: str  # "exact" | "fuzzy"
    source: str  # alias source, e.g. "cod", "census2023_split", "manual"


class AdminNames:
    """District and tehsil name resolver backed by the alias CSV files."""

    def __init__(
        self,
        district_aliases: list[tuple[str, str]],
        tehsil_aliases: list[tuple[str, str, str, str]],
        *,
        fuzzy_cutoff: float = 88.0,
    ) -> None:
        self.fuzzy_cutoff = fuzzy_cutoff
        self._districts: dict[str, str] = {}
        for alias, slug in district_aliases:
            self._districts.setdefault(name_key(alias), slug)
        # key -> list of (tehsil_id, district_slug, source)
        self._tehsils: dict[str, list[tuple[str, str, str]]] = {}
        for alias, district_slug, tehsil_id, source in tehsil_aliases:
            if not tehsil_id:
                continue
            entries = self._tehsils.setdefault(name_key(alias), [])
            if all(e[0] != tehsil_id for e in entries):
                entries.append((tehsil_id, district_slug, source))

    @classmethod
    def from_dir(cls, reference_dir: Path, **kwargs) -> AdminNames:
        with (reference_dir / "district_aliases.csv").open(encoding="utf-8") as fh:
            districts = [(r["alias"], r["district_slug"]) for r in csv.DictReader(fh)]
        tehsils: list[tuple[str, str, str, str]] = []
        for file in ("tehsil_aliases.csv", "manual_aliases.csv"):
            path = reference_dir / file
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r.get("level", "tehsil") != "tehsil":
                        continue
                    tehsils.append(
                        (r["alias"], r["district_slug"], r["tehsil_id"], r.get("source", file))
                    )
        return cls(districts, tehsils, **kwargs)

    def resolve_district(self, name: str) -> str | None:
        key = name_key(name)
        if not key:
            return None
        if key in self._districts:
            return self._districts[key]
        best = process.extractOne(key, self._districts.keys(), scorer=fuzz.ratio)
        if best and best[1] >= self.fuzzy_cutoff:
            return self._districts[best[0]]
        return None

    def resolve_tehsil(self, name: str, district_slug: str | None = None) -> list[TehsilMatch]:
        """All plausible tehsils for a name, best first. Empty if nothing is close."""

        key = name_key(name)
        if not key:
            return []

        def allowed(entry: tuple[str, str, str]) -> bool:
            return district_slug is None or entry[1] == district_slug

        exact = [e for e in self._tehsils.get(key, []) if allowed(e)]
        if exact:
            return [TehsilMatch(e[0], e[1], 100.0, "exact", e[2]) for e in exact]

        candidates = {k: v for k, v in self._tehsils.items() if any(allowed(e) for e in v)}
        matches: list[TehsilMatch] = []
        for found_key, score, _ in process.extract(
            key, candidates.keys(), scorer=fuzz.ratio, limit=5, score_cutoff=self.fuzzy_cutoff
        ):
            for e in candidates[found_key]:
                if allowed(e) and all(m.tehsil_id != e[0] for m in matches):
                    matches.append(TehsilMatch(e[0], e[1], float(score), "fuzzy", e[2]))
        return matches
