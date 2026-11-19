"""Extract passages from the guidance PDFs into backend/app/knowledge/index/passages.jsonl.gz.

    python -m pipelines.knowledge.build_index
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter

from pypdf import PdfReader

from backend.app.config import get_settings
from backend.app.knowledge.store import DOCUMENTS, INDEX_PATH, split_page

MIN_PAGE_CHARS = 200  # skip covers, blank and table-of-contents-like pages
_NAME_LIST = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Brig|Col|Maj|Engr)\.?\s*[A-Z]")


def is_name_list(text: str) -> bool:
    """Committee and contributor lists: not guidance, and full of people's names."""

    return len(_NAME_LIST.findall(text)) >= 3


def pages(path):
    if path.suffix == ".txt":
        yield 1, path.read_text(encoding="utf-8")
        return
    for page_no, page in enumerate(PdfReader(str(path)).pages, start=1):
        try:
            yield page_no, page.extract_text() or ""
        except Exception:  # damaged page: skip it
            continue


def main() -> int:
    raw = get_settings().data_dir / "raw" / "knowledge"
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter = Counter()
    with gzip.open(INDEX_PATH, "wt", encoding="utf-8") as out:
        for slug, (file_name, *_rest) in DOCUMENTS.items():
            path = raw / file_name
            if not path.is_file():
                print(f"missing {path}")
                continue
            for page_no, text in pages(path):
                if len(text.strip()) < MIN_PAGE_CHARS or text.count(".....") > 5:
                    continue
                for n, chunk in enumerate(split_page(text), start=1):
                    if is_name_list(chunk):
                        counts["skipped_name_lists"] += 1
                        continue
                    out.write(json.dumps({"ref": f"doc:{slug}:p{page_no}#{n}", "doc": slug,
                                          "page": page_no, "text": chunk}, ensure_ascii=False) + "\n")
                    counts[slug] += 1
    print(dict(counts), f"-> {INDEX_PATH} ({INDEX_PATH.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
