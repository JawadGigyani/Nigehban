"""One alert cycle: forecasts -> fixed rules -> compose -> store -> deliver.

Run by `python -m pipelines.alerts.run_cycle` (once or every few hours) or POST /internal/run-cycle. With `as_of`
it replays a past moment using the archived forecasts; replay alerts are marked
`replay=True` so they never mix with live ones in reports.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from sqlmodel import Session, select

from backend.app.alerts.rules import AlertCandidate, select_candidates, should_send
from backend.app.contracts import ChannelName, Language, RiskLevel
from backend.app.db import AlertRow, ContactCipher, DeliveryRow, SubscriptionRow

log = logging.getLogger(__name__)
PKT = dt.timezone(dt.timedelta(hours=5))


@dataclass
class CycleReport:
    issued_for: dt.date
    replay: bool
    candidates: int = 0
    new_alerts: list[dict] = field(default_factory=list)
    skipped_duplicates: int = 0
    deliveries_ok: int = 0
    deliveries_failed: int = 0

    def as_dict(self) -> dict:
        return {"issued_for": str(self.issued_for), "replay": self.replay, "candidates": self.candidates,
                "new_alerts": self.new_alerts, "skipped_duplicates": self.skipped_duplicates,
                "deliveries_ok": self.deliveries_ok, "deliveries_failed": self.deliveries_failed}


class AlertEngine:
    def __init__(self, risk_service, composer, channels: dict, cipher: ContactCipher | None,
                 village_tehsil: dict[str, str], in_scope: set[str],
                 min_level: RiskLevel = RiskLevel.HIGH, max_lead: int = 2, voice=None) -> None:
        self.risk = risk_service
        self.composer = composer
        self.channels = channels
        self.cipher = cipher
        self.village_tehsil = village_tehsil
        self.in_scope = in_scope
        self.min_level = min_level
        self.max_lead = max_lead
        self.voice = voice  # VoiceService or None

    def run(self, session: Session, as_of: dt.datetime | None = None, deliver: bool = True) -> CycleReport:
        now = dt.datetime.now(PKT)
        issue = (as_of.astimezone(PKT) if as_of else now).date()
        replay = as_of is not None and issue < now.date()
        report = CycleReport(issue, replay)
        forecasts = self.risk.forecast(issue, replay)
        candidates = select_candidates(forecasts, self.min_level, self.max_lead, self.in_scope)
        report.candidates = len(candidates)
        for candidate in candidates:
            f = candidate.forecast
            previous = session.exec(select(AlertRow.level).where(
                AlertRow.tehsil_id == f.tehsil_id, AlertRow.valid_date == f.valid_date,
                AlertRow.replay == replay)).all()
            if not should_send(candidate, list(previous)):
                report.skipped_duplicates += 1
                continue
            row = self._store(session, candidate, as_of or now, replay, speak=deliver)
            report.new_alerts.append({"id": row.id, "tehsil_id": row.tehsil_id, "level": row.level,
                                      "valid_date": str(row.valid_date), "lead_days": row.lead_days,
                                      "reasons": row.reason_codes})
            if deliver:
                ok, failed = self._deliver(session, row)
                report.deliveries_ok += ok
                report.deliveries_failed += failed
        session.commit()
        return report

    def _store(self, session: Session, candidate: AlertCandidate, issued_at: dt.datetime, replay: bool,
               speak: bool = True) -> AlertRow:
        f = candidate.forecast
        composed = self.composer.compose(candidate)
        reasons = list(candidate.reason_codes) + ([] if composed.checked else ["template_text"])
        row = AlertRow(tehsil_id=f.tehsil_id, level=f.level.value, valid_date=f.valid_date,
                       issued_at=issued_at.astimezone(dt.UTC), reason_codes=reasons, lead_days=f.lead_days,
                       message_ur=composed.message_ur, message_en=composed.message_en,
                       message_ur_roman=composed.message_ur_roman, citations=list(composed.citations),
                       replay=replay)
        if speak and self.voice is not None and self.voice.enabled:  # no voice quota spent on dry runs
            try:
                row.audio_key = self.voice.speak(composed.message_ur)
            except Exception as exc:  # voice is optional; the text alert still goes out
                log.warning("voice failed: %s", str(exc)[:120])
        session.add(row)
        session.flush()
        return row

    def subscribers_for(self, session: Session, tehsil_id: str) -> list[SubscriptionRow]:
        rows = session.exec(select(SubscriptionRow).where(SubscriptionRow.active == True)).all()  # noqa: E712
        return [s for s in rows if tehsil_id in (s.tehsil_ids or [])
                or any(self.village_tehsil.get(v) == tehsil_id for v in (s.village_ids or []))]

    def _deliver(self, session: Session, alert: AlertRow) -> tuple[int, int]:
        ok = failed = 0
        for sub in self.subscribers_for(session, alert.tehsil_id):
            text = {Language.UR.value: alert.message_ur, Language.EN.value: alert.message_en,
                    Language.UR_ROMAN.value: alert.message_ur_roman}.get(sub.language, alert.message_ur)
            try:
                channel = self.channels.get(ChannelName(sub.channel))
            except ValueError:  # a channel this build does not have
                channel = None
            if channel is None:
                failed += 1
                continue
            try:
                address = self.cipher.decrypt(sub.address_encrypted) if self.cipher else ""
                audio = f"/audio/{alert.audio_key}.mp3" if alert.audio_key else None
                result = channel.send(address, text, audio)
            except Exception as exc:  # one failed contact never stops the cycle
                log.warning("delivery failed on %s: %s", sub.channel, exc.__class__.__name__)
                result = None
            session.add(DeliveryRow(alert_id=alert.id, subscription_id=sub.id, channel=sub.channel,
                                    ok=bool(result and result.ok),
                                    provider_message_id=result.provider_message_id if result else None,
                                    error=(result.error if result else "exception")))
            if result and result.ok:
                ok += 1
            else:
                failed += 1
        alert.sent_to_count = ok
        session.add(alert)
        return ok, failed
