"""M8 agent: grounding checks, retries, fallback, language, place lookup, knowledge search, API."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.agent.graph import AgentAnswer, AnswerPoint, Understanding, detect_script
from backend.app.agent.service import AgentContext, ChatAgent, load_context
from backend.app.contracts import RiskDriver, RiskLevel, TehsilRiskForecast
from backend.app.contracts.enums import HydrometModel
from backend.app.knowledge import KnowledgeBase

ROOT = Path(__file__).resolve().parents[1]
PKT = dt.timezone(dt.timedelta(hours=5))
AS_OF = dt.datetime(2025, 8, 14, 9, tzinfo=PKT)


class FakeLLM:
    """Returns queued outputs per schema, in order."""

    def __init__(self, understanding: Understanding, answers: list[AgentAnswer]) -> None:
        self.understanding, self.answers, self.calls = understanding, list(answers), []

    def complete_structured(self, system: str, user: str, model):
        self.calls.append((model.__name__, user))
        if model is Understanding:
            return self.understanding
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


class FakeRisk:
    locator = None

    def forecast(self, issue, replay=False):
        out = []
        for lead, level in enumerate([RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.MODERATE, RiskLevel.LOW]):
            out.append(TehsilRiskForecast(
                tehsil_id="buner__gagra", issued_at=dt.datetime.combine(issue, dt.time(0), PKT),
                valid_date=issue + dt.timedelta(days=lead), lead_days=lead, probability=0.01, level=level,
                drivers=(RiskDriver(feature="precip_cell_max", value=61.0, contribution=1.2),),
                models_used=(HydrometModel.ECMWF, HydrometModel.GFS)))
        return out


def _context() -> AgentContext:
    gazetteer = pd.DataFrame([{"place_id": "manual:pir_baba", "name": "Pir Baba", "alt_names": "Pacha Kalay",
                               "name_ur": "پیر بابا", "feature": "town", "lat": 34.4527, "lon": 72.556,
                               "district_slug": "buner", "tehsil_id": "buner__gagra", "population": None},
                              {"place_id": "osm:1", "name": "Bab", "alt_names": "", "name_ur": "", "feature": "village",
                               "lat": 34.8, "lon": 73.0, "district_slug": "battagram", "tehsil_id": "battagram__allai",
                               "population": None}])
    villages = pd.DataFrame([{"village_id": "manual:pir_baba", "name": "Pir Baba", "tehsil_id": "buner__gagra",
                              "lat": 34.4527, "lon": 72.556, "hand_m": 4.0, "hand_min_m": 0.0,
                              "exposure_band": "high", "dist_to_stream_m": 90, "upstream_area_km2": 120.0}])
    facilities = pd.DataFrame([{"facility_id": "osm:n9", "kind": "shelter", "subtype": "school", "shelter_priority": 1,
                                "name": "Govt High School", "name_ur": "", "lat": 34.46, "lon": 72.56,
                                "tehsil_id": "buner__gagra", "hand_min_m": 20.0, "exposure_band": "low",
                                "verified": False, "source": "osm"}])
    tehsils = {"buner__gagra": {"lat": 34.45, "lon": 72.55, "in_scope": True},
               "battagram__allai": {"lat": 34.8, "lon": 73.0, "in_scope": True}}
    kb = KnowledgeBase.load()
    return AgentContext(FakeRisk(), kb, gazetteer, villages, facilities, tehsils)


UNDERSTOOD = Understanding(intent="risk", language="ur", place="Pir Baba", day="tomorrow",
                           search_query="flash flood higher ground")
GOOD = AgentAnswer(answer="کل پیر بابا میں خطرہ زیادہ ہے۔", actions=[
    AnswerPoint(text="اونچی جگہ پر جائیں", refs=["doc:pdma_flood_dos_donts:p1#1"])],
    refs=["risk:buner__gagra:2025-08-15"], stated_level="high")


def test_grounded_answer_passes_with_closing_line_and_model_level():
    llm = FakeLLM(UNDERSTOOD, [GOOD])
    r = ChatAgent(llm, _context()).ask("کل پیر بابا میں سیلاب کا خطرہ؟", as_of=AS_OF)
    assert r["checked"] and not r["fallback"] and r["attempts"] == 1
    assert r["level"] == "high" and r["tehsil_id"] == "buner__gagra"
    assert r["answer"].endswith("پی ڈی ایم اے اور ضلعی انتظامیہ کی ہدایات پر عمل کریں۔")
    assert {c["ref"] for c in r["citations"]} == {"risk:buner__gagra:2025-08-15", "doc:pdma_flood_dos_donts:p1#1"}


def test_made_up_citation_is_rejected_then_retried():
    bad = GOOD.model_copy(update={"refs": ["doc:invented:p99#1"]})
    llm = FakeLLM(UNDERSTOOD, [bad, GOOD])
    r = ChatAgent(llm, _context()).ask("کل پیر بابا میں سیلاب کا خطرہ؟", as_of=AS_OF)
    assert r["checked"] and r["attempts"] == 2
    assert "rejected" in llm.calls[-1][1] and "doc:invented:p99#1" in llm.calls[-1][1]


def test_wrong_level_never_reaches_the_user():
    softened = GOOD.model_copy(update={"stated_level": "low"})
    llm = FakeLLM(UNDERSTOOD, [softened])
    r = ChatAgent(llm, _context()).ask("کل پیر بابا میں سیلاب کا خطرہ؟", as_of=AS_OF)
    assert r["fallback"] and not r["checked"] and r["attempts"] == 3
    assert r["level"] == "high" and "زیادہ" in r["answer"]  # template states the model's level


def test_no_risk_evidence_means_no_level():
    u = Understanding(intent="safety_advice", language="en", place="", day="unspecified",
                      search_query="drinking water after flood")
    guess = AgentAnswer(answer="Risk is high.", actions=[], refs=["contact:helplines"], stated_level="high")
    honest = AgentAnswer(answer="Boil water before drinking.", actions=[], refs=["contact:helplines"],
                         stated_level="none")
    r = ChatAgent(FakeLLM(u, [guess, honest]), _context()).ask("Is the water safe after a flood?")
    assert r["checked"] and r["level"] is None and r["attempts"] == 2


def test_detect_script():
    assert detect_script("کل پیر بابا", "en") == "ur"
    assert detect_script("Kalam mein selab", "ur") == "ur_roman"
    assert detect_script("Is it safe?", "en") == "en"


def test_place_lookup_is_strict_and_knows_manual_places():
    ctx = _context()
    assert ctx.locate("Pir Baba", None, None, None)["tehsil_id"] == "buner__gagra"
    assert ctx.locate("پیر بابا", None, None, None)["tehsil_id"] == "buner__gagra"
    assert ctx.locate("Pacha Kalay", None, None, None)["village_id"] == "manual:pir_baba"
    assert ctx.locate("Pir Bab Kot", None, None, None) is None  # no loose partial match to "Bab"
    assert ctx.locate("", "buner__gagra", None, None)["tehsil_id"] == "buner__gagra"


def test_knowledge_search_finds_practical_guidance():
    kb = KnowledgeBase.load()
    hits = kb.search("flash flood move to higher ground", k=3)
    assert hits and hits[0].doc == "pdma_flood_dos_donts"
    assert all(not ("Mr." in p.text and p.text.count("Mr.") >= 3) for p in kb.passages)


def test_real_context_loads():
    ctx = load_context(ROOT / "data")
    assert ctx.locate("Mingora", None, None, None)["tehsil_id"] == "swat__babuzai"
    assert ctx.locate("Pir Baba", None, None, None)["tehsil_id"] == "buner__gagra"


def test_chat_api(monkeypatch):
    from backend.app.api import chat as chat_api
    from backend.app.main import create_app

    monkeypatch.setattr(chat_api, "get_agent", lambda: ChatAgent(FakeLLM(UNDERSTOOD, [GOOD]), _context()))
    client = TestClient(create_app())
    r = client.post("/chat", json={"message": "کل پیر بابا میں سیلاب کا خطرہ؟", "as_of": AS_OF.isoformat()})
    assert r.status_code == 200
    body = r.json()
    assert body["level"] == "high" and body["language"] == "ur" and body["checked"]
    assert body["session_id"]


@pytest.mark.live
@pytest.mark.skipif(os.getenv("NIGEHBAN_RUN_LIVE") != "1", reason="live LLM test (set NIGEHBAN_RUN_LIVE=1)")
def test_live_urdu_golden():
    from backend.app.agent.service import get_agent

    r = get_agent().ask("کل پیر بابا میں سیلاب کا کتنا خطرہ ہے؟", as_of=AS_OF)
    assert r["language"] == "ur" and r["tehsil_id"] == "buner__gagra"
    assert r["checked"] and r["level"] in {"moderate", "high", "very_high"}
    assert all(c["ref"].split(":")[0] in {"risk", "doc", "facility", "exposure", "contact", "river"}
               for c in r["citations"])
