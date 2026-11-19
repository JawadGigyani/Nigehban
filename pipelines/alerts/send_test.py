"""Send one test message on a channel, to check keys and delivery.

    python -m pipelines.alerts.send_test --channel sms --to +923001234567
    python -m pipelines.alerts.send_test --channel whatsapp --to +923001234567

Uses the same channel set-up as the alert engine (keys from .env). Prints only the result.
"""

from __future__ import annotations

import argparse

from backend.app.alerts.channels import build_channels
from backend.app.config import get_settings
from backend.app.contracts import ChannelName

TEXT = ("نگہبان: یہ ایک آزمائشی پیغام ہے۔ Nigehban test message: flash-flood alerts are working. "
        "Follow PDMA and district administration instructions.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, choices=[c.value for c in ChannelName])
    parser.add_argument("--to", required=True, help="phone number, e.g. +923001234567")
    args = parser.parse_args()
    channel = build_channels(get_settings())[ChannelName(args.channel)]
    result = channel.send(args.to, TEXT)
    print(f"{args.channel} via {channel.__class__.__name__}: {'sent' if result.ok else 'FAILED'}"
          f"{'' if result.ok else ' - ' + str(result.error)}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
