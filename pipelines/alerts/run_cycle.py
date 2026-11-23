"""Run the alert cycle on this machine: once, or every few hours.

    python -m pipelines.alerts.run_cycle                                  # once, live
    python -m pipelines.alerts.run_cycle --every-hours 3                  # keep running (Ctrl+C stops)
    python -m pipelines.alerts.run_cycle --as-of 2025-08-14T09:00:00+05:00   # replay a past day
    python -m pipelines.alerts.run_cycle --no-deliver                     # compute alerts, send nothing

Same engine as POST /internal/run-cycle: risk for every tehsil, fixed rules, de-duplication,
messages, delivery to subscribers. Uses the database in NIGEHBAN_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time

from sqlmodel import Session

from backend.app.alerts.service import get_alert_engine
from backend.app.db.session import get_engine


def run_once(as_of: dt.datetime | None, deliver: bool) -> dict:
    with Session(get_engine()) as session:
        return get_alert_engine().run(session, as_of, deliver).as_dict()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=dt.datetime.fromisoformat, default=None)
    parser.add_argument("--every-hours", type=float, default=None)
    parser.add_argument("--no-deliver", action="store_true")
    args = parser.parse_args()
    while True:
        started = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            print(started, json.dumps(run_once(args.as_of, not args.no_deliver)), flush=True)
        except Exception as exc:  # keep the loop alive; the next run may succeed
            print(started, "cycle failed:", exc, flush=True)
            if not args.every_hours:
                return 1
        if not args.every_hours:
            return 0
        time.sleep(args.every_hours * 3600)


if __name__ == "__main__":
    raise SystemExit(main())
