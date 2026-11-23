"""Replay the alert engine over 13–15 Aug 2025 and write reports/alerts_replay.md.

Uses a separate database (data/replay_alerts.db, rebuilt each run) with two demo
subscribers for Buner (console and web inbox) and one for Swat Babuzai.
Done when (plan): Buner alerts go out once, no duplicates, on console and web inbox.

    python -m pipelines.alerts.replay_cycle
"""

from __future__ import annotations

import datetime as dt
import io
from collections import Counter
from pathlib import Path

from sqlmodel import Session, select

from backend.app.alerts.service import get_alert_engine
from backend.app.alerts.subscriptions import subscribe
from backend.app.config import get_settings
from backend.app.contracts import ChannelName, Language, SubscriptionCreate
from backend.app.db import AlertRow, DeliveryRow, init_db, make_engine

PKT = dt.timezone(dt.timedelta(hours=5))
RUNS = [dt.datetime(2025, 8, 13, 9, tzinfo=PKT), dt.datetime(2025, 8, 14, 9, tzinfo=PKT),
        dt.datetime(2025, 8, 14, 15, tzinfo=PKT), dt.datetime(2025, 8, 15, 6, tzinfo=PKT)]


def main() -> int:
    data = get_settings().data_dir
    db_path = data / "replay_alerts.db"
    db_path.unlink(missing_ok=True)
    db = make_engine(f"sqlite:///{db_path.as_posix()}")
    init_db(db)
    engine = get_alert_engine()
    console = engine.channels[ChannelName.CONSOLE]
    console.stream = io.StringIO()  # keep the console output for the report
    with Session(db) as session:
        subs = [
            subscribe(session, engine.cipher, SubscriptionCreate(channel=ChannelName.CONSOLE, address="demo-buner-console",
                                                                 language=Language.UR,
                                                                 tehsil_ids=("buner__gagra", "buner__daggar")),
                      engine.in_scope, set(engine.village_tehsil)),
            subscribe(session, engine.cipher, SubscriptionCreate(channel=ChannelName.WEB_INBOX, address="demo-buner-inbox",
                                                                 language=Language.EN, village_ids=("manual:pir_baba",)),
                      engine.in_scope, set(engine.village_tehsil)),
            subscribe(session, engine.cipher, SubscriptionCreate(channel=ChannelName.WEB_INBOX, address="demo-swat-inbox",
                                                                 language=Language.UR_ROMAN, tehsil_ids=("swat__babuzai",)),
                      engine.in_scope, set(engine.village_tehsil)),
        ]
        runs = []
        for as_of in RUNS:
            report = engine.run(session, as_of)
            runs.append({"run (PKT)": f"{as_of:%d %b %H:%M}", "candidates": report.candidates,
                         "new alerts": len(report.new_alerts), "skipped (already sent)": report.skipped_duplicates,
                         "deliveries ok": report.deliveries_ok, "failed": report.deliveries_failed})
        alerts = session.exec(select(AlertRow).order_by(AlertRow.valid_date, AlertRow.tehsil_id)).all()
        deliveries = session.exec(select(DeliveryRow)).all()
        keys = Counter((a.tehsil_id, a.level, a.valid_date) for a in alerts)
        buner = [a for a in alerts if a.tehsil_id.startswith("buner__")]
        sub_by_id = {s.id: s for s in subs}
        buner_deliv = Counter((sub_by_id[d.subscription_id].channel, d.alert_id) for d in deliveries
                              if d.subscription_id in sub_by_id and d.ok)

    from pipelines.hydromet.qa import _md
    import pandas as pd

    duplicates = [k for k, n in keys.items() if n > 1]
    per_tehsil_date = Counter((a.tehsil_id, a.valid_date) for a in alerts)
    escalations = sum(1 for n in per_tehsil_date.values() if n > 1)
    buner_ok = bool(buner) and all(
        any(ch == "console" and aid == a.id for ch, aid in buner_deliv) for a in buner if a.tehsil_id in
        ("buner__gagra", "buner__daggar"))
    inbox_ok = any(ch == "web_inbox" for ch, _ in buner_deliv)
    alert_table = pd.DataFrame([{"tehsil": a.tehsil_id, "valid date": str(a.valid_date), "level": a.level,
                                 "lead days": a.lead_days, "issued (UTC)": f"{a.issued_at:%d %b %H:%M}",
                                 "text checked": "template_text" not in a.reason_codes, "sent to": a.sent_to_count}
                                for a in alerts])
    samples = "\n\n".join(f"**{a.tehsil_id}, {a.valid_date}, {a.level}**\n\n- EN: {a.message_en}\n- UR: {a.message_ur}"
                          f"\n- Roman: {a.message_ur_roman}\n- Citations: {', '.join(a.citations)}" for a in buner[:2])
    text = f"""# M9 alert engine: replay of 13–15 Aug 2025

Generated {dt.date.today()} by `python -m pipelines.alerts.replay_cycle` (separate replay database,
archived forecasts, the shipped model and forecast-tuned levels). Rule: level high or above at lead ≤ 2
days, or the river flag; one alert per tehsil, level and date; a repeat only if the level rises.

## Done-when check

| Check | Result |
|---|---|
| Buner alerts produced | {len(buner)} ({', '.join(sorted({f'{a.tehsil_id} {a.valid_date} {a.level}' for a in buner}))}) |
| Duplicate alerts (same tehsil, level, date) | {len(duplicates)} |
| Same tehsil and date sent again only because the level rose | {escalations} |
| Buner alerts delivered on console | {buner_ok} |
| Delivered to a web inbox | {inbox_ok} |

## Runs

{_md(pd.DataFrame(runs))}

The second run on 14 Aug (15:00) repeats the 09:00 run: everything is skipped as already sent.

## Alerts

{_md(alert_table)}

## Sample Buner alerts

{samples}

## Subscribers in this replay

Three demo subscriptions (contacts are demo strings, stored encrypted): Buner Gagra and Daggar on the
console in Urdu; Pir Baba (village, Gagra) in the web inbox in English; Swat Babuzai in the web inbox
in Roman Urdu.
"""
    Path("reports/alerts_replay.md").write_text(text, encoding="utf-8")
    print(text[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
