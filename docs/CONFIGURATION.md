# Configuration

Everything is set in `.env` at the repository root. Start from `.env.example`.

## Run

```bash
python -m uvicorn backend.app.main:app --port 8000    # API
cd frontend && npm run dev                            # website on :3000
```

Check http://localhost:8000/health. It says `ok`, or `degraded` with the data files still to build.

## Run the alert job

```bash
python -m pipelines.alerts.run_cycle                    # once
python -m pipelines.alerts.run_cycle --every-hours 3    # keep running
python -m pipelines.alerts.run_cycle --as-of 2025-08-14T09:00:00+05:00   # replay a past day
python -m pipelines.alerts.run_cycle --no-deliver       # dry run, no voice used
```

Only tehsils someone subscribed to get a message. To run it unattended on Windows, schedule the
`--every-hours 3` command in Task Scheduler.

## Generate secrets once

```bash
python -c "from backend.app.db import generate_keys; print(generate_keys())"   # contact keys
python -c "import secrets; print(secrets.token_urlsafe(32))"                  # internal token
```

Keep the contact keys safe: without them, saved contacts can't be read.

## Settings

All names start with `NIGEHBAN_` unless shown otherwise.

### Essentials

| Setting | Default | What it does |
|:--|:--|:--|
| `NIGEHBAN_BOARD_PASSWORD` | – | Authority board login |
| `NIGEHBAN_CONTACT_ENCRYPTION_KEY` | – | Encrypts subscriber contacts |
| `NIGEHBAN_CONTACT_HASH_KEY` | – | Finds contacts again without decrypting |
| `NIGEHBAN_DATABASE_URL` | SQLite file | Any database URL (Postgres works) |
| `NIGEHBAN_ENVIRONMENT` | `development` | `production` requires the internal token |
| `NIGEHBAN_INTERNAL_TOKEN` | – | Protects the alert-job endpoint |
| `NIGEHBAN_CORS_ALLOW_ORIGINS` | localhost:3000 | Website addresses allowed to call the API |

### Language models

| Setting | Default | What it does |
|:--|:--|:--|
| `GROQ_API_KEY` | – | Main model (free tier works) |
| `GEMINI_API_KEY` | – | Backup model; used first for Urdu |
| `NIGEHBAN_GROQ_API_KEYS`, `NIGEHBAN_GEMINI_API_KEYS` | – | Extra keys, comma-separated, rotated on rate limits |
| `NIGEHBAN_LLM_PROVIDER` | `groq` | Which provider goes first |
| `NIGEHBAN_GEMINI_MODEL` | `gemini-3.5-flash` | Main Gemini model |

### Alerts and voice

| Setting | Default | What it does |
|:--|:--|:--|
| `NIGEHBAN_ALERT_MIN_LEVEL` | `high` | Lowest level that sends an alert |
| `NIGEHBAN_ALERT_MAX_LEAD_DAYS` | `2` | How many days ahead alerts look |
| `NIGEHBAN_RIVER_FLAG_RETURN_PERIOD` | `5` | River flow (years) that raises a river flag |
| `NIGEHBAN_ELEVENLABS_API_KEY` | – | Urdu voice notes (needs the Text to Speech permission) |

### Data and limits

| Setting | Default | What it does |
|:--|:--|:--|
| `NIGEHBAN_EARTHDATA_TOKEN` | – | NASA satellite rain layer |
| `NIGEHBAN_ORS_API_KEY` | – | Optional OpenRouteService routes |
| `NIGEHBAN_RATE_LIMIT_CHAT_PER_MIN` | `8` | Chat requests per minute per IP |
| `NIGEHBAN_RATE_LIMIT_DEFAULT_PER_MIN` | `60` | Other requests per minute per IP |
| `NIGEHBAN_RATE_LIMIT_CHAT_PER_DAY_GLOBAL` | `1500` | Daily chat cap, protects free model quota |

### Website (`frontend/.env.local`)

| Setting | What it does |
|:--|:--|
| `NEXT_PUBLIC_API_URL` | API address (default `http://localhost:8000`) |

## Good to know

- **Weather quota:** Open-Meteo's free tier is plenty; a pacer and cache keep usage low.
- **Model quota:** chat and alerts share the free Groq and Gemini limits; extra keys add capacity.
- **Voice quota:** each alert voice note uses about 150–300 characters of ElevenLabs credit.
- API keys are never written to logs.
