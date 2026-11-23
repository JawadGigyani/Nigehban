# Deployment

Nigehban runs on free tiers:

| Part | Host | Notes |
|---|---|---|
| Backend (FastAPI) | Hugging Face Spaces, Docker | `Dockerfile`, port 7860, entry `python -m backend.app.start` |
| Runtime data (~140 MB) | Private Hugging Face dataset | Downloaded into `data/` at startup when missing |
| Database | Supabase Postgres | SQLite locally; tables are created and migrated at startup |
| Website and board | Vercel | Root directory `nigehban/frontend` |
| Alert cycle | GitHub Actions | `.github/workflows/alert-cycle.yml`, every 3 hours |

Status: prepared, not yet deployed. The Docker image has not been built locally yet (Docker is not
installed on the development machine), so the first Space build is its first test.

## Steps

1. **Secrets ready.** Generate the values you will need:

   ```powershell
   .venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"            # NIGEHBAN_INTERNAL_TOKEN
   .venv\Scripts\python -c "from backend.app.db import generate_keys; print(generate_keys())"   # contact keys
   .venv\Scripts\python -m backend.app.alerts.channels --vapid                            # web push keys
   ```

   Choose a strong `NIGEHBAN_BOARD_PASSWORD`. Keep the contact keys safe: without them stored
   phone numbers cannot be read.

2. **Runtime data.** Create a private dataset on Hugging Face (for example
   `<user>/nigehban-runtime`) and a write token, then:

   ```powershell
   $env:HF_TOKEN="<write token>"; .venv\Scripts\python -m pipelines.deploy.bundle_runtime_data --upload <user>/nigehban-runtime; Remove-Item Env:HF_TOKEN
   ```

3. **Database.** Create a Supabase project and copy the Postgres connection string (session
   pooler) into `NIGEHBAN_DATABASE_URL`.

4. **Backend.** Create a Hugging Face Space (SDK: Docker), push this repository's `nigehban`
   folder to it, and add the backend settings below as Space secrets, including
   `NIGEHBAN_ENVIRONMENT=production`, `NIGEHBAN_RUNTIME_DATA_REPO` and a read `HF_TOKEN`. Check
   `https://<user>-<space>.hf.space/health` returns `"status": "ok"`.

5. **Website.** Import the GitHub repository in Vercel with root directory `nigehban/frontend`.
   Set `NEXT_PUBLIC_API_URL` to the Space URL and `NEXT_PUBLIC_VAPID_PUBLIC_KEY` to the VAPID
   public key. Then add the Vercel domain to the backend's `NIGEHBAN_CORS_ALLOW_ORIGINS`.

6. **Alert cycle.** In the GitHub repository settings add the secrets `NIGEHBAN_API_URL` (the Space
   URL) and `NIGEHBAN_INTERNAL_TOKEN`. Run the `alert-cycle` workflow once by hand to check it.

7. **Check.** Open the website, look up a place, ask a question, subscribe with the web inbox, log
   in to `/board`, and confirm the workflow run shows `new_alerts` and `deliveries_ok`.

## Backend settings

All variables use the `NIGEHBAN_` prefix unless noted. Defaults are in
`backend/app/config/settings.py`; a template is in `.env.example`.

### Core

| Variable | Default | Purpose |
|---|---|---|
| `NIGEHBAN_ENVIRONMENT` | `development` | `production` makes the internal token required |
| `NIGEHBAN_DATABASE_URL` | local SQLite | Postgres URL when deployed |
| `NIGEHBAN_CORS_ALLOW_ORIGINS` | localhost:3000 | Website origins allowed to call the API (JSON list) |
| `NIGEHBAN_BOARD_PASSWORD` | — | Authority board login |
| `NIGEHBAN_INTERNAL_TOKEN` | — | Protects `/internal/run-cycle` |
| `NIGEHBAN_CONTACT_ENCRYPTION_KEY`, `NIGEHBAN_CONTACT_HASH_KEY` | — | Encrypt and look up subscriber contacts |
| `NIGEHBAN_RUNTIME_DATA_REPO`, `HF_TOKEN` | — | Private dataset with the runtime data |
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
| `NIGEHBAN_VAPID_PUBLIC_KEY`, `NIGEHBAN_VAPID_PRIVATE_KEY` | — | Browser notifications |
| `NIGEHBAN_ELEVENLABS_API_KEY` | — | Urdu voice (ElevenLabs, model `eleven_v3`, Text to Speech permission) |
| `NIGEHBAN_SMSTO_API_KEY`, `NIGEHBAN_SMSTO_SENDER_ID` | — | SMS through SMS.to |
| `NIGEHBAN_SMS_GATEWAY_URL`, `_USERNAME`, `_PASSWORD` | cloud URL | SMS through the open-source SMS Gateway for Android app |
| `NIGEHBAN_TWILIO_ACCOUNT_SID`, `_AUTH_TOKEN`, `_SMS_FROM` | — | Twilio SMS and WhatsApp sandbox (used instead of the above when set) |
| `NIGEHBAN_WHATSAPP_TOKEN`, `NIGEHBAN_WHATSAPP_PHONE_NUMBER_ID`, `NIGEHBAN_WHATSAPP_TEMPLATE` | — | WhatsApp Cloud API (Meta) |
| `NIGEHBAN_TELEGRAM_BOT_TOKEN` | — | Development only (Telegram is blocked in Pakistan) |

Test a channel: `python -m pipelines.alerts.send_test --channel sms --to +92XXXXXXXXXX`.

### Data and limits

| Variable | Default | Purpose |
|---|---|---|
| `NIGEHBAN_EARTHDATA_TOKEN` | — | NASA IMERG satellite rain (approve "NASA GESDISC DATA ARCHIVE" in Earthdata) |
| `NIGEHBAN_ORS_API_KEY` | — | OpenRouteService routes (optional; built-in OSM router otherwise) |
| `NIGEHBAN_RATE_LIMIT_CHAT_PER_MIN` | 8 | Per IP |
| `NIGEHBAN_RATE_LIMIT_DEFAULT_PER_MIN` | 60 | Per IP, other endpoints |
| `NIGEHBAN_RATE_LIMIT_CHAT_PER_DAY_GLOBAL` | 1500 | Protects the free LLM quota |
| `NIGEHBAN_PDMA_REQUEST_INTERVAL_S` | 2.0 | Scraper politeness (2 s or more) |

## Frontend settings

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL |
| `NEXT_PUBLIC_VAPID_PUBLIC_KEY` | Same public key as the backend, for browser notifications |

## Operating notes

- **Free Space sleeps** when idle; the workflow wakes it with `/health` before each cycle.
- **Open-Meteo quota**: live forecasts for all cells cost far less than the daily limit; the
  pacer and cache keep usage in check. Replays read the bundled archive.
- **LLM quota**: alerts and chat share the Groq/Gemini free quotas; extra keys rotate on rate
  limits, and the daily chat cap protects alert wording.
- **Logs**: the Space log shows startup (runtime data download), each cycle, and channel errors.
  API keys are never logged.
