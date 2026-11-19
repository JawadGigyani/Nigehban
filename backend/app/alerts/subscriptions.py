"""Subscriptions: opt-in, minimal data, encrypted contacts, unsubscribe and delete-my-data.

- The contact (phone, chat id or push subscription) is stored only encrypted
  (Fernet) plus a keyed hash used to find it again. It is never returned by the API.
- Subscribing again with the same contact on the same channel updates the
  existing subscription instead of creating a second one.
- DELETE /subscriptions/{id} removes one subscription and its delivery records.
- POST /me/delete removes every subscription and delivery for a contact.
"""

from __future__ import annotations

from sqlmodel import Session, select

from backend.app.contracts import Subscription, SubscriptionCreate
from backend.app.db import ContactCipher, DeliveryRow, SubscriptionRow


class SubscriptionError(ValueError):
    pass


def to_contract(row: SubscriptionRow) -> Subscription:
    return Subscription(id=row.id, channel=row.channel, language=row.language, tehsil_ids=tuple(row.tehsil_ids),
                        village_ids=tuple(row.village_ids), created_at=row.created_at, active=row.active)


def subscribe(session: Session, cipher: ContactCipher, data: SubscriptionCreate,
              known_tehsils: set[str], known_villages: set[str]) -> Subscription:
    unknown = [t for t in data.tehsil_ids if t not in known_tehsils] + \
              [v for v in data.village_ids if v not in known_villages]
    if unknown:
        raise SubscriptionError(f"Unknown places: {unknown[:5]}")
    if not data.tehsil_ids and not data.village_ids:
        raise SubscriptionError("Choose at least one tehsil or village.")
    address_hash = cipher.hash(data.address)
    row = session.exec(select(SubscriptionRow).where(SubscriptionRow.channel == data.channel.value,
                                                     SubscriptionRow.address_hash == address_hash)).first()
    if row is None:
        row = SubscriptionRow(channel=data.channel.value, address_encrypted=cipher.encrypt(data.address),
                              address_hash=address_hash)
    row.language = data.language.value
    row.tehsil_ids = sorted(set(data.tehsil_ids))
    row.village_ids = sorted(set(data.village_ids))
    row.active = True
    session.add(row)
    session.commit()
    session.refresh(row)
    return to_contract(row)


def _delete_rows(session: Session, rows: list[SubscriptionRow]) -> int:
    for row in rows:
        for d in session.exec(select(DeliveryRow).where(DeliveryRow.subscription_id == row.id)).all():
            session.delete(d)
        session.delete(row)
    session.commit()
    return len(rows)


def unsubscribe(session: Session, subscription_id: str) -> bool:
    row = session.get(SubscriptionRow, subscription_id)
    return bool(row) and _delete_rows(session, [row]) == 1


def delete_my_data(session: Session, cipher: ContactCipher, address: str) -> int:
    """Every subscription (any channel) for this contact, with its delivery records."""

    rows = session.exec(select(SubscriptionRow).where(SubscriptionRow.address_hash == cipher.hash(address))).all()
    return _delete_rows(session, list(rows))
