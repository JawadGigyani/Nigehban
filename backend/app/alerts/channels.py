"""Delivery channels.

- console: prints the alert (demo, logs).
- web_inbox: nothing to send; the delivery row makes the alert appear in the
  user's inbox in the web app (GET /inbox/{subscription_id}).
- webpush: browser push with VAPID keys (works on Android Chrome and installed PWAs).
- telegram: private development channel only (Telegram is blocked in Pakistan).
- sms: the free open-source "SMS Gateway for Android" app (an Android phone + SIM sends the
  SMS; cloud mode https://api.sms-gate.app or local mode on the phone). Carrier SMS charges and
  limits apply to the SIM.
- whatsapp: Meta WhatsApp Cloud API. Free only with Meta's test number and up to 5 verified
  recipients; real use needs an approved template and is paid per message in Pakistan.

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


class SmsGatewayChannel:
    """SMS through the SMS Gateway for Android app (https://docs.sms-gate.app)."""

    name = ChannelName.SMS

    def __init__(self, base_url: str, username: str | None, password: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.username, self.password = username, password

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        if not (self.username and self.password):
            return DeliveryResult(ok=False, channel=self.name, error="sms gateway not configured")
        phone = address if address.startswith("+") else "+92" + address.lstrip("0")
        # Cloud mode uses /messages; the phone's local server uses /message.
        path = "/message" if ":8080" in self.base_url else "/messages"
        try:
            r = httpx.post(f"{self.base_url}{path}", auth=(self.username, self.password), timeout=20,
                           json={"textMessage": {"text": text[:900]}, "phoneNumbers": [phone], "ttl": 6 * 3600})
            if r.status_code in (200, 201, 202):
                return DeliveryResult(ok=True, channel=self.name, provider_message_id=str(r.json().get("id", "")))
            return DeliveryResult(ok=False, channel=self.name, error=f"HTTP {r.status_code}: {r.text[:120]}")
        except (httpx.HTTPError, ValueError) as exc:
            return DeliveryResult(ok=False, channel=self.name, error=exc.__class__.__name__)


class WhatsAppChannel:
    """WhatsApp Cloud API: template message when configured, else plain text (24-hour window only)."""

    name = ChannelName.WHATSAPP

    def __init__(self, token: str | None, phone_number_id: str | None, template: str | None) -> None:
        self.token, self.phone_number_id, self.template = token, phone_number_id, template

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        if not (self.token and self.phone_number_id):
            return DeliveryResult(ok=False, channel=self.name, error="whatsapp not configured")
        to = address.lstrip("+")
        if self.template:
            body = {"messaging_product": "whatsapp", "to": to, "type": "template",
                    "template": {"name": self.template, "language": {"code": "ur"},
                                 "components": [{"type": "body", "parameters": [{"type": "text", "text": text[:1000]}]}]}}
        else:
            body = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text[:4000]}}
        try:
            r = httpx.post(f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages", json=body,
                           headers={"Authorization": f"Bearer {self.token}"}, timeout=20)
            data = r.json()
            if r.status_code == 200 and data.get("messages"):
                return DeliveryResult(ok=True, channel=self.name, provider_message_id=data["messages"][0].get("id"))
            return DeliveryResult(ok=False, channel=self.name, error=str(data.get("error", {}).get("message"))[:160])
        except (httpx.HTTPError, ValueError) as exc:
            return DeliveryResult(ok=False, channel=self.name, error=exc.__class__.__name__)


class SmsToChannel:
    """SMS through SMS.to (https://sms.to): POST /sms/send with a bearer API key."""

    name = ChannelName.SMS

    def __init__(self, api_key: str, sender_id: str = "Nigehban") -> None:
        self.api_key, self.sender_id = api_key, sender_id

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        to = address if address.startswith("+") else "+92" + address.lstrip("0")
        try:
            r = httpx.post("https://api.sms.to/sms/send", timeout=20,
                           headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
                           json={"message": text[:900], "to": to, "sender_id": self.sender_id})
            body = r.json()
            if r.status_code in (200, 201, 202) and body.get("success", True):
                return DeliveryResult(ok=True, channel=self.name, provider_message_id=str(body.get("message_id", "")))
            return DeliveryResult(ok=False, channel=self.name, error=str(body.get("message", r.status_code))[:200])
        except (httpx.HTTPError, ValueError) as exc:
            return DeliveryResult(ok=False, channel=self.name, error=exc.__class__.__name__)


class TwilioChannel:
    """SMS or WhatsApp through Twilio's Messages API (trial credit works for testing).

    WhatsApp uses the Sandbox number until a WhatsApp sender is approved; recipients must first
    send the sandbox join code from their WhatsApp. Trial SMS only reach verified numbers.
    """

    def __init__(self, name: ChannelName, account_sid: str, auth_token: str, sender: str) -> None:
        self.name, self.sid, self.token, self.sender = name, account_sid, auth_token, sender

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        to = address if address.startswith("+") else "+92" + address.lstrip("0")
        prefix = "whatsapp:" if self.name is ChannelName.WHATSAPP else ""
        data = {"From": f"{prefix}{self.sender}", "To": f"{prefix}{to}", "Body": text[:1500]}
        try:
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json",
                           data=data, auth=(self.sid, self.token), timeout=20)
            body = r.json()
            if r.status_code in (200, 201):
                return DeliveryResult(ok=True, channel=self.name, provider_message_id=body.get("sid"))
            return DeliveryResult(ok=False, channel=self.name, error=f"{body.get('code')}: {body.get('message')}"[:200])
        except (httpx.HTTPError, ValueError) as exc:
            return DeliveryResult(ok=False, channel=self.name, error=exc.__class__.__name__)


class StubChannel:
    def __init__(self, name: ChannelName) -> None:
        self.name = name

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult:
        return DeliveryResult(ok=False, channel=self.name, error=f"{self.name.value} not configured")


def build_channels(settings) -> dict[ChannelName, object]:
    secret = lambda s: s.get_secret_value() if s is not None else None  # noqa: E731
    twilio = settings.twilio_account_sid and settings.twilio_auth_token
    channels = {
        ChannelName.CONSOLE: ConsoleChannel(),
        ChannelName.WEB_INBOX: WebInboxChannel(),
        ChannelName.WEBPUSH: WebPushChannel(secret(settings.vapid_private_key), settings.vapid_subject),
        ChannelName.TELEGRAM: TelegramChannel(secret(settings.telegram_bot_token)),
        ChannelName.WHATSAPP: WhatsAppChannel(secret(settings.whatsapp_token), settings.whatsapp_phone_number_id,
                                              settings.whatsapp_template),
        ChannelName.SMS: SmsGatewayChannel(settings.sms_gateway_url, settings.sms_gateway_username,
                                           secret(settings.sms_gateway_password)),
    }
    if settings.smsto_api_key:
        channels[ChannelName.SMS] = SmsToChannel(secret(settings.smsto_api_key), settings.smsto_sender_id)
    if twilio:
        token = secret(settings.twilio_auth_token)
        channels[ChannelName.WHATSAPP] = TwilioChannel(ChannelName.WHATSAPP, settings.twilio_account_sid, token,
                                                       settings.twilio_whatsapp_from)
        if settings.twilio_sms_from:
            channels[ChannelName.SMS] = TwilioChannel(ChannelName.SMS, settings.twilio_account_sid, token,
                                                      settings.twilio_sms_from)
    return channels


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
