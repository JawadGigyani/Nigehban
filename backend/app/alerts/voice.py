"""Urdu voice for alerts and answers (ElevenLabs text to speech).

- Model `eleven_v3` with language code "ur" (multilingual_v2 and flash do not support Urdu).
- Audio is cached on disk by a hash of the text, so the same alert is spoken once.
- Only Urdu script is spoken; text is cut at `voice_max_chars` to protect the free quota.
- If the key is missing or the call fails, alerts still go out as text.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import httpx

log = logging.getLogger(__name__)
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class VoiceError(RuntimeError):
    pass


def speakable(text: str, max_chars: int) -> str:
    """Drop URLs and symbols the voice would read out, then cut at a sentence end."""

    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_#|>`]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind("۔"), cut.rfind("."), cut.rfind("؟"))
    return cut[: end + 1] if end > max_chars // 2 else cut


class VoiceService:
    def __init__(self, api_key: str | None, voice_id: str, model: str, cache_dir: Path, max_chars: int = 600,
                 http: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.cache_dir = cache_dir
        self.max_chars = max_chars
        self.http = http or httpx.Client(timeout=60)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings) -> VoiceService:
        key = settings.elevenlabs_api_key.get_secret_value() if settings.elevenlabs_api_key else None
        return cls(key, settings.elevenlabs_voice_id, settings.elevenlabs_model,
                   settings.data_dir / "audio", settings.voice_max_chars)

    def key_for(self, text: str) -> str:
        blob = f"{self.model}|{self.voice_id}|{speakable(text, self.max_chars)}"
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:20]

    def path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.mp3"

    def speak(self, text: str) -> str:
        """Return the audio key (file data/audio/<key>.mp3), creating it if needed."""

        if not self.enabled:
            raise VoiceError("Voice is not configured (NIGEHBAN_ELEVENLABS_API_KEY).")
        clean = speakable(text, self.max_chars)
        if not clean:
            raise VoiceError("Nothing to speak.")
        key = self.key_for(text)
        path = self.path_for(key)
        if path.is_file():
            return key
        r = self.http.post(TTS_URL.format(voice_id=self.voice_id),
                           params={"output_format": "mp3_44100_64"},
                           headers={"xi-api-key": self.api_key, "Accept": "audio/mpeg"},
                           json={"text": clean, "model_id": self.model, "language_code": "ur"})
        if r.status_code != 200:
            detail = r.text[:200]
            raise VoiceError(f"ElevenLabs error {r.status_code}: {detail}")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        tmp.replace(path)
        return key
