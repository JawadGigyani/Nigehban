# Configuration and running

Nigehban runs on one machine: the FastAPI backend, the Next.js website, a local database, and an
alert cycle you start yourself. All settings come from `.env` in the `nigehban` folder (template:
`.env.example`; defaults in `backend/app/config/settings.py`).

## Running

```powershell
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000   # API
cd frontend; npm run dev                                                           # website on :3000
```

`GET /health` says `"ok"`, or `"degraded"` with the runtime data files that are missing (build them
with the pipelines in [DATA.md](DATA.md)).

## Alert cycle

The cycle computes risk for every tehsil, applies the alert rules, writes the messages and delivers
them to subscribers. Run it on demand or keep it running:

```powershell
.venv\Scripts\python -m pipelines.alerts.run_cycle                         # once, live
.venv\Scripts\python -m pipelines.alerts.run_cycle --every-hours 3         # every 3 hours (Ctrl+C stops)
.venv\Scripts\python -m pipelines.alerts.run_cycle --as-of 2025-08-14T09:00:00+05:00   # replay a past day
.venv\Scripts\python -m pipelines.alerts.run_cycle --no-deliver            # compute, send nothing
```

The same cycle is available over HTTP as `POST /internal/run-cycle` (see [API.md](API.md)). To run it
unattended on Windows, point Task Scheduler at the `--every-hours` command or at a single run every
3 hours.

## First-time secrets

```powershell
.venv\Scripts\python -c "from backend.app.db import generate_keys; print(generate_keys())"   # contact keys
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"            # internal token
```

Keep the contact keys safe: without them, stored phone numbers cannot be read.

## Settings

All variables use the `NIGEHBAN_` prefix unless noted.

### Core

| Variable | Default | Purpose |
|---|---|---|
| `NIGEHBAN_ENVIRONMENT` | `development` | `production` makes the internal token required |
| `NIGEHBAN_DATABASE_URL` | local SQLite (`data/nigehban.db`) | Any SQLAlchemy URL; Postgres works too. Tables are created and migrated at startup |
| `NIGEHBAN_CORS_ALLOW_ORIGINS` | localhost:3000 | Website origins allowed to call the API (JSON list) |
| `NIGEHBAN_BOARD_PASSWORD` | — | Authority board login |
| `NIGEHBAN_INTERNAL_TOKEN` | — | Protects `POST /internal/run-cycle` |
| `NIGEHBAN_CONTACT_ENCRYPTION_KEY`, `NIGEHBAN_CONTACT_HASH_KEY` | — | Encrypt and look up subscriber contacts |
| `NIGEHBAN_LOG_LEVEL` | `INFO` | Logging |

### LLM (LangChain)

| Variable | Default | Purpose |
|---|---|---|
| `NIGEHBAN_LLM_PROVIDER` | `groq` | Primary provider: `groq`, `gemini`, `openai`, `custom` |
| `NIGEHBAN_LLM_FALLBACK_PROVIDERS` | `["gemini"]` | Tried in order when the primary fails or is rate limited |
| `GROQ_API_KEY` / `NIGEHBAN_GROQ_API_KEYS` | — | Main key / extra keys (comma-separated), rotated on rate limits |
| `GEMINI_API_KEY` / `NIGEHBAN_GEMINI_API_KEYS` | — | Same for Gemini |
| `NIGEHBAN_LLM_MODEL`, `NIGEHBAN_GEMINI_MODEL` | provider default | Override models (Groq `openai/gpt-oss-120b`, Gemini `gemini-3.5-flash-lite`) |
| `NIGEHBAN_LLM_COOLDOWN_S`, `NIGEHBAN_LLM_DAILY_COOLDOWN_S` | 120, 3600 | How long a rate-limited key is skipped |

### Alerts and channels

| Variable | Default | Purpose |
|---|---|---|
| `NIGEHBAN_ALERT_MIN_LEVEL` | `high` | Alert at this level or above |
| `NIGEHBAN_ALERT_MAX_LEAD_DAYS` | 2 | Up to this many days ahead |
| `NIGEHBAN_ALERT_FALSE_ALARM_TARGET_PER_SEASON` | 2.5 | Target behind the "High" threshold |
| `NIGEHBAN_RIVER_FLAG_RETURN_PERIOD` | 5 | GloFAS return period (years) that raises the river flag |
| `NIGEHBAN_ELEVENLABS_API_KEY` | — | Urdu voice (ElevenLabs, model `eleven_v3`, Text to Speech permission) |

Alerts are delivered to the web inbox. Other channels (SMS, WhatsApp, browser push) are not built;
see `backend/app/alerts/channels.py` for how one would be added.

### Data and limits

| Variable | Default | Purpose |
|---|---|---|
| `NIGEHBAN_EARTHDATA_TOKEN` | — | NASA IMERG satellite rain (approve "NASA GESDISC DATA ARCHIVE" in Earthdata) |
| `NIGEHBAN_ORS_API_KEY` | — | OpenRouteService routes (optional; built-in OSM router otherwise) |
| `NIGEHBAN_RATE_LIMIT_CHAT_PER_MIN` | 8 | Per IP |
| `NIGEHBAN_RATE_LIMIT_DEFAULT_PER_MIN` | 60 | Per IP, other endpoints |
| `NIGEHBAN_RATE_LIMIT_CHAT_PER_DAY_GLOBAL` | 1500 | Protects the free LLM quota |
| `NIGEHBAN_PDMA_REQUEST_INTERVAL_S` | 2.0 | Scraper politeness (2 s or more) |

### Website (`frontend/.env.local`)

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL (default `http://localhost:8000`) |

## Notes

- **Open-Meteo quota**: live forecasts for all cells cost far less than the free daily limit; the
  pacer and cache keep usage in check. Replays read the local archive in `data/cache/openmeteo/`.
- **LLM quota**: alerts and chat share the Groq/Gemini free quotas; extra keys rotate on rate
  limits, and the daily chat cap protects alert wording.
- API keys are never logged.
