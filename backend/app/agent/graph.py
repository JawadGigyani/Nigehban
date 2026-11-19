"""The Nigehban agent as a LangGraph state graph.

understand -> locate -> gather -> compose -> validate --ok--> finish
                                     ^            |
                                     +--retry-----+ (up to 2 retries)
                                                  +--fallback (template from evidence)

Rules the graph enforces in code, not by asking the model:
- every cited id must exist in the evidence;
- the risk level the answer states must equal the model's level for that day;
- the closing line ("Follow PDMA and district administration instructions") is
  added by code in the user's language;
- if the model cannot produce a valid answer, a template answer built only from
  the evidence is returned instead.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from backend.app.agent.evidence import LEVEL_WORDS, EvidenceBundle
from backend.app.contracts import Language, RiskLevel

MAX_RETRIES = 2

CLOSING = {
    Language.EN: "Follow PDMA and district administration instructions.",
    Language.UR: "پی ڈی ایم اے اور ضلعی انتظامیہ کی ہدایات پر عمل کریں۔",
    Language.UR_ROMAN: "PDMA aur zilai intezamia ki hidayat par amal karein.",
}
LEVEL_NAMES = {
    Language.EN: {"low": "low", "moderate": "moderate", "high": "high", "very_high": "very high"},
    Language.UR: {"low": "کم", "moderate": "درمیانہ", "high": "زیادہ", "very_high": "بہت زیادہ"},
    Language.UR_ROMAN: {"low": "kam", "moderate": "darmiyana", "high": "zyada", "very_high": "bohat zyada"},
}


# ---- structured outputs ----------------------------------------------------------------------

class Understanding(BaseModel):
    """What the user asked, read by the LLM."""

    intent: Literal["risk", "safety_advice", "shelter_or_help", "general_info", "small_talk", "out_of_scope"]
    language: Literal["en", "ur", "ur_roman"] = Field(
        description="Language of the user's message: ur = Urdu script, ur_roman = Urdu in Latin letters, en = English")
    place: str = Field(description="Village, town or tehsil named in the message, in English spelling; empty if none")
    day: Literal["today", "tomorrow", "day_after", "next_days", "unspecified"]
    search_query: str = Field(description="English keywords to search official flood guidance; empty for small talk")


class AnswerPoint(BaseModel):
    text: str
    refs: list[str]


class AgentAnswer(BaseModel):
    answer: str = Field(description="The reply, 2-6 sentences, in the requested language")
    actions: list[AnswerPoint] = Field(description="0-5 concrete things to do, each with evidence ids")
    refs: list[str] = Field(description="Evidence ids supporting the reply")
    stated_level: Literal["low", "moderate", "high", "very_high", "none"] = Field(
        description="The risk level the reply communicates for the place and day asked about; none if no level")


class AgentState(TypedDict, total=False):
    message: str
    history: list[tuple[str, str]]
    language: str | None  # requested language (overrides detection)
    tehsil_id: str | None
    lat: float | None
    lon: float | None
    as_of: dt.datetime | None
    understanding: Understanding
    located: dict | None
    evidence: EvidenceBundle
    target_day: dt.date | None
    expected_level: RiskLevel | None
    answer: AgentAnswer | None
    errors: list[str]
    attempts: int
    result: dict


# ---- prompts ---------------------------------------------------------------------------------

UNDERSTAND_SYSTEM = """You read messages sent to Nigehban, a flash-flood early-warning service for
northern Khyber Pakhtunkhwa (Swat, Buner, Shangla, Dir, Bajaur, Malakand, Mansehra, Battagram).
Classify the message. Give the place in English spelling (for example "Mingora", "Kalam",
"Bahrain", "Pir Baba"). Write search_query as English keywords for official flood guidance
(for example "livestock evacuation flash flood"). Use the conversation for context."""

ANSWER_SYSTEM = """You are Nigehban, a flash-flood early-warning assistant for northern Khyber Pakhtunkhwa.
Answer ONLY from the evidence given. Rules:
1. Cite evidence ids in `refs` and in each action's `refs`. Never invent an id.
2. Never set, change or soften the risk level. If the evidence has a risk level for the place and
   day asked about, state exactly that level and set `stated_level` to it. If there is no risk
   evidence, do not guess a level: say so and set `stated_level` to "none".
3. Keep it short, calm and practical. Actions must come from the evidence (official guidance,
   shelters, higher ground, Rescue 1122). Shelter and Rescue 1122 locations are unverified: say so.
4. Write `answer` and action texts in {language_name}. Keep ids, numbers and place names exact.
5. Do not add a closing line about following instructions; it is added automatically.
6. If the question is outside floods and safety, say briefly what you can help with."""

LANGUAGE_NAMES = {Language.EN: "English", Language.UR: "Urdu (Nastaliq script)",
                  Language.UR_ROMAN: "Roman Urdu (Urdu written in Latin letters)"}


def _history_text(history: list[tuple[str, str]]) -> str:
    return "\n".join(f"{role}: {text}" for role, text in history[-6:]) or "(none)"


# ---- graph -----------------------------------------------------------------------------------

def build_graph(llm, context) -> Any:
    """`llm` has complete_structured(system, user, model); `context` is an AgentContext."""

    def understand(state: AgentState) -> AgentState:
        user = f"Conversation so far:\n{_history_text(state.get('history', []))}\n\nMessage: {state['message']}"
        u = llm.complete_structured(UNDERSTAND_SYSTEM, user, Understanding)
        u = u.model_copy(update={"language": detect_script(state["message"], u.language)})
        return {"understanding": u, "attempts": 0, "errors": []}

    def locate(state: AgentState) -> AgentState:
        u = state["understanding"]
        bundle = EvidenceBundle()
        found = context.locate(u.place, state.get("tehsil_id"), state.get("lat"), state.get("lon"))
        if found is not None:
            bundle.tehsil_id, bundle.place_name = found["tehsil_id"], found["name"]
        return {"evidence": bundle, "located": found}

    def gather(state: AgentState) -> AgentState:
        u = state["understanding"]
        bundle: EvidenceBundle = state["evidence"]
        expected, target = None, None
        if u.intent not in ("small_talk", "out_of_scope"):
            context.add_evidence(bundle, state.get("located") or {}, u, state.get("as_of"))
            target = context.target_day(u.day, state.get("as_of"))
            if bundle.levels:
                if target in bundle.levels:
                    expected = bundle.levels[target]
                else:  # "next days" / unspecified: the highest level in the window
                    expected = max(bundle.levels.values(), key=lambda lv: lv.rank)
        return {"evidence": bundle, "target_day": target, "expected_level": expected}

    def compose(state: AgentState) -> AgentState:
        lang = _language(state)
        u = state["understanding"]
        bundle: EvidenceBundle = state["evidence"]
        expected = state.get("expected_level")
        focus = ""
        if expected is not None:
            focus = (f"\nThe model's level for the day asked about is {LEVEL_WORDS[expected]} "
                     f"(stated_level must be \"{expected.value}\"). In the reply, write the level as "
                     f"\"{LEVEL_NAMES[lang][expected.value]}\".")
        if u.intent in ("small_talk", "out_of_scope"):
            focus += ("\nReply in one or two friendly sentences: you are Nigehban, you give flash-flood risk "
                      "for tehsils in northern KP for today and the next 3 days, safety advice from PDMA and "
                      "NDMA guidance, and nearby shelters and Rescue 1122. Ask which place they want to check.")
        feedback = ""
        if state.get("errors"):
            feedback = "\nYour previous answer was rejected: " + "; ".join(state["errors"]) + ". Fix this."
        user = (f"Conversation so far:\n{_history_text(state.get('history', []))}\n\n"
                f"User message: {state['message']}\nIntent: {u.intent}. Place: {bundle.place_name or u.place or 'none'}."
                f"{focus}\n\nEvidence:\n{bundle.render()}{feedback}")
        answer = llm.complete_structured(ANSWER_SYSTEM.format(language_name=LANGUAGE_NAMES[lang]), user, AgentAnswer)
        return {"answer": answer, "attempts": state.get("attempts", 0) + 1}

    def validate(state: AgentState) -> AgentState:
        return {"errors": validate_answer(state["answer"], state["evidence"], state.get("expected_level"),
                                          state["understanding"].intent)}

    def route(state: AgentState) -> str:
        if not state["errors"]:
            return "finish"
        return "compose" if state["attempts"] <= MAX_RETRIES else "fallback"

    def finish(state: AgentState) -> AgentState:
        return {"result": _result(state, state["answer"], fallback=False)}

    def fallback(state: AgentState) -> AgentState:
        return {"result": _result(state, template_answer(state["evidence"], state.get("expected_level"),
                                                         _language(state)), fallback=True)}

    graph = StateGraph(AgentState)
    for name, fn in [("understand", understand), ("locate", locate), ("gather", gather), ("compose", compose),
                     ("validate", validate), ("finish", finish), ("fallback", fallback)]:
        graph.add_node(name, fn)
    graph.set_entry_point("understand")
    graph.add_edge("understand", "locate")
    graph.add_edge("locate", "gather")
    graph.add_edge("gather", "compose")
    graph.add_edge("compose", "validate")
    graph.add_conditional_edges("validate", route, {"finish": "finish", "compose": "compose", "fallback": "fallback"})
    graph.add_edge("finish", END)
    graph.add_edge("fallback", END)
    return graph.compile()


# ---- validation and fallbacks ----------------------------------------------------------------

def detect_script(message: str, detected: str) -> str:
    """Urdu script in the message means Urdu; Urdu words in Latin letters mean Roman Urdu."""

    if any("؀" <= ch <= "ۿ" for ch in message):
        return "ur"
    return "ur_roman" if detected == "ur" else detected


def validate_answer(answer: AgentAnswer, bundle: EvidenceBundle, expected: RiskLevel | None, intent: str) -> list[str]:
    errors = []
    if not answer.answer.strip():
        errors.append("the reply text is empty")
    allowed = bundle.refs
    cited = set(answer.refs) | {r for a in answer.actions for r in a.refs}
    unknown = sorted(cited - allowed)
    if unknown:
        errors.append(f"cites ids that are not in the evidence: {unknown}")
    if allowed and not cited and intent not in ("small_talk", "out_of_scope"):
        errors.append("no evidence ids cited")
    for a in answer.actions:
        if not a.refs:
            errors.append(f"action without evidence ids: {a.text[:40]!r}")
    if expected is not None and answer.stated_level != expected.value and intent in ("risk", "safety_advice",
                                                                                    "shelter_or_help"):
        errors.append(f"stated level {answer.stated_level!r} differs from the model's level {expected.value!r}")
    if expected is None and answer.stated_level != "none":
        errors.append("states a risk level although there is no risk evidence")
    return errors


def template_answer(bundle: EvidenceBundle, expected: RiskLevel | None, lang: Language) -> AgentAnswer:
    """Answer built only from evidence, used when the LLM output fails validation."""

    names = LEVEL_NAMES[lang]
    place = bundle.place_name or ""
    risk = next((i for i in bundle.items if i.kind == "risk"), None)
    refs = [risk.ref] if risk else []
    if expected is not None:
        text = {Language.EN: f"Flash-flood risk for {place}: {names[expected.value]}.",
                Language.UR: f"{place} کے لیے سیلابی ریلے کا خطرہ: {names[expected.value]}۔",
                Language.UR_ROMAN: f"{place} ke liye selabi raile ka khatra: {names[expected.value]}."}[lang]
    else:
        text = {Language.EN: "I could not prepare a checked answer right now. In an emergency call Rescue 1122.",
                Language.UR: "ابھی تصدیق شدہ جواب تیار نہیں ہو سکا۔ ہنگامی صورت میں ریسکیو 1122 پر کال کریں۔",
                Language.UR_ROMAN: "Abhi tasdeeq shuda jawab tayyar nahi ho saka. Emergency mein Rescue 1122 par call karein."}[lang]
    if "contact:helplines" in bundle.refs:
        refs.append("contact:helplines")
    return AgentAnswer(answer=text, actions=[], refs=refs, stated_level=expected.value if expected else "none")


def _language(state: AgentState) -> Language:
    if state.get("language"):
        return Language(state["language"])
    return Language(state["understanding"].language)


def _result(state: AgentState, answer: AgentAnswer, fallback: bool) -> dict:
    lang = _language(state)
    bundle: EvidenceBundle = state["evidence"]
    by_ref = {i.ref: i for i in bundle.items}
    cited = list(dict.fromkeys([*answer.refs, *(r for a in answer.actions for r in a.refs)]))
    intent = state["understanding"].intent
    text = answer.answer.strip()
    if intent not in ("small_talk", "out_of_scope"):
        text = f"{text}\n\n{CLOSING[lang]}"
    return {
        "answer": text,
        "actions": [{"text": a.text, "refs": a.refs} for a in answer.actions],
        "language": lang.value,
        "intent": intent,
        "tehsil_id": bundle.tehsil_id,
        "place": bundle.place_name,
        "level": state["expected_level"].value if state.get("expected_level") else None,
        "citations": [{"ref": r, "label": by_ref[r].label, "kind": by_ref[r].kind} for r in cited if r in by_ref],
        "checked": not fallback,
        "fallback": fallback,
        "attempts": state.get("attempts", 0),
    }
