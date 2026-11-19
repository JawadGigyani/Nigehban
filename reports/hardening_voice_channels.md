# Hardening, voice, SMS/WhatsApp, contacts, deployment prep

Built 20 Nov 2026.

## Hardening
- Rate limits per client IP (sliding minute): chat 8, voice 4, advisory 6, subscribe 10, delete 5,
  board login 5, route 20, point check 30, everything else 60; chat also has a global cap of 1,500 a
  day to protect the free LLM keys. Behind a proxy the IP comes from X-Forwarded-For.
- Security headers (nosniff, no-referrer, frame deny, no-store on risk/alerts/inbox); CORS limited to
  the needed methods and headers; `/health` reports missing runtime data.
- Forward-only database migration: new columns are added automatically (SQLite and Postgres).

## Deployment prep
- `Dockerfile` (Hugging Face Spaces, port 7860) and `backend/app/start.py`.
- Runtime data (140 MB: weather history, terrain layers, road tiles, archived forecasts for replays)
  is shipped as a private Hugging Face dataset and downloaded at start
  (`python -m pipelines.deploy.bundle_runtime_data --upload <user>/nigehban-runtime`). No PDMA data,
  events or labels are included; the bundler refuses private paths.
- `.github/workflows/alert-cycle.yml`: runs the alert cycle every 3 hours.
- Postgres driver added for Supabase.

## Urdu voice (ElevenLabs)
- Each new alert gets an Urdu audio file (model `eleven_v3`, language `ur`; `eleven_multilingual_v2`
  and Flash do not support Urdu). Audio is cached by text, cut at 600 characters.
- Citizen app: play button on alerts in the inbox; "Listen" on Urdu chat answers.
- Off until `NIGEHBAN_ELEVENLABS_API_KEY` is set; alerts always go out as text too.

## SMS and WhatsApp
- SMS: adapter for the free, open-source "SMS Gateway for Android" app (an Android phone + SIM sends
  the messages; no sign-up; cloud or local mode). Only the SIM's SMS charges apply.
- WhatsApp: adapter for Meta's Cloud API. Free only with Meta's test number and up to 5 verified
  recipients; real alerts need an approved template and are paid per message in Pakistan. Unofficial
  WhatsApp libraries break WhatsApp's terms and risk the number being banned, so they are not used.

## Shelters and Rescue 1122
- Added the official Rescue 1122 KP district control-room numbers for the 9 candidate districts
  (rescuekp.gov.pk telephone directory). They appear in answers, alerts and the board.
- No public list of station addresses or designated shelters was found: PDMA reports 184 shortlisted
  camp sites but does not publish the list. Shelters stay "unverified" from OpenStreetMap.

## Still open
- Remaining weather months: resumes when the Open-Meteo daily allowance frees up.
- IMERG: needs a free NASA Earthdata account (see the session notes).
