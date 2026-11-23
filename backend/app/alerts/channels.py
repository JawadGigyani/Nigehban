"""Delivery channels.

- web_inbox: nothing to send; the delivery row makes the alert appear in the user's inbox in the
  web app (GET /inbox/{subscription_id}). This is the channel the website uses.
- console: prints the alert (logs, local runs, tests).

Other channels (SMS, WhatsApp, browser push, a mobile app) are not built. Each can be integrated as
one class with `name` and `send(address, text, audio_url) -> DeliveryResult`, registered in
`build_channels` and added to `ChannelName`; the alert cycle, de-duplication, encrypted contacts and
delivery records already work for any channel.
"""

from __future__ import annotations

import logging
import sys

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


def build_channels(settings=None) -> dict[ChannelName, object]:
    return {ChannelName.CONSOLE: ConsoleChannel(), ChannelName.WEB_INBOX: WebInboxChannel()}
