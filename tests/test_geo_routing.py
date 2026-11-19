"""M10 routing, M11 danger check, F11 advisory: offline tests (real rasters used only if present)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from backend.app.alerts.advisory import AdvisoryAction, AdvisoryDraft, check_public_message, risk_sentences
from backend.app.geo.danger import advice
from backend.app.geo.routing import SafeRouter, build_graph, km

ROOT = Path(__file__).resolve().parents[1]
TERRAIN = ROOT / "data" / "interim" / "terrain"


class FakeTiles:
    """A small grid of paths: a riverside road (low ground) and a longer hill road."""

    def ways_for_bbox(self, *args, **kwargs):
        return [
            {"hw": "path", "pts": [[72.000, 34.000], [72.010, 34.000]]},  # start -> riverside -> shelter
            {"hw": "path", "pts": [[72.000, 34.000], [72.000, 34.006], [72.010, 34.006], [72.010, 34.000]]},  # hill loop
        ]


class FakeLow:
    """Everything on lat 34.000 is low ground (beside the river)."""

    def hand(self, lons, lats):
        import numpy as np

        return np.where(abs(lats - 34.0) < 1e-4, 0.5, 20.0)


FACILITIES = pd.DataFrame([{"facility_id": "osm:1", "kind": "shelter", "subtype": "school", "name": "School",
                            "lat": 34.0, "lon": 72.0105, "exposure_band": "low"},
                           {"facility_id": "osm:2", "kind": "shelter", "subtype": "school", "name": "Riverside",
                            "lat": 34.0, "lon": 72.0012, "exposure_band": "high"}])


def test_graph_penalises_low_ground():
    g = build_graph(FakeTiles().ways_for_bbox(), "walk", FakeLow())
    low_edges = [d for _, _, d in g.edges(data=True) if d["low"]]
    assert low_edges and all(d["cost"] == pytest.approx(d["seconds"] * 5) for d in low_edges)


def test_route_avoids_riverside_and_high_exposure_shelters():
    router = SafeRouter(FakeTiles(), FakeLow(), FACILITIES)
    dests = router.candidates(34.0, 72.0)
    assert [d["id"] for d in dests] == ["osm:1"]  # the high-exposure shelter is never offered
    route = router.route(34.0, 72.0, "walk")
    assert route.destination["id"] == "osm:1"
    assert route.low_ground_share < 0.5  # took the hill loop, not the riverside path
    assert route.distance_m > km(34.0, 72.0, 34.0, 72.0105) * 1000
    assert "unverified" in route.notes[0]


def test_drive_mode_skips_footpaths():
    g = build_graph([{"hw": "footway", "pts": [[72, 34], [72.01, 34]]},
                     {"hw": "secondary", "pts": [[72, 34.01], [72.01, 34.01]]}], "drive", None)
    assert g.number_of_edges() == 1


def test_advice_combines_zone_and_level():
    assert advice(True, "very_high") == "move_away" and advice(True, "high") == "move_away"
    assert advice(True, "moderate") == "be_ready"
    assert advice(True, "low") == "stay_alert" and advice(False, "very_high") == "normal"


ROWS = [{"tehsil_id": "buner__gagra", "tehsil": "Gagra tehsil (Buner district)", "tehsil_ur": "گاگرہ، بونیر",
         "days": [{"date": "2025-08-14", "lead_days": 0, "level": "moderate", "river_flag": False},
                  {"date": "2025-08-15", "lead_days": 1, "level": "high", "river_flag": False}]}]


def test_advisory_risk_sentence_is_written_by_code():
    en, ur = risk_sentences(ROWS)
    assert en == "Flash-flood risk for today and tomorrow: Gagra: high." and "گاگرہ: زیادہ" in ur


def test_advisory_public_message_checks():
    ok = AdvisoryDraft(actions=[AdvisoryAction(text="x", refs=["contact:helplines"])],
                       public_message_en="People in Gagra should move to higher ground.",
                       public_message_ur="گاگرہ کے لوگ اونچی جگہ پر چلے جائیں۔")
    assert check_public_message(ok, ROWS) == []  # "higher" is not a level word
    states_level = ok.model_copy(update={"public_message_en": "Risk in Gagra is very high."})
    assert any("levels" in e for e in check_public_message(states_level, ROWS))
    misspelled = ok.model_copy(update={"public_message_ur": "گگرہ کے لوگ اونچی جگہ پر چلے جائیں۔"})
    assert any("گاگرہ" in e for e in check_public_message(misspelled, ROWS))


@pytest.mark.skipif(not (TERRAIN / "stream_upstream_km2.tif").is_file(), reason="terrain rasters not built")
def test_danger_check_on_real_terrain():
    from backend.app.geo.danger import DangerChecker

    checker = DangerChecker(ROOT / "data", locator=None)
    checker._spots = __import__("numpy").zeros((0, 2))  # no network in tests
    riverside = checker.check(34.7937, 72.3720)  # Mingora bypass, about 90 m from the Swat River
    assert riverside["in_danger_zone"] and riverside["terrain"]["river_upstream_km2"] > 1000
    hill = checker.check(34.7795, 72.3600)  # Mingora town, about 1.6 km from the river
    assert not hill["in_danger_zone"]


@pytest.mark.skipif(not (ROOT / "data" / "cache" / "osm_roads").is_dir(), reason="road tiles not extracted")
def test_geo_api(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.api import geo
    from backend.app.main import create_app
    from tests.test_ui_api import FakeRisk

    class Ctx:
        risk = FakeRisk()
        tehsils = {"buner__gagra": {}}

    monkeypatch.setattr("backend.app.api.risk._context", lambda: Ctx)
    client = TestClient(create_app())
    assert client.post("/advisories/draft", json={"tehsil_ids": ["buner__gagra"]}).status_code == 401
    assert client.post("/geo/check", json={"lat": 10, "lon": 10}).status_code in (422, 500)


def test_advisory_rejects_urdu_script_in_english_actions():
    from backend.app.alerts.advisory import compose_advisory
    from backend.app.contracts import RiskDriver, RiskLevel, TehsilRiskForecast
    from backend.app.contracts.enums import HydrometModel
    from tests.test_agent import _context

    class LLM:
        def __init__(self):
            self.calls = 0

        def complete_structured(self, system, user, model):
            self.calls += 1
            text = "Rescue 1122 to stand by in گاگرہ." if self.calls == 1 else "Rescue 1122 to stand by in Gagra."
            return AdvisoryDraft(actions=[AdvisoryAction(text=text, refs=["contact:helplines"])],
                                 public_message_en="Keep away from streams.",
                                 public_message_ur="ندی نالوں سے دور رہیں۔")

    issue = dt.date(2025, 8, 14)
    f = [TehsilRiskForecast(tehsil_id="buner__gagra", issued_at=dt.datetime(2025, 8, 14), valid_date=issue,
                            lead_days=0, probability=0.02, level=RiskLevel.HIGH,
                            drivers=(RiskDriver(feature="precip_cell_max", value=50, contribution=1),),
                            models_used=(HydrometModel.ECMWF,))]
    llm = LLM()
    out = compose_advisory(llm, _context(), {"buner__gagra": f}, issue)
    assert out["checked"] and llm.calls == 2 and "Gagra" in out["actions"][0]["text"]
    assert out["public_message_en"].startswith("Flash-flood risk for today and tomorrow: Gagra: high.")
    assert out["footer"].startswith("DRAFT FOR OFFICIAL REVIEW")
