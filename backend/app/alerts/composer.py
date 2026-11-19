"""Alert text in Urdu, English and Roman Urdu, written by the LLM from evidence and checked by code.

Checks: cited ids must exist in the evidence; each message must contain the
model's level word in that language; length limits. On failure: up to 2 retries,
then a template built only from the evidence. The closing line is added by code.
"""

from __future__ import annotations

from dataclasses import dataclass

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
from backend.app.agent.graph import CLOSING, LEVEL_NAMES
from backend.app.alerts.rules import AlertCandidate
from backend.app.contracts import Language
from backend.app.geo.urdu import district_ur, place_ur, tehsil_ur

MAX_CHARS = 480
# Urdu district names in scope, plus neighbours the model has confused them with.
DISTRICTS_UR = ("سوات", "بونیر", "شانگلہ", "باجوڑ", "ملاکنڈ", "مانسہرہ", "بٹگرام", "بنوں", "چترال",
                "کوہستان", "مردان", "صوابی", "پشاور")
MAX_RETRIES = 2


class AlertDraft(BaseModel):
    message_ur: str = Field(description="Alert in Urdu (Nastaliq script), 2-4 short sentences")
    message_en: str = Field(description="The same alert in English")
    message_ur_roman: str = Field(description="The same alert in Roman Urdu (Urdu in Latin letters)")
    refs: list[str] = Field(description="Evidence ids the alert is based on")


SYSTEM = """You write short flash-flood alerts for residents of northern Khyber Pakhtunkhwa.
Use ONLY the evidence. Each message: the place, the day, the risk level exactly as given, the main
reason in plain words, and one or two actions from the evidence (move to higher ground, avoid
streams and nullahs, keep livestock away from the river, where to go, call Rescue 1122).
Shelter locations are unverified: say "if safe" or similar. No panic words, no exaggeration.
Plain words only: give rain in mm if useful, but no other technical units or values (say "wet ground",
not soil-moisture numbers).
Do not add a closing line about following instructions; it is added automatically.
Keep each message under 400 characters. Cite evidence ids in `refs`; never invent ids."""


@dataclass
class ComposedAlert:
    message_ur: str
    message_en: str
    message_ur_roman: str
    citations: tuple[str, ...]
    checked: bool


class AlertComposer:
    def __init__(self, llm, context) -> None:
        """`llm` has complete_structured; `context` is an agent AgentContext (data + knowledge)."""

        self.llm = llm
        self.context = context

    def evidence(self, candidate: AlertCandidate) -> EvidenceBundle:
        f = candidate.forecast
        bundle = EvidenceBundle(tehsil_id=f.tehsil_id, place_name=tehsil_name(f.tehsil_id))
        for item in risk_items([f]):
            bundle.add(item)
        for item in exposure_items(self.context.villages, f.tehsil_id, None):
            bundle.add(item)
        t = self.context.tehsils[f.tehsil_id]
        for item in facility_items(self.context.facilities, f.tehsil_id, t["lat"], t["lon"])[:2]:
            bundle.add(item)
        if self.context.kb is not None:
            for item in doc_items(self.context.kb.search("flash flood move to higher ground streams livestock", k=2)):
                bundle.add(item)
        bundle.add(HELPLINES)
        from backend.app.geo.contacts import contact_evidence

        local = contact_evidence(f.tehsil_id)
        if local is not None:
            bundle.add(local)
        return bundle

    def compose(self, candidate: AlertCandidate) -> ComposedAlert:
        f = candidate.forecast
        bundle = self.evidence(candidate)
        level = f.level.value
        errors: list[str] = []
        for _ in range(MAX_RETRIES + 1):
            user = (f"Tehsil: {tehsil_name(f.tehsil_id)}. Day: {f.valid_date:%d %B %Y} "
                    f"({'today' if f.lead_days == 0 else f'in {f.lead_days} day(s)'}).\n"
                    f"Risk level: {level}. Write it as \"{LEVEL_NAMES[Language.UR][level]}\" in Urdu, "
                    f"\"{LEVEL_NAMES[Language.EN][level]}\" in English, "
                    f"\"{LEVEL_NAMES[Language.UR_ROMAN][level]}\" in Roman Urdu.\n"
                    + (f"In Urdu, write the place exactly as \"{place_ur(f.tehsil_id)}\" (do not transliterate "
                       f"it yourself).\n" if place_ur(f.tehsil_id) else "")
                    +
                    f"Reasons for alerting: {', '.join(candidate.reason_codes)}.\n\nEvidence:\n{bundle.render()}")
            if errors:
                user += "\n\nYour previous draft was rejected: " + "; ".join(errors) + ". Fix this."
            try:
                draft = self.llm.complete_structured(SYSTEM, user, AlertDraft)
            except Exception as exc:  # LLM down: the template still goes out
                errors = [f"LLM error: {exc.__class__.__name__}"]
                break
            errors = check_draft(draft, bundle, level, f.tehsil_id)
            if not errors:
                return ComposedAlert(_close(draft.message_ur, Language.UR), _close(draft.message_en, Language.EN),
                                     _close(draft.message_ur_roman, Language.UR_ROMAN),
                                     tuple(dict.fromkeys(draft.refs)), True)
        return template(candidate, bundle)


def check_draft(draft: AlertDraft, bundle: EvidenceBundle, level: str, tehsil_id: str | None = None) -> list[str]:
    errors = []
    if tehsil_id and tehsil_ur(tehsil_id):
        if tehsil_ur(tehsil_id) not in draft.message_ur:
            errors.append(f"the Urdu message must name the tehsil as \"{tehsil_ur(tehsil_id)}\"")
        own = district_ur(tehsil_id) or ""
        wrong = [d for d in DISTRICTS_UR if d in draft.message_ur and d not in own]
        if wrong:
            errors.append(f"the Urdu message names another district: {wrong}")
    unknown = sorted(set(draft.refs) - bundle.refs)
    if unknown:
        errors.append(f"cites ids not in the evidence: {unknown}")
    if not draft.refs:
        errors.append("no evidence ids cited")
    for lang, text in ((Language.UR, draft.message_ur), (Language.EN, draft.message_en),
                       (Language.UR_ROMAN, draft.message_ur_roman)):
        if not text.strip():
            errors.append(f"{lang.value} message is empty")
        elif len(text) > MAX_CHARS:
            errors.append(f"{lang.value} message is longer than {MAX_CHARS} characters")
        elif LEVEL_NAMES[lang][level].lower() not in text.lower():
            errors.append(f"{lang.value} message must state the level as \"{LEVEL_NAMES[lang][level]}\"")
    return errors


def template(candidate: AlertCandidate, bundle: EvidenceBundle) -> ComposedAlert:
    f = candidate.forecast
    level = f.level.value
    place = tehsil_name(f.tehsil_id)
    day = f"{f.valid_date:%d %b}"
    river = " River levels are also unusually high." if f.glofas_flag else ""
    en = (f"Nigehban alert: flash-flood risk is {LEVEL_NAMES[Language.EN][level]} for {place} on {day}.{river} "
          f"Stay away from streams and nullahs, keep livestock away from the river, and move to higher ground "
          f"if water rises. Emergency: call 1122.")
    ur = (f"نگہبان الرٹ: {day} کو {place_ur(f.tehsil_id) or place} میں سیلابی ریلے کا خطرہ {LEVEL_NAMES[Language.UR][level]} ہے۔ "
          f"ندی نالوں سے دور رہیں، مویشیوں کو دریا سے دور رکھیں اور پانی بڑھے تو اونچی جگہ پر چلے جائیں۔ "
          f"ہنگامی صورت میں 1122 پر کال کریں۔")
    roman = (f"Nigehban alert: {day} ko {place} mein selabi raile ka khatra {LEVEL_NAMES[Language.UR_ROMAN][level]} hai. "
             f"Nadi nalon se door rahein, maweshiyon ko darya se door rakhein aur pani barhe to oonchi jagah par "
             f"chale jayein. Emergency mein 1122 par call karein.")
    refs = tuple(i.ref for i in bundle.items if i.kind in ("risk", "contact"))
    return ComposedAlert(_close(ur, Language.UR), _close(en, Language.EN), _close(roman, Language.UR_ROMAN),
                         refs, False)


def _close(text: str, lang: Language) -> str:
    return f"{text.strip()}\n{CLOSING[lang]}"
