import datetime as dt
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app import contracts as c
from tests.fixtures.contracts.build_fixtures import FIXTURES

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "contracts"

MODEL_FOR = {
    "tehsil_region": c.TehsilRegion,
    "flood_event": c.FloodEvent,
    "hydromet_daily": c.HydrometDaily,
    "tehsil_static": c.TehsilStatic,
    "village_exposure": c.VillageExposure,
    "river_thresholds": c.RiverThresholds,
    "tehsil_risk_forecast": c.TehsilRiskForecast,
    "subscription_create": c.SubscriptionCreate,
    "subscription": c.Subscription,
    "alert": c.Alert,
    "delivery_result": c.DeliveryResult,
}


def test_every_fixture_has_a_model_and_a_file():
    assert set(FIXTURES) == set(MODEL_FOR)
    for name in FIXTURES:
        assert (FIXTURE_DIR / f"{name}.json").is_file(), f"run build_fixtures for {name}"


@pytest.mark.parametrize("name", sorted(MODEL_FOR))
def test_fixture_files_validate_against_contract(name):
    rows = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
    assert rows
    for row in rows:
        MODEL_FOR[name].model_validate(row)


def test_contracts_are_frozen_and_forbid_extra_fields():
    region = FIXTURES["tehsil_region"][0]
    with pytest.raises(ValidationError):
        region.tehsil = "changed"
    with pytest.raises(ValidationError):
        c.TehsilRegion(**region.model_dump(), unexpected="x")


def test_positive_label_rule():
    positives = {c.EventType.FLASH_FLOOD, c.EventType.FLOOD, c.EventType.CLOUDBURST, c.EventType.DROWNING}
    assert c.POSITIVE_EVENT_TYPES == positives
    assert not c.is_positive("landslide")
    assert not c.is_positive(c.EventType.ROOF_COLLAPSE)
    flash, roof = FIXTURES["flood_event"]
    assert flash.is_positive and not roof.is_positive


def test_flood_event_has_no_name_fields():
    banned = {"name", "names", "victim", "victims", "person", "persons"}
    assert not banned & set(c.FloodEvent.model_fields)


def test_risk_level_order():
    assert c.RiskLevel.LOW.rank < c.RiskLevel.MODERATE.rank < c.RiskLevel.HIGH.rank < c.RiskLevel.VERY_HIGH.rank


def test_risk_probability_bounds():
    with pytest.raises(ValidationError):
        c.TehsilRiskForecast(
            tehsil_id="t", issued_at=dt.datetime(2025, 1, 1, tzinfo=dt.UTC),
            valid_date=dt.date(2025, 1, 1), lead_days=0, probability=1.2, level="high",
        )
    with pytest.raises(ValidationError):
        c.HydrometDaily(tehsil_id="t", date=dt.date(2025, 1, 1), model="era5", lead_days=4, precip_sum=0)


def test_protocols_are_runtime_checkable():
    class FakeRisk:
        def get_tehsil_risk(self, tehsil_id, start, end, as_of=None):
            return []

        def get_risk_for_point(self, lat, lon, as_of=None):
            return []

    class FakeChannel:
        name = c.ChannelName.CONSOLE

        def send(self, address, text, audio_url=None):
            return c.DeliveryResult(ok=True, channel=self.name)

    assert isinstance(FakeRisk(), c.RiskProvider)
    assert isinstance(FakeChannel(), c.AlertChannel)


def test_subscription_read_model_has_no_address():
    assert "address" not in c.Subscription.model_fields
