"""Wiring for the alert engine (shared by the API and the replay script)."""

from __future__ import annotations

from functools import lru_cache

from backend.app.alerts.channels import build_channels
from backend.app.alerts.composer import AlertComposer
from backend.app.alerts.cycle import AlertEngine
from backend.app.contracts import RiskLevel
from backend.app.db import ContactCipher, ContactCipherError


def citation_label(ref: str, kb=None) -> str:
    kind = ref.split(":", 1)[0]
    if kind == "doc" and kb is not None:
        passage = kb.get(ref)
        if passage:
            return passage.label
    return {"risk": "Nigehban risk model", "river": "GloFAS river flow (Copernicus)",
            "exposure": "Nigehban terrain analysis", "facility": "OpenStreetMap / Nigehban (unverified)",
            "contact": "Rescue 1122; PDMA helpline"}.get(kind, ref)


def make_cipher(settings) -> ContactCipher | None:
    try:
        return ContactCipher.from_settings(settings)
    except ContactCipherError:
        return None


@lru_cache(maxsize=1)
def get_alert_engine() -> AlertEngine:
    from backend.app.agent.service import load_context
    from backend.app.config import get_settings
    from backend.app.llm import LLMService
    from backend.app.risk.service import get_risk_service

    settings = get_settings()
    risk = get_risk_service()
    context = load_context(settings.data_dir, risk)
    # Subscribable villages: every populated place in scope (gazetteer + manual places).
    village_tehsil = dict(zip(context.gazetteer["place_id"], context.gazetteer["tehsil_id"], strict=True))
    village_tehsil.update(zip(context.villages["village_id"], context.villages["tehsil_id"], strict=True))
    in_scope = {t for t, v in context.tehsils.items() if v["in_scope"]}
    return AlertEngine(risk, AlertComposer(LLMService.from_settings(settings), context), build_channels(settings),
                       make_cipher(settings), village_tehsil, in_scope,
                       RiskLevel(settings.alert_min_level), settings.alert_max_lead_days)
