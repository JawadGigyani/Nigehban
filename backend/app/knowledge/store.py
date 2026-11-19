"""Passages from the guidance PDFs, searched with BM25.

- Build: `python -m pipelines.knowledge.build_index` reads the PDFs in
  data/raw/knowledge/, splits each page into passages of about 900 characters
  (overlapping a little, cut at sentence ends) and writes
  backend/app/knowledge/index/passages.jsonl.gz (public documents, small).
- Search: BM25 over English words. Questions in Urdu are first rewritten into an
  English search query by the agent. No embedding API is needed, it works
  offline and gives the same result every time.
- Citation id: `doc:<slug>:p<page>`; the board and alerts show the title and page.
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from pathlib import Path

INDEX_PATH = Path(__file__).resolve().parent / "index" / "passages.jsonl.gz"

# slug -> (file name, title, publisher, year)
DOCUMENTS: dict[str, tuple[str, str, str, str]] = {
    "pdma_kp_summer_contingency": ("PDMA_KP_Inclusive_Summer_Hazards_Contingency_Plan.pdf",
                                   "Inclusive Summer Hazards Contingency Plan", "PDMA Khyber Pakhtunkhwa", ""),
    "ndmp_main": ("National_Disaster_Management_Plan__NDMP__Main_Volume.pdf",
                  "National Disaster Management Plan, Main Volume", "NDMA Pakistan", ""),
    "ndrr_strategy_2025": ("NDMA_National_Disaster_Risk_Reduction_Strategy_2025-2030.pdf",
                           "National Disaster Risk Reduction Strategy 2025-2030", "NDMA Pakistan", "2025"),
    "swat_risk_mapping": ("Disaster_Risk_Mapping_District_Swat.pdf",
                          "Disaster Risk Mapping, District Swat", "District Swat", ""),
    "pdma_flood_dos_donts": ("pdma_flood_dos_donts.txt", "Flood: Do's and Don'ts",
                             "PDMA (pdma.gov.pk)", ""),
    "nih_flood_guidelines": ("NIH_Guidelines_on_floods.pdf", "Guidelines on Floods (health)",
                             "National Institute of Health, Islamabad", "2022"),
}
# Search weight per document: practical, local guidance first; the national plan is long and
# mostly about institutions, so it is weighted down.
DOC_WEIGHT = {"pdma_flood_dos_donts": 1.6, "nih_flood_guidelines": 1.3, "pdma_kp_summer_contingency": 1.3,
              "swat_risk_mapping": 1.2, "ndrr_strategy_2025": 0.9, "ndmp_main": 0.7}

_STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to was were
will with which these those their there been being into not no can may also such than other more most
all any each per via under over within""".split())
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass(frozen=True)
class Passage:
    ref: str  # doc:<slug>:p<page>#<n>
    doc: str
    page: int
    text: str

    @property
    def title(self) -> str:
        return DOCUMENTS[self.doc][1]

    @property
    def publisher(self) -> str:
        return DOCUMENTS[self.doc][2]

    @property
    def label(self) -> str:
        return f"{self.publisher}, {self.title}, p. {self.page}"


def split_page(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Cut one page into passages of about `size` characters at sentence ends."""

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?;:])\s+", text)
    out, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > size:
            out.append(current.strip())
            current = current[-overlap:] + " " + sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current.strip():
        out.append(current.strip())
    return out


class KnowledgeBase:
    def __init__(self, passages: list[Passage]) -> None:
        from rank_bm25 import BM25Okapi

        self.passages = passages
        self._by_ref = {p.ref: p for p in passages}
        self._bm25 = BM25Okapi([tokenize(p.text) for p in passages]) if passages else None
        import numpy as np

        self._weights = np.array([DOC_WEIGHT.get(p.doc, 1.0) for p in passages])

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> KnowledgeBase:
        if not path.is_file():
            return cls([])
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return cls([Passage(**json.loads(line)) for line in fh])

    def get(self, ref: str) -> Passage | None:
        return self._by_ref.get(ref)

    def search(self, query: str, k: int = 4, min_score: float = 1.0) -> list[Passage]:
        if self._bm25 is None:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens) * self._weights
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        out, seen_pages = [], set()
        for i in order:
            if scores[i] < min_score or len(out) >= k:
                break
            p = self.passages[i]
            if (p.doc, p.page) in seen_pages:  # one passage per page keeps results varied
                continue
            seen_pages.add((p.doc, p.page))
            out.append(p)
        return out
