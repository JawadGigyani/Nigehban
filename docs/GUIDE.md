# Nigehban: guide to running, testing and understanding it

Other documents: [Architecture](ARCHITECTURE.md) · [Risk model](MODEL.md) · [Data](DATA.md) · [API](API.md) · [Deployment](DEPLOYMENT.md).

Nigehban gives a flash-flood risk level for each tehsil in northern Khyber Pakhtunkhwa for today
and the next 3 days. It sends Urdu alerts to people who subscribe and gives PDMA, district
administrations and Rescue 1122 a risk board. It supports official warnings and never replaces them.

## 1. Is it complete?

| Part | State |
|---|---|
| Data (PDMA flood events, weather history, terrain, villages, shelters, rivers) | Done |
| Risk model (forecast 1–3 days ahead per tehsil) and backtest | Done, gate G2 passed |
| Alert engine (rules, Urdu / English / Roman Urdu text, voice, de-duplication) | Done |
| Public website (English and Urdu; desktop and phone, with motion) and authority board | Done |
| Ask Nigehban (grounded Q&A agent), place check, route to safety, advisory drafts | Done |
| Satellite rain layer on the board (NASA IMERG) | Done |
| Security hardening (rate limits, headers, encrypted contacts, board login) | Done |
| Channels that work today | Web inbox, browser push, console, voice audio |
| SMS | Code done (SMS.to, Android SMS Gateway, Twilio); needs a paid or phone route |
| WhatsApp | Code done (Meta Cloud API, Twilio); needs a Meta test number |
| Deployment (Hugging Face Spaces + Vercel + Supabase + GitHub cron) | Prepared, not yet deployed |
| Demo pack (method note, script, results) | Last step |
| Weather history for non-monsoon months (`--scope all`) | Optional, 13/35 chunks; the app does not need it |

**In short:** the application is built and runs end to end on your computer. What remains is
putting it online (deployment), choosing an SMS/WhatsApp route, and the demo pack.

## 2. Run it yourself (Windows, PowerShell)

You need Python 3.11 and Node.js 18+ installed. Everything below is run from
`H:\AIChallenge26\nigehban`.

### First time only

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
cd frontend; npm install; cd ..
```

`.env` already has your keys. The board password is `NIGEHBAN_BOARD_PASSWORD` in `.env`.

### Every time: two terminals

Terminal 1, the API (backend):

```powershell
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. Check http://127.0.0.1:8000/health: it should say
`"status": "ok"`. The API docs (every endpoint, with a "Try it out" button) are at
http://127.0.0.1:8000/docs.

Terminal 2, the web app (frontend):

```powershell
cd frontend; npm run dev
```

Open:

- http://localhost:3000 for the public website. Pages: Home, Risk map, My area, Ask, Alerts,
  Safety guide. It also works on a phone-size window (F12, then the phone icon).
- http://localhost:3000/board for the authority board (log in with the board password).

In the Claude app you can also start both from the Browser pane: they are the `api` and `web`
entries in `.claude/launch.json`.

### Run the tests

```powershell
.venv\Scripts\python -m pytest -q
```

Expected: about 192 passed, 5 skipped (the skipped ones need live keys). Live LLM tests are opt-in:

```powershell
$env:NIGEHBAN_RUN_LIVE="1"; .venv\Scripts\python -m pytest -m live; Remove-Item Env:NIGEHBAN_RUN_LIVE
```

## 3. A 15-minute test walkthrough

It is November, so live risk is almost all "Low". Use the **replays**. They rerun the system
with the forecasts exactly as they were issued before real floods, with no knowledge of what
happened next.

### A. Board: the Buner cloudburst (15 Aug 2025)

1. Open `/board` and log in.
2. In the top bar choose **Replay: 14 Aug 2025 (Buner cloudburst eve)**.
3. Click the day buttons (Thu 14 Aug … Sun 17 Aug). The map and the counts change by day.
4. Click a coloured tehsil (for example Buner Daggar or Swat Babuzai). The side panel shows:
   - its level for each day and **why** (for example "rain over 3 days: 56 mm", "wet topsoil");
   - villages on low ground near big streams (high / medium / low exposure);
   - shelters and higher ground, Rescue 1122 stations, the district control-room number;
   - river flow forecast against the 2-year flow.
5. Click **Draft advisory for high-risk tehsils**. A ready-to-print advisory appears: a risk table,
   actions checked against the evidence, a public message in English and Urdu, and sources.
   Use **Copy text** or **Print**.
6. Click **Satellite rain** at the top left of the map. Blue squares show rain that NASA
   satellites measured on the day before the replay date. The darker the blue, the more rain;
   purple is 60 mm or more. The side list shows the wettest tehsils. Switch back with
   **Forecast risk**.
   - Tip: choose the date **15 Aug 2025** in "or date" to see the 14 Aug storm (60–80 mm over
     Swat, Shangla, Battagram).
7. **Alerts sent (replay)** at the bottom lists alerts the engine produced for that replay.
8. Also try **Replay: 26 Jun 2025 (Swat River flood eve)**, or any date from 1 Mar 2024.

### B. Public website

1. Open http://localhost:3000. It opens in English; switch to **اردو** in the header.
   The choice is remembered.
2. Click the **Live** pill in the header and choose **14 Aug 2025 · Buner cloudburst**. A yellow bar
   says you are viewing a past forecast; every page now shows that day. **Back to live** undoes it.
3. **Home**: the map shows each tehsil's level. Switch days (Today, Tomorrow, …) and switch to
   **Satellite rain**. The card on the map shows the highest-risk tehsil; click any tehsil to see
   its card, then **See details**. The counts under the map, the feature cards, "How Nigehban
   works", and the safety band follow.
4. **Search** on Home (for example "Mingora", "Pir Baba", "Daggar") or click **Use my location**:
   it opens **My area** with the 4-day levels, what to do, the reasons, villages on low ground,
   nearby safer places, Rescue 1122 and the district control room. **Am I in a danger zone?**
   checks the exact point and, if it is low ground by a river, gives a walking route to higher
   ground. **Get alerts** adds the place to your alerts.
5. **Risk map**: a full-screen map with a filterable ranked list; click a tehsil for its levels,
   reasons, exposure, river flow and satellite rain.
6. **Ask**: click a suggested question or type one, in Urdu or English, for example:
   - "کیا کل سوات میں سیلاب کا خطرہ ہے؟"
   - "What should I do if water enters my house?"
   Answers use only Nigehban's own data and official guidance and list their sources. In Urdu,
   **Listen** plays the answer (ElevenLabs voice).
7. **Alerts**: add places and **Subscribe to alerts** (web inbox, no phone number needed). Then
   start an alert cycle for the replay date. In a third terminal:

   ```powershell
   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/internal/run-cycle -ContentType "application/json" -Body '{"as_of":"2025-08-14T09:00:00+05:00"}'
   ```

   If your place is at high or above within 2 days, the alert appears in the inbox in your
   language, with a play button for the Urdu voice message. Run the command again: no
   duplicate is sent. This also works from http://127.0.0.1:8000/docs. **Stop alerts** and
   **Delete all my data** are on the same page.
8. **Safety guide**: before / during / after advice and the emergency numbers (1122, PDMA 1700).

### C. Command-line checks (optional)

```powershell
.venv\Scripts\python -m pipelines.alerts.replay_cycle   # Buner 13–15 Aug 2025 -> reports/m9_alerts_replay.md
.venv\Scripts\python -m pipelines.backtest.run          # how many past floods were caught -> reports/m7_backtest.md
.venv\Scripts\python -m pipelines.alerts.send_test --channel sms --to +92XXXXXXXXXX   # once an SMS route is set
```

## 4. How it works

```
 Open-Meteo forecasts (ECMWF, GFS, ICON)     NASA IMERG satellite rain (observed, board layer only)
 Open-Meteo GloFAS river flow                       |
        |                                           v
        v                                  "Satellite rain" map layer
 Weather per tehsil (0.25° cells, area-weighted) ---+
        |                                           |
        v                                           |
 Risk model (logistic regression, 7 inputs) <-- terrain + PDMA flood history (training)
        |   per tehsil, lead 0–3 days, level low / moderate / high / very high, with reasons
        v
 +--------------------+-------------------------+----------------------+
 | Alert engine       | Website + board         | Ask Nigehban agent   |
 | rules, dedupe,     | maps, details, routes,  | LangGraph: understand|
 | Urdu/English/Roman | advisory drafts         | -> locate -> gather  |
 | text, voice        |                         | -> compose -> check  |
 +--------------------+-------------------------+----------------------+
        |
        v
 Web inbox, browser push, (SMS, WhatsApp when a route is set)
```

### The pieces, one by one

1. **Flood history (M1).** 8,000+ PDMA KP daily situation reports were downloaded politely,
   read by an LLM into a fixed form (date, tehsil, village, river, damage), geocoded to tehsils
   and merged. This gives the flood days the model learns from. Names are removed and the raw
   reports never leave your computer (gitignored).
2. **Weather (M2).** Each tehsil is covered by 0.25° weather cells, weighted by area. For every
   day we keep rain (tehsil average and wettest cell), 3- and 7-day rain, soil moisture and
   temperature, from ERA5 (past) and the ECMWF / GFS / ICON forecasts (live and as issued in the past).
3. **Terrain (M3) and places (M4b).** From a 90 m elevation model (30 m for Swat) we compute
   "height above the nearest stream" and how big each stream is. A village on ground less than
   5 m above a large stream is "high exposure". Shelters (schools, mosques, health sites),
   higher ground and Rescue 1122 come from OpenStreetMap and official directories, and are
   marked unverified.
4. **Risk model (M5).** A calibrated logistic regression on 7 inputs (rain amounts, wet soil,
   terrain exposure). We compared it with LightGBM, random forest and others: the simple model
   generalised best with 89 flood days. Each forecast model (ECMWF, GFS, ICON) is run and the
   results averaged. Level thresholds are tuned per lead day so false alarms stay near the
   target. Every level comes with the reasons that pushed it up.
5. **Rivers (M6).** GloFAS river flow forecasts for points on the main rivers. A flag is raised
   when the flow is forecast above the 2-year flood. It never lowers a level.
6. **Backtest (M7).** On real archived forecasts for 2024–2025 the system caught 22 of 41 flood
   events, against 16 for a plain rain threshold at the same false-alarm rate; 19 were caught
   3 days ahead.
7. **Ask Nigehban (M8).** A LangGraph agent. It works out what you are asking and where, gathers
   evidence (risk, exposure, facilities, PDMA/NDMA guidance from a search index, contacts),
   writes an answer, then checks it: every claim must point to evidence, and Urdu place names
   come from a fixed table. If the check fails twice it falls back to a safe template. It uses
   LangChain with Groq first and Gemini as backup.
8. **Alerts (M9).** Each cycle (every 3 hours when deployed) the engine alerts subscribers when
   their tehsil is high or above within 2 days, or the river flag is raised. It sends once per
   tehsil, level and date and only again if the level goes up. Text is written by the LLM in
   Urdu, English and Roman Urdu, then checked by code (level, place, date). A short plain SMS
   version is built by code. The Urdu message is also turned into audio (ElevenLabs).
   Contacts are encrypted; phone numbers are never shown back.
9. **Website and board (M12/M13).** The public website has six pages (Home, Risk map, My area,
   Ask, Alerts, Safety guide) in English and Urdu (Nastaliq, right-to-left), with a
   Live / Replay switch in the header. The board is English, behind a password, with replays.
10. **Place check, routes, advisories (M10/M11/F11).** Point danger check from terrain; walking
    or driving route to safety on OpenStreetMap roads, avoiding low ground; advisory drafts for
    officials, with actions checked against the evidence.
11. **Satellite rain layer.** NASA IMERG rain already fallen, per 0.1° cell (about 11 km). We
    tested it as a model input: it helps only on the day itself, after the rain, so it is shown
    as an observed layer and kept out of the forecast. See `reports/imerg_vs_era5.md`.

## 5. Where things are

```
backend/app/
  api/         HTTP endpoints (risk, geo, chat, alerts, voice)
  hydromet/    weather, rivers, IMERG satellite rain, nowcast
  risk/        risk model and its saved artefacts
  agent/       Ask Nigehban (LangGraph)
  knowledge/   search index of official guidance
  alerts/      rules, composer, channels, voice, advisory
  geo/         danger check, routing, contacts, Urdu names
  db/          database tables (SQLite locally, Postgres when deployed)
frontend/      Next.js website (/, /map, /area, /ask, /alerts, /safety) and board (/board)
pipelines/     offline jobs that build data, train and evaluate
reports/       results of each step (QA, model, backtest, alerts, IMERG)
tests/         automated tests
data/          reference data (small files in git; large and private data gitignored)
```

Useful reports: `m5_risk_qa.md` (model choice), `m7_backtest.md` (floods caught),
`m9_alerts_replay.md` (Buner alert replay), `imerg_vs_era5.md` (satellite rain),
`hardening_voice_channels.md` (security, voice, channels).

## 6. API endpoints (for reference)

| Endpoint | What it does |
|---|---|
| `GET /health` | Is everything loaded |
| `GET /geo/tehsils` | Tehsil boundaries |
| `GET /risk?as_of=` | Level for every tehsil, days 0–3 (as_of = replay) |
| `GET /tehsils/{id}` | Detail: exposure, shelters, Rescue 1122, rivers |
| `GET /places/search?q=` | Find a village or town |
| `POST /geo/check` | Is this point in a danger zone, and what to do |
| `POST /route/shelter` | Route to the nearest safer place |
| `POST /chat` | Ask Nigehban |
| `POST /subscriptions`, `DELETE /subscriptions/{id}`, `POST /me/delete` | Alerts sign-up and data deletion |
| `GET /inbox/{id}` | Web inbox |
| `GET /rain/observed?as_of=` | Satellite rain already fallen |
| `POST /board/login`, `GET /alerts`, `POST /advisories/draft` | Board (password) |
| `POST /internal/run-cycle` | Run one alert cycle (token when deployed) |
| `POST /tts`, `GET /audio/{key}.mp3` | Urdu voice |

## 7. Limits to say out loud

- Risk is per tehsil, not per house. Some floods will be missed (about half in the backtest),
  and some alerts will be false.
- Shelters and higher ground come from maps and are unverified.
- Forecasts are only as good as the weather models; local cloudbursts are the hardest case.
- Nigehban supports PDMA and district warnings; people should follow official instructions.
