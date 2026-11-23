# Security hardening, Urdu voice, and Rescue 1122 contacts

Built 20 Nov 2026; updated 23 Nov 2026 (delivery is the in-app inbox only).

## Hardening
- Rate limits per client IP (sliding minute): chat 8, voice 4, advisory 6, subscribe 10, delete 5,
  board login 5, route 20, point check 30, everything else 60; chat also has a global cap of 1,500 a
  day to protect the free LLM keys. Behind a reverse proxy the IP comes from X-Forwarded-For.
- Security headers (nosniff, no-referrer, frame deny, no-store on risk/alerts/inbox); CORS limited to
  the needed methods and headers; `/health` reports missing runtime data.
- Forward-only database migration: new columns are added automatically (SQLite and Postgres).
- Subscriber contacts are Fernet-encrypted and looked up by keyed hash; the API never returns them.

## Urdu voice (ElevenLabs)
- Each new alert gets an Urdu audio file (model `eleven_v3`, language `ur`; `eleven_multilingual_v2`
  and Flash do not support Urdu). Audio is cached by text, cut at 600 characters. Dry runs of the
  alert cycle (`--no-deliver`) skip voice so no quota is spent.
- Website: play button on alerts in the inbox; "Listen" on Urdu answers in Ask Nigehban.
- Off until `NIGEHBAN_ELEVENLABS_API_KEY` is set; alerts always have text too.

## Delivery
- Alerts are delivered to the in-app web inbox. SMS, WhatsApp, browser push or a mobile app can be
  integrated as one channel class each (`backend/app/alerts/channels.py`); rules, de-duplication,
  encrypted contacts and delivery records already work for any channel.

## Shelters and Rescue 1122
- Added the official Rescue 1122 KP district control-room numbers for the 9 covered districts
  (rescuekp.gov.pk telephone directory). They appear in answers, alerts and the board.
- No public list of station addresses or designated shelters was found: PDMA reports 184 shortlisted
  camp sites but does not publish the list. Shelters stay "unverified" from OpenStreetMap.
