"""Draft advisory for selected tehsils (F11), for officials to edit and issue.

Layout (agreed): title, date, area, risk, actions, sources, "Draft for official review".
- Title, date, area, the risk table (levels per day from the model) and the sources are
  written by code; the LLM cannot change a level.
- The LLM writes only the recommended actions (each with evidence ids) and a short public
  message in Urdu and English. Ids are checked; on failure a template is used.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from backend.app.agent.evidence import (
    HELPLINES,
    EvidenceBundle,
    doc_items,
    exposure_items,
    facility_items,
    risk_items,
    tehsil_name,
)
from backend.app.agent.graph import LEVEL_NAMES
from backend.app.contracts import Language, RiskLevel
from backend.app.geo.urdu import place_ur

FOOTER = "DRAFT FOR OFFICIAL REVIEW. Not an official warning until issued by PDMA KP or the district administration."
MAX_RETRIES = 2


class AdvisoryAction(BaseModel):
    text: str
    refs: list[str]


class AdvisoryDraft(BaseModel):
    actions: list[AdvisoryAction] = Field(description="4-8 concrete actions for officials and residents")
    public_message_en: str = Field(description="1-2 sentences of advice for the public, English, without risk levels")
    public_message_ur: str = Field(description="The same advice in Urdu (Nastaliq), without risk levels")


SYSTEM = """You draft flash-flood advisories for PDMA Khyber Pakhtunkhwa and district administrations.
Use ONLY the evidence. Write concrete actions for officials (Rescue 1122 readiness, closing riverside
tourist spots, clearing nullahs, preparing shelters) and for residents (move to higher ground, keep away
from streams, move livestock), each citing evidence ids. Shelter and Rescue 1122 locations are unverified.
Do not state or change risk levels anywhere (no "low", "moderate", "high", "very high"): the risk table
and the risk sentence are added by code. Actions and public_message_en are in English with English place
names; use the Urdu place names given only in public_message_ur. No exaggeration: the model gives a raised
chance, never a certainty, so never write that floods are "expected", "certain" or "will" happen."""

CERTAINTY_WORDS = ("expected", "certain", "will occur", "will hit", "will strike", "imminent", "guaranteed")

LEVEL_WORDS_EN = ("low", "moderate", "high", "very high")
LEVEL_WORDS_UR = ("درمیانہ", "زیادہ", "بہت زیادہ")


def risk_sentences(risk_rows: list[dict]) -> tuple[str, str]:
    """Code-written level sentence (the higher of today and tomorrow) in English and Urdu."""

    parts_en, parts_ur = [], []
    for row in risk_rows:
        near = [d for d in row["days"] if d["lead_days"] <= 1] or row["days"][:1]
        top = max(near, key=lambda d: RiskLevel(d["level"]).rank)["level"]
        name = row["tehsil"].split(" (")[0].replace(" tehsil", "")
        parts_en.append(f"{name}: {LEVEL_NAMES[Language.EN][top]}")
        parts_ur.append(f"{(row['tehsil_ur'] or name).split('،')[0]}: {LEVEL_NAMES[Language.UR][top]}")
    return ("Flash-flood risk for today and tomorrow: " + "; ".join(parts_en) + ".",
            "آج اور کل سیلابی ریلے کا خطرہ: " + "؛ ".join(parts_ur) + "۔")


def check_public_message(draft, risk_rows: list[dict]) -> list[str]:
    errors = []
    lowered = f" {draft.public_message_en.lower()} "
    for w in LEVEL_WORDS_EN:
        if any(f" {w}{end}" in lowered for end in (" ", ",", ".", ";")):
            errors.append("the public message must not state risk levels")
            break
    if any(w in draft.public_message_ur for w in LEVEL_WORDS_UR):
        errors.append("the Urdu public message must not state risk levels")
    for row in risk_rows:
        en_name = row["tehsil"].split(" (")[0].replace(" tehsil", "")
        t_ur = (row["tehsil_ur"] or "").split("،")[0]
        if t_ur and en_name.lower() in lowered and t_ur not in draft.public_message_ur:
            errors.append(f"in Urdu write {en_name} exactly as {t_ur}")
    return errors


def compose_advisory(llm, context, forecasts_by_tehsil: dict[str, list], issue: dt.date) -> dict:
    bundle = EvidenceBundle()
    risk_rows = []
    for tehsil_id, forecasts in forecasts_by_tehsil.items():
        for item in risk_items(forecasts):
            bundle.add(item)
        for item in exposure_items(context.villages, tehsil_id, None):
            bundle.add(item)
        t = context.tehsils[tehsil_id]
        for item in facility_items(context.facilities, tehsil_id, t["lat"], t["lon"])[:3]:
            bundle.add(item)
        risk_rows.append({"tehsil_id": tehsil_id, "tehsil": tehsil_name(tehsil_id), "tehsil_ur": place_ur(tehsil_id),
                          "days": [{"date": str(f.valid_date), "lead_days": f.lead_days, "level": f.level.value,
                                    "river_flag": f.glofas_flag} for f in sorted(forecasts, key=lambda f: f.lead_days)]})
    if context.kb is not None:
        for q in ("flash flood evacuation tourists riverside", "livestock higher ground streams nullah",
                  "district emergency operation centre rescue preparedness"):
            for item in doc_items(context.kb.search(q, k=2)):
                bundle.add(item)
    bundle.add(HELPLINES)

    draft, checked, errors = None, False, []
    for _ in range(MAX_RETRIES + 1):
        names_ur = ", ".join(f"{r['tehsil'].split(' (')[0]} = {r['tehsil_ur']}" for r in risk_rows if r["tehsil_ur"])
        user = (f"Tehsils: {', '.join(r['tehsil'] for r in risk_rows)}. Issued {issue:%d %B %Y}.\n"
                f"Urdu names to use exactly: {names_ur}.\n\nEvidence:\n{bundle.render()}")
        if errors:
            user += "\n\nYour previous draft was rejected: " + "; ".join(errors) + ". Fix this."
        try:
            draft = llm.complete_structured(SYSTEM, user, AdvisoryDraft)
        except Exception as exc:  # LLM down: template actions
            errors = [exc.__class__.__name__]
            draft = None
            break
        errors = []
        unknown = sorted({r for a in draft.actions for r in a.refs} - bundle.refs)
        if unknown:
            errors.append(f"cites ids not in the evidence: {unknown}")
        if any(not a.refs for a in draft.actions):
            errors.append("every action needs evidence ids")
        if not draft.actions or not draft.public_message_en.strip() or not draft.public_message_ur.strip():
            errors.append("actions and both public messages are required")
        errors += check_public_message(draft, risk_rows)
        text_en = " ".join([draft.public_message_en, *(a.text for a in draft.actions)]).lower()
        if any(w in text_en for w in CERTAINTY_WORDS):
            errors.append("do not present floods as certain or expected; say the risk is raised")
        if any(any("؀" <= ch <= "ۿ" for ch in a.text) for a in draft.actions) or \
                any("؀" <= ch <= "ۿ" for ch in draft.public_message_en):
            errors.append("actions and the English message must use English place names (no Urdu script)")
        if not errors:
            checked = True
            break
    if not checked:
        draft = AdvisoryDraft(
            actions=[AdvisoryAction(text="Residents near streams and nullahs should move to higher ground if water "
                                         "rises; keep livestock away from rivers.", refs=["contact:helplines"]),
                     AdvisoryAction(text="Rescue 1122 and district teams to stay on standby for the tehsils listed.",
                                    refs=["contact:helplines"])],
            public_message_en="Stay away from streams and nullahs, move to higher ground if water rises, "
                              "and call 1122 in an emergency.",
            public_message_ur="ندی نالوں سے دور رہیں، پانی بڑھے تو اونچی جگہ پر چلے جائیں اور ہنگامی صورت میں "
                              "1122 پر کال کریں۔")

    risk_en, risk_ur = risk_sentences(risk_rows)
    draft = draft.model_copy(update={"public_message_en": f"{risk_en} {draft.public_message_en.strip()}",
                                     "public_message_ur": f"{risk_ur} {draft.public_message_ur.strip()}"})
    by_ref = {i.ref: i for i in bundle.items}
    cited = list(dict.fromkeys(r for a in draft.actions for r in a.refs))
    risk_refs = [i.ref for i in bundle.items if i.kind == "risk"]
    sources = sorted({by_ref[r].label for r in [*risk_refs, *cited] if r in by_ref})
    worst = max((d["level"] for row in risk_rows for d in row["days"]), key=lambda lv: RiskLevel(lv).rank,
                default="low")
    title = f"Flash-flood advisory: {LEVEL_NAMES[Language.EN][worst].title()} risk, " + \
            ", ".join(r["tehsil"].split(" (")[0] for r in risk_rows[:4]) + (" and others" if len(risk_rows) > 4 else "")
    markdown = _markdown(title, issue, risk_rows, draft, sources)
    return {"title": title, "date": str(issue), "area": [r["tehsil"] for r in risk_rows], "risk": risk_rows,
            "actions": [a.model_dump() for a in draft.actions], "public_message_en": draft.public_message_en,
            "public_message_ur": draft.public_message_ur, "sources": sources, "footer": FOOTER,
            "checked": checked, "markdown": markdown}


def _markdown(title, issue, rows, draft, sources) -> str:
    head = "| Tehsil | " + " | ".join(f"{dt.date.fromisoformat(d['date']):%a %d %b}" for d in rows[0]["days"]) + " |"
    sep = "|---|" + "---|" * len(rows[0]["days"])
    body = "\n".join(f"| {r['tehsil']} | " + " | ".join(
        LEVEL_NAMES[Language.EN][d["level"]] + (" (river)" if d["river_flag"] else "") for d in r["days"]) + " |"
                     for r in rows)
    actions = "\n".join(f"{i}. {a.text}" for i, a in enumerate(draft.actions, start=1))
    return (f"# {title}\n\n**Date:** {issue:%d %B %Y}\n\n**Area:** {', '.join(r['tehsil'] for r in rows)}\n\n"
            f"## Risk (Nigehban risk model)\n\n{head}\n{sep}\n{body}\n\n## Recommended actions\n\n{actions}\n\n"
            f"## Message for the public\n\n{draft.public_message_en}\n\n{draft.public_message_ur}\n\n"
            f"## Sources\n\n" + "\n".join(f"- {s}" for s in sources) + f"\n\n---\n**{FOOTER}**\n")
