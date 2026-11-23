"""Ask the live agent a fixed set of questions and write reports/agent_samples.md.

    python -m pipelines.agent.sample_answers
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from backend.app.agent.service import get_agent

PKT = dt.timezone(dt.timedelta(hours=5))
REPLAY = dt.datetime(2025, 8, 14, 9, tzinfo=PKT)  # the day before the Buner cloudburst
QUESTIONS = [
    ("کل پیر بابا میں سیلاب کا کتنا خطرہ ہے؟", REPLAY),
    ("Is there a safe place near Mingora if the river rises tomorrow?", REPLAY),
    ("Kalam mein mavishi ka kya karein agar selab aaye?", REPLAY),
    ("Is tap water safe to drink after a flood?", None),
    ("Who won the cricket match yesterday?", None),
]


def main() -> int:
    agent = get_agent()
    blocks = []
    for question, as_of in QUESTIONS:
        started = time.time()
        r = agent.ask(question, as_of=as_of)
        cites = "\n".join(f"  - `{c['ref']}`: {c['label']}" for c in r["citations"]) or "  - none"
        actions = "\n".join(f"  - {a['text']}" for a in r["actions"]) or "  - none"
        blocks.append(
            f"### {question}\n\n"
            f"Replay as of: {as_of:%d %b %Y %H:%M} PKT\n\n" if as_of else f"### {question}\n\nLive\n\n")
        blocks[-1] += (
            f"- Language: {r['language']} · intent: {r['intent']} · place: {r['place'] or 'none'}\n"
            f"- Level (from the model): {r['level'] or 'none'} · passed checks: {r['checked']} "
            f"(attempts {r['attempts']}, fallback {r['fallback']}) · {time.time() - started:.1f} s\n\n"
            f"**Answer**\n\n{r['answer']}\n\n**Actions**\n\n{actions}\n\n**Citations**\n\n{cites}\n")
    text = f"""# M8 agent: sample answers

Generated {dt.date.today()} by `python -m pipelines.agent.sample_answers` (live LLM, Groq with key and
model rotation; Gemini as fallback).

## How the agent works

LangGraph flow: understand (intent, language, place, day, English search query) → locate (gazetteer,
manual places, tehsil names, or the user's tehsil / location) → gather evidence → compose → validate.

Evidence items each have an id: `risk:` (model level per day and its reasons), `exposure:` (terrain bands),
`facility:` (nearest shelters, higher ground, Rescue 1122, health; unverified), `doc:` (passages from PDMA,
NDMA and NIH guidance), `contact:helplines`.

Checks in code, not left to the model:
- every cited id must exist in the evidence; actions need at least one id;
- the level stated must equal the model's level for the day asked about; with no risk evidence, no level;
- up to 2 retries with the reason for rejection; then a template answer built only from the evidence;
- the closing line "Follow PDMA and district administration instructions" is added in the user's language;
- Urdu script in the message means an Urdu reply; Urdu in Latin letters means Roman Urdu.

Knowledge base: {sum(1 for _ in agent.graph.get_graph().nodes)} graph nodes; passages from 6 official documents,
BM25 search (no embedding API), name lists from committee pages removed.

## Samples

""" + "\n".join(blocks)
    Path("reports/agent_samples.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
