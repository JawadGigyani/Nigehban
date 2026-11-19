"""Delivery channels.

- console: prints the alert (demo, logs).
- web_inbox: nothing to send; the delivery row makes the alert appear in the
  user's inbox in the web app (GET /inbox/{subscription_id}).
- webpush: browser push with VAPID keys (works on Android Chrome and installed PWAs).
- telegram: private development channel only (Telegram is blocked in Pakistan).
- whatsapp, sms: stubs until a provider is chosen; they report "not configured".

    python -m backend.app.alerts.channels --vapid   # print a new VAPID key pair for .env
"""

from __future__ import annotations

import json
import logging
import sys

import httpx

from backend.app.contracts import ChannelName, DeliveryResult

log = logging.getLogger(__name__)


class ConsoleChannel:
    name = ChannelName.CONSOLE

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        self.sent: list[tuple[str, str]] = []

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        self.sent.append((address, text))
        try:
            print(f"--- alert to {address[:4]}*** ---\n{text}\n", file=self.stream)
        except UnicodeEncodeError:  # Windows consoles without UTF-8
            print(f"--- alert to {address[:4]}*** --- ({len(text)} chars, non-ASCII)", file=self.stream)
        return DeliveryResult(ok=True, channel=self.name)


class WebInboxChannel:
    name = ChannelName.WEB_INBOX

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        return DeliveryResult(ok=True, channel=self.name, provider_message_id="inbox")


class WebPushChannel:
    name = ChannelName.WEBPUSH

    def __init__(self, private_key: str | None, subject: str) -> None:
        self.private_key, self.subject = private_key, subject

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        if not self.private_key:
            return DeliveryResult(ok=False, channel=self.name, error="web push not configured (VAPID keys)")
        from pywebpush import WebPushException, webpush

        try:
            webpush(subscription_info=json.loads(address),
                    data=json.dumps({"title": "Nigehban", "body": text[:900]}, ensure_ascii=False),
                    vapid_private_key=self.private_key, vapid_claims={"sub": self.subject}, ttl=12 * 3600)
            return DeliveryResult(ok=True, channel=self.name)
        except (WebPushException, ValueError) as exc:
            return DeliveryResult(ok=False, channel=self.name, error=str(exc)[:200])


class TelegramChannel:
    name = ChannelName.TELEGRAM

    def __init__(self, token: str | None) -> None:
        self.token = token

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        if not self.token:
            return DeliveryResult(ok=False, channel=self.name, error="telegram not configured (development only)")
        try:
            r = httpx.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                           json={"chat_id": address, "text": text}, timeout=20)
            data = r.json()
            if data.get("ok"):
                return DeliveryResult(ok=True, channel=self.name,
                                      provider_message_id=str(data["result"]["message_id"]))
            return DeliveryResult(ok=False, channel=self.name, error=str(data.get("description"))[:200])
        except httpx.HTTPError as exc:
            return DeliveryResult(ok=False, channel=self.name, error=exc.__class__.__name__)


class StubChannel:
    def __init__(self, name: ChannelName) -> None:
        self.name = name

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        return DeliveryResult(ok=False, channel=self.name, error=f"{self.name.value} not configured")


def build_channels(settings) -> dict[ChannelName, object]:
    secret = lambda s: s.get_secret_value() if s is not None else None  # noqa: E731
    return {
        ChannelName.CONSOLE: ConsoleChannel(),
        ChannelName.WEB_INBOX: WebInboxChannel(),
        ChannelName.WEBPUSH: WebPushChannel(secret(settings.vapid_private_key), settings.vapid_subject),
        ChannelName.TELEGRAM: TelegramChannel(secret(settings.telegram_bot_token)),
        ChannelName.WHATSAPP: StubChannel(ChannelName.WHATSAPP),
        ChannelName.SMS: StubChannel(ChannelName.SMS),
    }


def _print_vapid_keys() -> None:
    import base64

    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid

    vapid = Vapid()
    vapid.generate_keys()
    public = vapid.public_key.public_bytes(serialization.Encoding.X962,
                                           serialization.PublicFormat.UncompressedPoint)
    private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731
    print(f"NIGEHBAN_VAPID_PUBLIC_KEY={b64(public)}\nNIGEHBAN_VAPID_PRIVATE_KEY={b64(private)}")


if __name__ == "__main__":
    if "--vapid" in sys.argv:
        _print_vapid_keys()
