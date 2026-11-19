"""M12/M13 backend routes: tehsil shapes, risk, tehsil detail, place search, board login."""

from __future__ import annotations

import datetime as dt
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app.contracts import RiskDriver, RiskLevel, TehsilRiskForecast
from backend.app.contracts.enums import HydrometModel

PKT = dt.timezone(dt.timedelta(hours=5))


class FakeRisk:
    locator = None
    rivers = None

    def forecast(self, issue, replay=False):
        return [TehsilRiskForecast(tehsil_id="buner__gagra", issued_at=dt.datetime.combine(issue, dt.time(0), PKT),
                                   valid_date=issue + dt.timedelta(days=lead), lead_days=lead, probability=0.01 * (lead + 1),
                                   level=[RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.LOW, RiskLevel.LOW][lead],
                                   drivers=(RiskDriver(feature="precip_cell_max", value=50, contribution=1.0),),
                                   models_used=(HydrometModel.ECMWF,)) for lead in range(4)]


@pytest.fixture()
def client(monkeypatch):
    from backend.app.agent.service import load_context
    from backend.app.api import risk as risk_api
    from backend.app.config import get_settings
    from backend.app.main import create_app

    ctx = load_context(get_settings().data_dir, FakeRisk())
    monkeypatch.setattr(risk_api, "_context", lambda: ctx)
    monkeypatch.setattr(get_settings(), "board_password", SecretStr("test-board-pw"))
    return TestClient(create_app())


def test_tehsil_shapes_have_urdu_names(client):
    geo = client.get("/geo/tehsils").json()
    assert len(geo["features"]) == 48
    gagra = next(f for f in geo["features"] if f["properties"]["tehsil_id"] == "buner__gagra")
    assert gagra["properties"]["tehsil_ur"] == "گاگرہ"


def test_risk_and_replay_limits(client):
    r = client.get("/risk", params={"as_of": "2025-08-14T09:00:00+05:00"}).json()
    assert r["replay"] and r["issue_date"] == "2025-08-14"
    row = r["tehsils"][0]
    assert row["tehsil_id"] == "buner__gagra" and row["max_level"] == "high"
    assert row["days"][1]["driver_codes"] == ["precip_cell_max"]
    assert client.get("/risk", params={"as_of": "2023-07-01T09:00:00+05:00"}).status_code == 422


def test_tehsil_detail_and_search(client):
    d = client.get("/tehsils/buner__gagra").json()
    assert d["exposure"]["villages"] > 0 and d["shelters"] and d["rescue_1122"]
    assert all(not f["exposure_band"] == "high" for f in d["shelters"])
    assert client.get("/tehsils/nowhere__x").status_code == 404
    hits = client.get("/places/search", params={"q": "Pir"}).json()
    assert any(h["id"] == "manual:pir_baba" for h in hits)
    assert any(h["type"] == "tehsil" for h in client.get("/places/search", params={"q": "babu"}).json())


def test_board_login_and_protected_alerts(client):
    assert client.get("/alerts").status_code == 401
    assert client.post("/board/login", json={"password": "wrong"}).status_code == 401
    token = client.post("/board/login", json={"password": "test-board-pw"}).json()["token"]
    assert client.get("/alerts", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    from backend.app.api.risk import make_token

    expired = make_token(int(time.time()) - 10)
    assert client.get("/alerts", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged = token.split(".")[0] + ".AAAA"
    assert client.get("/alerts", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
