from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.app.contracts._base import Contract
from backend.app.contracts.enums import ChannelName


class DeliveryResult(Contract):
    ok: bool
    channel: ChannelName
    provider_message_id: str | None = None
    error: str | None = None


@runtime_checkable
class AlertChannel(Protocol):
    """A way to reach a subscriber. Implementations live in `alerts/channels/`."""

    name: ChannelName

    def send(self, address: str, text: str, audio_url: str | None = None) -> DeliveryResult: ...
