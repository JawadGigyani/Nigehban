"""Alert, subscription and inbox routes.

- POST /internal/run-cycle         run one alert cycle (cron every 3 h, or on demand; as_of = replay)
- POST /subscriptions              subscribe (returns the id; the contact is never returned)
- DELETE /subscriptions/{id}       unsubscribe (deletes the subscription and its delivery records)
- POST /me/delete                  delete every subscription and delivery for a contact
- GET /inbox/{subscription_id}     alerts delivered to this subscription (web app inbox)
- GET /alerts                      recent alerts (the board adds a password in M12)
"""

from __future__ import annotations

import datetime as dt
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.config import get_settings
from backend.app.config.settings import Environment
from backend.app.contracts import ChannelName, Subscription, SubscriptionCreate
from backend.app.db import AlertRow, DeliveryRow, SubscriptionRow, get_session

router = APIRouter(tags=["alerts"])


def get_engine():  # separate so tests can override
    from backend.app.alerts.service import get_alert_engine

    return get_alert_engine()


def get_cipher():
    from backend.app.alerts.service import make_cipher

    cipher = make_cipher(get_settings())
    if cipher is None:
        raise HTTPException(503, "Contact encryption keys are not configured.")
    return cipher


def known_places() -> tuple[set[str], set[str]]:
    engine = get_engine()
    return engine.in_scope, set(engine.village_tehsil)


def check_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = settings.internal_token.get_secret_value() if settings.internal_token else None
    if expected is None:
        if settings.environment is Environment.PRODUCTION:
            raise HTTPException(503, "NIGEHBAN_INTERNAL_TOKEN is not set.")
        return  # development: open
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(401, "Invalid internal token.")


class RunCycleRequest(BaseModel):
    as_of: dt.datetime | None = None
    deliver: bool = True


@router.post("/internal/run-cycle", dependencies=[Depends(check_internal_token)])
def run_cycle(request: RunCycleRequest, session: Session = Depends(get_session)) -> dict:
    return get_engine().run(session, request.as_of, request.deliver).as_dict()


@router.post("/subscriptions", response_model=Subscription)
def create_subscription(data: SubscriptionCreate, session: Session = Depends(get_session)) -> Subscription:
    from backend.app.alerts.subscriptions import SubscriptionError, subscribe

    tehsils, villages = known_places()
    try:
        return subscribe(session, get_cipher(), data, tehsils, villages)
    except SubscriptionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(subscription_id: str, session: Session = Depends(get_session)) -> dict:
    from backend.app.alerts.subscriptions import unsubscribe

    if not unsubscribe(session, subscription_id):
        raise HTTPException(404, "Subscription not found.")
    return {"deleted": True}


class DeleteMyData(BaseModel):
    address: str


@router.post("/me/delete")
def delete_my_data(request: DeleteMyData, session: Session = Depends(get_session)) -> dict:
    from backend.app.alerts.subscriptions import delete_my_data as _delete

    return {"deleted_subscriptions": _delete(session, get_cipher(), request.address)}


@router.get("/inbox/{subscription_id}")
def inbox(subscription_id: str, session: Session = Depends(get_session)) -> dict:
    from backend.app.alerts.service import citation_label

    sub = session.get(SubscriptionRow, subscription_id)
    if sub is None:
        raise HTTPException(404, "Subscription not found.")
    rows = session.exec(select(AlertRow).join(DeliveryRow, DeliveryRow.alert_id == AlertRow.id).where(
        DeliveryRow.subscription_id == subscription_id, DeliveryRow.ok == True,  # noqa: E712
        DeliveryRow.channel == ChannelName.WEB_INBOX.value).order_by(AlertRow.issued_at.desc())).all()
    kb = getattr(getattr(get_engine().composer, "context", None), "kb", None)
    text_field = {"ur": "message_ur", "en": "message_en", "ur_roman": "message_ur_roman"}[sub.language]
    return {"subscription_id": sub.id, "language": sub.language, "alerts": [
        {"id": a.id, "tehsil_id": a.tehsil_id, "level": a.level, "valid_date": str(a.valid_date),
         "issued_at": a.issued_at.isoformat(), "lead_days": a.lead_days, "message": getattr(a, text_field),
         "replay": a.replay, "citations": [{"ref": r, "label": citation_label(r, kb)} for r in a.citations]}
        for a in rows]}


@router.get("/alerts")
def recent_alerts(limit: int = 50, replay: bool | None = None, session: Session = Depends(get_session)) -> list[dict]:
    query = select(AlertRow).order_by(AlertRow.issued_at.desc()).limit(min(limit, 500))
    if replay is not None:
        query = query.where(AlertRow.replay == replay)
    return [{"id": a.id, "tehsil_id": a.tehsil_id, "level": a.level, "valid_date": str(a.valid_date),
             "lead_days": a.lead_days, "issued_at": a.issued_at.isoformat(), "reasons": a.reason_codes,
             "message_en": a.message_en, "message_ur": a.message_ur, "sent_to": a.sent_to_count,
             "replay": a.replay} for a in session.exec(query).all()]
