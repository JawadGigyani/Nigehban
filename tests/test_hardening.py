"""Hardening, voice, SMS/WhatsApp channels, contacts, migration, runtime data."""

from __future__ import annotations

import json

import numpy as np
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.alerts.voice import VoiceError, VoiceService, speakable
from backend.app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

ROOT = Path(__file__).resolve().parents[1]


def _app(**limits) -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, **limits)

    @app.post("/chat")
    def chat():
        return {"ok": True}

    @app.get("/risk")
    def risk():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return TestClient(app)


def test_rate_limits_per_ip_and_global_chat_cap():
    client = _app(chat_per_min=3, default_per_min=5, chat_per_day=4)
    codes = [client.post("/chat").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    other_ip = {"X-Forwarded-For": "203.0.113.9"}
    assert client.post("/chat", headers=other_ip).status_code == 200  # 4th chat today (global cap 4)
    assert client.post("/chat", headers={"X-Forwarded-For": "203.0.113.10"}).status_code == 429  # daily cap
    assert all(client.get("/health").status_code == 200 for _ in range(20))  # exempt


def test_security_headers():
    r = _app().get("/risk")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Cache-Control"] == "no-store"


def test_speakable_trims_urls_and_cuts_at_sentence():
    text = "پہلا جملہ۔ " * 100 + "https://example.com"
    out = speakable(text, 60)
    assert len(out) <= 60 and out.endswith("۔") and "http" not in out


def test_voice_service_caches_and_reports_errors(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        assert request.headers["xi-api-key"] == "k"
        return httpx.Response(200, content=b"ID3fake")

    voice = VoiceService("k", "v", "eleven_v3", tmp_path, http=httpx.Client(transport=httpx.MockTransport(handler)))
    key = voice.speak("سیلاب کا خطرہ زیادہ ہے۔")
    assert voice.path_for(key).read_bytes() == b"ID3fake"
    voice.speak("سیلاب کا خطرہ زیادہ ہے۔")
    assert len(calls) == 1 and calls[0]["language_code"] == "ur" and calls[0]["model_id"] == "eleven_v3"
    bad = VoiceService("k", "v", "eleven_v3", tmp_path,
                       http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, text="no"))))
    with pytest.raises(VoiceError):
        bad.speak("دوسرا جملہ۔")
    with pytest.raises(VoiceError):
        VoiceService(None, "v", "eleven_v3", tmp_path).speak("x")


def test_sms_gateway_channel(monkeypatch):
    from backend.app.alerts.channels import SmsGatewayChannel

    sent = {}

    def fake_post(url, auth=None, json=None, timeout=None):
        sent.update(url=url, auth=auth, json=json)
        return httpx.Response(202, json={"id": "abc"})

    monkeypatch.setattr(httpx, "post", fake_post)
    r = SmsGatewayChannel("https://api.sms-gate.app/3rdparty/v1", "u", "p").send("03001234567", "الرٹ")
    assert r.ok and r.provider_message_id == "abc"
    assert sent["url"].endswith("/messages") and sent["json"]["phoneNumbers"] == ["+923001234567"]
    assert sent["json"]["textMessage"]["text"] == "الرٹ"
    SmsGatewayChannel("http://192.168.1.5:8080", "u", "p").send("+923001234567", "x")
    assert sent["url"] == "http://192.168.1.5:8080/message"
    assert not SmsGatewayChannel("https://x", None, None).send("+92300", "x").ok


def test_whatsapp_channel(monkeypatch):
    from backend.app.alerts.channels import WhatsAppChannel

    bodies = []

    def fake_post(url, json=None, headers=None, timeout=None):
        bodies.append(json)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert WhatsAppChannel("t", "123", "nigehban_alert").send("+923001234567", "الرٹ").ok
    assert bodies[0]["type"] == "template" and bodies[0]["to"] == "923001234567"
    assert WhatsAppChannel("t", "123", None).send("+923001234567", "hi").ok and bodies[1]["type"] == "text"
    assert not WhatsAppChannel(None, None, None).send("+92", "x").ok


def test_district_contacts():
    from backend.app.geo.contacts import contact_evidence, district_contact

    assert district_contact("swat__babuzai")["control_room"] == "0946-9240249"
    item = contact_evidence("buner__gagra")
    assert item.ref == "contact:rescue1122:buner" and "0939-510129" in item.text
    assert district_contact("nowhere__x") is None


def test_migration_adds_missing_columns(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from backend.app.db import init_db

    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # an alerts table from before the voice column existed
        conn.execute(text("CREATE TABLE alerts (id VARCHAR PRIMARY KEY, tehsil_id VARCHAR, level VARCHAR, "
                          "valid_date DATE, issued_at DATETIME, reason_codes JSON, message_ur VARCHAR, "
                          "message_en VARCHAR, citations JSON, sent_to_count INTEGER, replay BOOLEAN)"))
    init_db(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("alerts")}
    assert {"audio_key", "message_ur_roman", "lead_days"} <= cols


def test_runtime_data_manifest_has_no_private_paths():
    from backend.app.runtime_data import RUNTIME_FILES, missing_files

    assert not any(p.startswith(("raw/pdma", "interim/pdma", "events")) for p in RUNTIME_FILES)
    assert isinstance(missing_files(ROOT / "data"), list)


def test_tts_route_is_urdu_only(monkeypatch):
    from backend.app.api import voice as voice_api
    from backend.app.main import create_app

    class FakeVoice:
        enabled = True

        def speak(self, text):
            return "0123456789abcdef0123"

        def path_for(self, key):
            return Path("missing.mp3")

    monkeypatch.setattr(voice_api, "get_voice", lambda: FakeVoice())
    client = TestClient(create_app())
    assert client.post("/tts", json={"text": "hello"}).status_code == 422
    assert client.post("/tts", json={"text": "سلام"}).json()["audio_url"] == "/audio/0123456789abcdef0123.mp3"
    assert client.get("/audio/../../etc.mp3").status_code == 404
    assert client.get("/config").json().keys() >= {"voice", "sms", "whatsapp"}


def test_twilio_channel(monkeypatch):
    from backend.app.alerts.channels import TwilioChannel
    from backend.app.contracts import ChannelName

    posts = []

    def fake_post(url, data=None, auth=None, timeout=None):
        posts.append((url, data, auth))
        return httpx.Response(201, json={"sid": "SM1"})

    monkeypatch.setattr(httpx, "post", fake_post)
    wa = TwilioChannel(ChannelName.WHATSAPP, "AC1", "tok", "+14155238886")
    assert wa.send("03001234567", "الرٹ").ok
    url, data, auth = posts[0]
    assert url.endswith("/Accounts/AC1/Messages.json") and auth == ("AC1", "tok")
    assert data["From"] == "whatsapp:+14155238886" and data["To"] == "whatsapp:+923001234567"
    sms = TwilioChannel(ChannelName.SMS, "AC1", "tok", "+15550001111")
    assert sms.send("+923001234567", "x").ok and posts[1][1]["From"] == "+15550001111"


def test_imerg_parsing_and_tehsil_weights():
    from backend.app.hydromet.imerg import LATS, LONS, parse_ascii, tehsil_values, tehsil_weights

    text = "Dataset {...}\nprecipitation.precipitation[1][2][3]\n[0][0], 1.5, -9999.9, 3\n[0][1], 0, 2, 4\n"
    grid = parse_ascii(text)
    assert grid.shape == (2, 3) and np.isnan(grid[0, 1]) and grid[1, 2] == 4
    weights = tehsil_weights(ROOT / "data" / "reference" / "tehsils.geojson")
    assert len(weights) == 48 and abs(sum(w for *_, w in weights["swat__babuzai"]) - 1) < 1e-9
    full = np.full((len(LONS), len(LATS)), 10.0)
    mean, cell_max = tehsil_values(full, weights)["swat__babuzai"]
    assert mean == 10.0 and cell_max == 10.0


def test_smsto_channel(monkeypatch):
    from backend.app.alerts.channels import SmsToChannel

    seen = {}

    def fake_post(url, timeout=None, headers=None, json=None):
        seen.update(url=url, headers=headers, json=json)
        return httpx.Response(200, json={"success": True, "message_id": "m1", "message": "queued"})

    monkeypatch.setattr(httpx, "post", fake_post)
    r = SmsToChannel("key", "Nigehban").send("03235550000", "الرٹ")
    assert r.ok and r.provider_message_id == "m1"
    assert seen["url"] == "https://api.sms.to/sms/send" and seen["headers"]["Authorization"] == "Bearer key"
    assert seen["json"] == {"message": "الرٹ", "to": "+923235550000", "sender_id": "Nigehban"}
