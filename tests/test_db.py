import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.db import (
    AlertRow,
    ContactCipher,
    ContactCipherError,
    DeliveryRow,
    SubscriptionRow,
    generate_keys,
    init_db,
    make_engine,
)


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    init_db(engine)
    return engine


@pytest.fixture
def cipher():
    return ContactCipher(*generate_keys())


def test_cipher_roundtrip_and_hash(cipher):
    token = cipher.encrypt(" +92 300 1234567 ")
    assert "300" not in token
    assert cipher.decrypt(token) == "+923001234567"
    assert cipher.hash("+92 300 1234567") == cipher.hash("+923001234567")
    assert cipher.hash("+923001234567") != cipher.hash("+923001234568")


def test_cipher_rejects_wrong_key(cipher):
    other = ContactCipher(*generate_keys())
    with pytest.raises(ContactCipherError):
        other.decrypt(cipher.encrypt("abc"))


def test_cipher_requires_keys():
    with pytest.raises(ContactCipherError):
        ContactCipher("", "")


def test_subscription_alert_delivery(engine, cipher):
    with Session(engine) as s:
        sub = SubscriptionRow(
            channel="web_inbox",
            address_encrypted=cipher.encrypt("device-1"),
            address_hash=cipher.hash("device-1"),
            tehsil_ids=["buner__daggar"],
        )
        alert = AlertRow(tehsil_id="buner__daggar", level="high", valid_date=dt.date(2025, 8, 15),
                         reason_codes=["heavy_rain_forecast"])
        s.add(sub)
        s.add(alert)
        s.commit()
        s.add(DeliveryRow(alert_id=alert.id, subscription_id=sub.id, channel="web_inbox", ok=True))
        s.commit()

        loaded = s.exec(select(SubscriptionRow)).one()
        assert loaded.tehsil_ids == ["buner__daggar"]
        assert cipher.decrypt(loaded.address_encrypted) == "device-1"
        assert s.exec(select(DeliveryRow)).one().ok


def test_alert_cooldown_unique(engine):
    day = dt.date(2025, 8, 15)
    with Session(engine) as s:
        s.add(AlertRow(tehsil_id="t1", level="high", valid_date=day))
        s.commit()
        s.add(AlertRow(tehsil_id="t1", level="very_high", valid_date=day))  # escalation is allowed
        s.commit()
        s.add(AlertRow(tehsil_id="t1", level="high", valid_date=day))  # repeat is not
        with pytest.raises(IntegrityError):
            s.commit()


def test_duplicate_subscription_rejected(engine, cipher):
    with Session(engine) as s:
        for _ in range(2):
            s.add(SubscriptionRow(channel="sms", address_encrypted=cipher.encrypt("1"),
                                  address_hash=cipher.hash("1")))
        with pytest.raises(IntegrityError):
            s.commit()
