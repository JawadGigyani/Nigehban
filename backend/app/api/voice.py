"""Voice routes.

- GET /audio/{key}.mp3   a cached Urdu voice file (alerts and answers)
- POST /tts              speak an Urdu text (answers in the app); rate limited, cached, Urdu only
"""

from __future__ import annotations

import re
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.config import get_settings

router = APIRouter(tags=["voice"])
KEY = re.compile(r"^[0-9a-f]{20}$")


@lru_cache(maxsize=1)
def get_voice():
    from backend.app.alerts.voice import VoiceService

    return VoiceService.from_settings(get_settings())


@router.get("/audio/{key}.mp3")
def audio(key: str):
    if not KEY.match(key):
        raise HTTPException(404, "Not found.")
    path = get_voice().path_for(key)
    if not path.is_file():
        raise HTTPException(404, "Not found.")
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/tts")
def tts(request: TtsRequest) -> dict:
    from backend.app.alerts.voice import VoiceError

    voice = get_voice()
    if not voice.enabled:
        raise HTTPException(503, "Voice is not configured.")
    if not any("؀" <= ch <= "ۿ" for ch in request.text):
        raise HTTPException(422, "Only Urdu text is spoken.")
    try:
        key = voice.speak(request.text)
    except VoiceError as exc:
        raise HTTPException(502, str(exc)[:200]) from exc
    return {"audio_url": f"/audio/{key}.mp3"}


@router.get("/config")
def public_config() -> dict:
    """What the web app may turn on (no secrets)."""

    s = get_settings()
    return {"voice": bool(s.elevenlabs_api_key), "webpush_public_key": s.vapid_public_key,
            "sms": bool(s.sms_gateway_username and s.sms_gateway_password),
            "whatsapp": bool(s.whatsapp_token and s.whatsapp_phone_number_id)}
