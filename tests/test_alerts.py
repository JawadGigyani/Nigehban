"""M9 alert engine: rules, cooldown and escalation, checked text, channels, subscriptions, API."""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.app.alerts.channels import ConsoleChannel, StubChannel, WebInboxChannel, WebPushChannel
from backend.app.alerts.composer import AlertComposer, AlertDraft, check_draft
from backend.app.alerts.cycle import AlertEngine
from backend.app.alerts.rules import select_candidates, should_send
from backend.app.alerts.subscriptions import SubscriptionError, delete_my_data, subscribe, unsubscribe
from backend.app.contracts import (
    ChannelName,
    Language,
    RiskDriver,
    RiskLevel,
    SubscriptionCreate,
    TehsilRiskForecast,
)
from backend.app.contracts.enums import HydrometModel
from backend.app.db import AlertRow, ContactCipher, DeliveryRow, SubscriptionRow, generate_keys, init_db, make_engine
from tests.test_agent import _context

PKT = dt.timezone(dt.timedelta(hours=5))
D = dt.date(2025, 8, 15)


def fc(tehsil="buner__gagra", lead=1, level=RiskLevel.HIGH, glofas=False, valid=D) -> TehsilRiskForecast:
    return TehsilRiskForecast(tehsil_id=tehsil, issued_at=dt.datetime(2025, 8, 14, tzinfo=PKT), valid_date=valid,
                              lead_days=lead, probability=0.02, level=level, glofas_flag=glofas,
                              drivers=(RiskDriver(feature="precip_cell_max", value=60, contribution=1.0),),
                              models_used=(HydrometModel.ECMWF,))


def test_rules_threshold_lead_and_river_flag():
    picks = select_candidates([fc(level=RiskLevel.MODERATE), fc(tehsil="swat__kalam", level=RiskLevel.HIGH, lead=3),
                               fc(tehsil="swat__bahrain", level=RiskLevel.LOW, glofas=True),
                               fc(tehsil="swat__babuzai", level=RiskLevel.VERY_HIGH, lead=0)])
    assert [c.forecast.tehsil_id for c in picks] == ["swat__babuzai", "swat__bahrain"]  # lead 3 and moderate dropped
    assert "river_flag" in picks[1].reason_codes


def test_cooldown_and_escalation():
    high = select_candidates([fc(level=RiskLevel.HIGH)])[0]
    very = select_candidates([fc(level=RiskLevel.VERY_HIGH)])[0]
    assert should_send(high, [])
    assert not should_send(high, ["high"])  # same level, same day: no repeat
    assert not should_send(high, ["very_high"])  # lower than already sent
    assert should_send(very, ["high"])  # level rose: send again


class DraftLLM:
    def __init__(self, drafts):
        self.drafts = list(drafts)

    def complete_structured(self, system, user, model):
        return self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]


GOOD = AlertDraft(message_ur="کل گاگرہ، بونیر میں خطرہ زیادہ ہے۔ ندی نالوں سے دور رہیں۔",
                  message_en="Flash-flood risk is high for Gagra tomorrow. Keep away from streams.",
                  message_ur_roman="Kal Gagra mein khatra zyada hai. Nadi nalon se door rahein.",
                  refs=["risk:buner__gagra:2025-08-15", "contact:helplines"])


def test_composer_checks_level_words_and_citations():
    composer = AlertComposer(DraftLLM([GOOD]), _context())
    candidate = select_candidates([fc()])[0]
    bundle = composer.evidence(candidate)
    assert check_draft(GOOD, bundle, "high") == []
    softened = GOOD.model_copy(update={"message_en": "Some risk for Gagra tomorrow."})
    assert any("level" in e for e in check_draft(softened, bundle, "high"))
    invented = GOOD.model_copy(update={"refs": ["doc:invented:p1#1"]})
    assert any("not in the evidence" in e for e in check_draft(invented, bundle, "high"))
    out = composer.compose(candidate)
    assert out.checked and out.message_en.endswith("Follow PDMA and district administration instructions.")


def test_composer_falls_back_to_template():
    bad = GOOD.model_copy(update={"refs": ["doc:invented:p1#1"]})
    out = AlertComposer(DraftLLM([bad]), _context()).compose(select_candidates([fc()])[0])
    assert not out.checked and "high" in out.message_en and "زیادہ" in out.message_ur and "1122" in out.message_en


@pytest.fixture()
def db():
    engine = make_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def cipher():
    return ContactCipher(*generate_keys())


class FixedRisk:
    def __init__(self, forecasts):
        self.forecasts = forecasts

    def forecast(self, issue, replay=False):
        return self.forecasts


def _engine(risk, cipher, console):
    channels = {ChannelName.CONSOLE: console, ChannelName.WEB_INBOX: WebInboxChannel(),
                ChannelName.SMS: StubChannel(ChannelName.SMS)}
    return AlertEngine(risk, AlertComposer(DraftLLM([GOOD]), _context()), channels, cipher,
                       {"manual:pir_baba": "buner__gagra"}, {"buner__gagra", "battagram__allai"})


def test_cycle_sends_once_then_escalates(db, cipher):
    console = ConsoleChannel(stream=io.StringIO())
    for sub in (SubscriptionCreate(channel=ChannelName.CONSOLE, address="+92 300 1234567", tehsil_ids=("buner__gagra",)),
                SubscriptionCreate(channel=ChannelName.WEB_INBOX, address="inbox-1", language=Language.EN,
                                   village_ids=("manual:pir_baba",)),
                SubscriptionCreate(channel=ChannelName.SMS, address="+923001112222", tehsil_ids=("buner__gagra",))):
        subscribe(db, cipher, sub, {"buner__gagra"}, {"manual:pir_baba"})
    risk = FixedRisk([fc(level=RiskLevel.HIGH)])
    engine = _engine(risk, cipher, console)
    as_of = dt.datetime(2025, 8, 14, 9, tzinfo=PKT)
    first = engine.run(db, as_of)
    assert len(first.new_alerts) == 1 and first.deliveries_ok == 2 and first.deliveries_failed == 1  # SMS stub
    assert console.sent[0][0] == "+923001234567"  # decrypted only to send
    again = engine.run(db, as_of)
    assert again.new_alerts == [] and again.skipped_duplicates == 1
    risk.forecasts = [fc(level=RiskLevel.VERY_HIGH, lead=0)]
    up = engine.run(db, as_of)
    assert len(up.new_alerts) == 1 and up.new_alerts[0]["level"] == "very_high"
    rows = db.exec(select(AlertRow)).all()
    assert len(rows) == 2 and all(r.replay for r in rows)
    assert all("+92" not in str(r.message_en) for r in rows)


def test_subscription_privacy_and_deletion(db, cipher):
    data = SubscriptionCreate(channel=ChannelName.WEB_INBOX, address="Inbox-ABC", tehsil_ids=("buner__gagra",))
    first = subscribe(db, cipher, data, {"buner__gagra"}, set())
    second = subscribe(db, cipher, data.model_copy(update={"language": Language.EN}), {"buner__gagra"}, set())
    assert first.id == second.id  # same contact updates, no duplicate
    row = db.get(SubscriptionRow, first.id)
    assert "inbox" not in row.address_encrypted.lower() and row.address_hash != "inbox-abc"
    with pytest.raises(SubscriptionError):
        subscribe(db, cipher, data.model_copy(update={"tehsil_ids": ("nowhere__x",)}), {"buner__gagra"}, set())
    subscribe(db, cipher, data.model_copy(update={"channel": ChannelName.CONSOLE}), {"buner__gagra"}, set())
    assert delete_my_data(db, cipher, "inbox-abc") == 2  # both channels, case-insensitive
    assert not unsubscribe(db, first.id)


def test_webpush_json_keeps_case(cipher):
    address = '{"endpoint": "https://push.example/AbC", "keys": {"p256dh": "BXyZ", "auth": "QwE"}}'
    assert cipher.decrypt(cipher.encrypt(address)) == address.replace(" ", "")
    assert not WebPushChannel(None, "mailto:x").send(address, "hi").ok  # not configured


def test_api_flow(db, cipher, monkeypatch):
    from backend.app.api import alerts as api
    from backend.app.db import get_session
    from backend.app.main import create_app

    console = ConsoleChannel(stream=io.StringIO())
    engine = _engine(FixedRisk([fc()]), cipher, console)
    monkeypatch.setattr(api, "get_engine", lambda: engine)
    monkeypatch.setattr(api, "get_cipher", lambda: cipher)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db
    client = TestClient(app)
    r = client.post("/subscriptions", json={"channel": "web_inbox", "address": "inbox-api", "language": "en",
                                            "tehsil_ids": ["buner__gagra"]})
    assert r.status_code == 200 and "address" not in r.json()
    sub_id = r.json()["id"]
    run = client.post("/internal/run-cycle", json={"as_of": "2025-08-14T09:00:00+05:00"})
    assert run.status_code == 200 and len(run.json()["new_alerts"]) == 1
    inbox = client.get(f"/inbox/{sub_id}").json()
    assert inbox["alerts"][0]["level"] == "high" and "Follow PDMA" in inbox["alerts"][0]["message"]
    assert client.get("/alerts").json()[0]["tehsil_id"] == "buner__gagra"
    assert client.post("/me/delete", json={"address": "inbox-api"}).json() == {"deleted_subscriptions": 1}
    assert client.get(f"/inbox/{sub_id}").status_code == 404


def test_internal_token_required_when_set(monkeypatch):
    from pydantic import SecretStr

    from backend.app.api import alerts as api
    from backend.app.config import get_settings
    from backend.app.main import create_app

    monkeypatch.setattr(get_settings(), "internal_token", SecretStr("s3cret"))
    client = TestClient(create_app())
    assert client.post("/internal/run-cycle", json={}).status_code == 401
    assert client.post("/internal/run-cycle", json={}, headers={"X-Internal-Token": "wrong"}).status_code == 401


def test_urdu_place_names_are_fixed_and_checked():
    from backend.app.geo.urdu import place_ur

    assert place_ur("buner__gagra") == "گاگرہ، بونیر"
    composer = AlertComposer(DraftLLM([GOOD]), _context())
    candidate = select_candidates([fc(tehsil="buner__khado_khel")])[0]
    bundle = composer.evidence(candidate) if "buner__khado_khel" in composer.context.tehsils else None
    draft = GOOD.model_copy(update={"message_ur": "خدو خیل، بنوں میں خطرہ زیادہ ہے۔",
                                    "refs": ["contact:helplines"]})
    from backend.app.agent.evidence import HELPLINES, EvidenceBundle

    bundle = bundle or EvidenceBundle(items=[HELPLINES])
    errors = check_draft(draft, bundle, "high", "buner__khado_khel")
    assert any("another district" in e for e in errors)  # Bannu instead of Buner
    misspelled = draft.model_copy(update={"message_ur": "گرا، بونیر میں خطرہ زیادہ ہے۔"})
    assert any("name the tehsil" in e for e in check_draft(misspelled, bundle, "high", "buner__gagra"))
