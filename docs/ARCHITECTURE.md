# Architecture

## Overview

```
                 ┌──────────────────────── external data ────────────────────────┐
                 │ Open-Meteo: ECMWF / GFS / ICON forecasts, ERA5, GloFAS rivers  │
                 │ NASA IMERG satellite rain · ElevenLabs voice · Groq / Gemini   │
                 └───────────────┬───────────────────────────────┬────────────────┘
                                 │                               │
 offline pipelines ──► data/ ──► │  FastAPI backend (backend/app) │
 (events, terrain,               │                               │
  training, index)               ▼                               ▼
                         hydromet ──► risk ──► alerts ──► channels (web inbox, push, SMS, WhatsApp)
                            │          │  │       │
                            │          │  └──► agent (LangGraph) ◄── knowledge (BM25 index)
                            │          │                 │
                            ▼          ▼                 ▼
                         geo (danger check, routing, contacts)      db (SQLModel: SQLite / Postgres)
                                 │
                                 ▼  HTTP (JSON)
                 Next.js frontend: public website + authority board
                                 ▲
   pipelines.alerts.run_cycle ───┘  (or POST /internal/run-cycle), e.g. every 3 hours
```

One Python backend serves everything. The website and board call it over HTTP. The alert cycle
runs from `python -m pipelines.alerts.run_cycle` (once or every few hours) or the internal endpoint.

## Components

| Component | Folder | Role |
|---|---|---|
| Contracts | `backend/app/contracts/` | Pydantic v2 models shared by every module (levels, forecasts, alerts, subscriptions) |
| Config | `backend/app/config/` | Settings from `.env` (prefix `NIGEHBAN_`); see [CONFIGURATION.md](CONFIGURATION.md) |
| Hydromet | `backend/app/hydromet/` | Weather per tehsil: Open-Meteo client with a request pacer and disk cache, 0.25° grid with area weights, daily and rolling features, river monitor (GloFAS), IMERG satellite rain and nowcast |
| Risk | `backend/app/risk/` | Feature matrix, the trained model (`artifacts/v1/`), per-lead levels, drivers (reasons), 3-model ensemble, river flag, replays |
| Geo | `backend/app/geo/` | Tehsil locator, point danger check (HAND terrain rasters), safe routing on OSM roads, Rescue 1122 contacts, fixed Urdu names |
| Knowledge | `backend/app/knowledge/` | BM25 search over PDMA, NDMA and NIH guidance (`index/passages.jsonl.gz`) |
| Agent | `backend/app/agent/` | Ask Nigehban: LangGraph graph understand → locate → gather → compose → validate, with retries and a template fallback |
| LLM | `backend/app/llm/` | LangChain chat models (Groq first, Gemini fallback), key rotation with cooldowns, structured output |
| Alerts | `backend/app/alerts/` | Rules, de-duplication, trilingual message composer with code checks, channels, voice (ElevenLabs), advisory drafts, subscriptions |
| DB | `backend/app/db/` | SQLModel tables (subscriptions with encrypted contacts, alerts, deliveries); SQLite by default, Postgres supported |
| API | `backend/app/api/` | FastAPI routers: risk, geo, chat, alerts, voice; see [API.md](API.md) |
| Middleware | `backend/app/middleware.py` | Security headers and per-IP rate limits (stricter for chat, plus a daily global chat cap) |
| Runtime data | `backend/app/runtime_data.py` | List of data files the backend needs; `/health` reports missing ones |
| Frontend | `frontend/` | Next.js 15 website and board, MapLibre map; see [frontend/README.md](../frontend/README.md) |
| Pipelines | `pipelines/` | Offline jobs that build data, train and evaluate; see [DATA.md](DATA.md) |

## Main flows

### Risk for a day

1. `HydrometService` fetches forecasts for every 0.25° cell over the area (batches of 40 cells,
   all three models in each request), caches them, and turns hourly values into daily per-tehsil features (area-weighted
   mean and wettest cell, 3-day and 7-day rain, soil moisture).
2. `RiskService` builds the 7-feature matrix for each forecast model (ECMWF, GFS, ICON), scores it
   with the calibrated logistic model, and averages the three probabilities.
3. Fixed per-lead thresholds (`artifacts/v1/forecast_levels.json`) turn the probability into a
   level. If a river point serving the tehsil is forecast at or above the 5-year GloFAS flow, the
   day carries a river flag: it triggers alerts on its own, and the point check treats the day as
   at least Moderate. The flag never lowers a level.
4. Drivers: for each feature, how much the log-odds drop when it is set to its typical value. The
   top ones become the plain-language reasons ("heavy rain forecast", "ground already wet").
5. Results are cached per issue date. A replay (`as_of` in the past) uses the forecasts exactly as
   issued then (Open-Meteo previous runs), so it never sees what happened next.

### Alert cycle

1. `pipelines.alerts.run_cycle` (or `POST /internal/run-cycle`, token protected) computes risk for
   all tehsils.
2. Rules: alert when a tehsil is High or above within 2 days, or the river flag is raised.
3. De-duplication: one alert per tehsil, level and date; a new alert only if the level goes up.
4. The composer asks the LLM for the message in Urdu, English and Roman Urdu, then checks in code
   that the level, place and date are right and that Urdu place names match the fixed table. On
   failure it uses a template.
5. A short plain SMS text is built in code. The Urdu message is turned into audio.
6. Each subscriber gets the alert on their channel in their language; deliveries are recorded.

### Ask Nigehban

1. **Understand**: the LLM extracts intent, place, day and language (Urdu script is detected in
   code).
2. **Locate**: the place is matched to a district, tehsil or village (exact names first; district
   names resolve to the district's main town; fuzzy matching only above a strict score).
3. **Gather**: evidence items, each with an id: model risk for each day, exposed villages, nearby
   shelters and higher ground, Rescue 1122 contacts, and guidance passages from the knowledge
   index.
4. **Compose**: the LLM answers only from the evidence and cites ids.
5. **Validate**: every cited id must exist; the stated level must equal the model's level; Urdu
   names are fixed. Up to 2 retries with the reason, then a template answer built from the
   evidence. The closing line ("Follow PDMA and district administration instructions") is added
   by code.

### Danger check and route

`/geo/check` reads the HAND rasters (height above the nearest stream; 30 m for Swat, 90 m
elsewhere) around the point: low ground beside a stream draining at least 50 km² is a danger
zone. Combined with the model's level for today and tomorrow it gives one of four advice codes.
`/route/shelter` finds the nearest shelter or higher ground and routes on OSM roads with
networkx, penalising low ground five times (OpenRouteService is used instead if a key is set).

## Code map

```
backend/app/
  main.py               app factory: middleware, routers, /health
  api/risk.py           /geo/tehsils, /risk, /tehsils/{id}, /places/search, /board/login
  api/geo.py            /geo/check, /route/shelter, /advisories/draft, /rain/observed
  api/chat.py           /chat
  api/alerts.py         /internal/run-cycle, /subscriptions, /me/delete, /inbox, /alerts
  api/voice.py          /audio/{key}.mp3, /tts, /config
  hydromet/client.py    Open-Meteo client, RatePacer, ResponseCache
  hydromet/features.py  daily, rolling and climatology features
  hydromet/service.py   live and replay features per tehsil
  hydromet/rivers.py    GloFAS river readings and return periods
  hydromet/imerg.py     NASA IMERG client and per-tehsil values
  hydromet/nowcast.py   observed-rain layer (live or replay)
  risk/features.py      feature lists and matrix
  risk/service.py       RiskModel, RiskService, drivers
  agent/graph.py        LangGraph graph and checks
  agent/service.py      AgentContext (place lookup, evidence), ChatAgent
  alerts/rules.py       alert rules and de-duplication
  alerts/composer.py    trilingual message with code checks
  alerts/cycle.py       one alert cycle; SMS text; voice hook
  alerts/channels.py    web inbox, web push, SMS.to, SMS Gateway, Twilio, WhatsApp, console
  alerts/advisory.py    advisory drafts for the board
  geo/danger.py         point danger check
  geo/routing.py        road tiles, low-ground penalty, SafeRouter
frontend/src/
  app/(site)/           public pages and shared layout
  app/board/            authority board
  components/RiskMap.tsx, components/site/*
  lib/api.ts, lib/site.tsx, lib/copy.ts, lib/i18n.ts, lib/hooks.ts
```

## Key decisions

| Decision | Why |
|---|---|
| Tehsil as the unit | PDMA reports name tehsils or villages; the weather grid is 0.25° (~25 km). A per-house risk would claim precision the inputs don't have. |
| Logistic regression on 7 features | With 89 tehsil-level flood days, tree models (LightGBM, XGBoost, random forest) overfit. The simple model generalised best on held-out seasons and districts ([MODEL.md](MODEL.md)). |
| Levels from fixed thresholds, never the LLM | A warning must be reproducible and auditable. The LLM writes words only, and code checks them. |
| Levels tuned on forecasts, per lead day | Levels tuned on ERA5 (rain that fell) fired too rarely on real forecasts. |
| 3-model ensemble | ECMWF, GFS and ICON disagree on local storms; averaging is steadier than any one. |
| River flag never lowers a level | GloFAS adds no extra hits in the backtest, but a high river is still worth an alert and a "be ready". |
| Satellite rain (IMERG) not a model input | Same-day IMERG helps, but it exists only after the rain falls; past days add nothing. Shown as an observed layer instead. |
| Evidence ids in every answer | Lets code verify that an answer is grounded, and lets users see sources. |
| Fixed Urdu names table | LLMs misspell local names; place names come from `data/reference/urdu_names.csv`. |
| Contacts encrypted | Phone numbers are Fernet-encrypted and looked up by keyed hash; they are never returned by the API. |
| Free data and models | Open-Meteo, NASA IMERG and Groq/Gemini free quotas: the system runs without a budget. A request pacer and caches keep within quotas. |

## Tech stack

Python 3.11, FastAPI, Pydantic v2, SQLModel, LangChain and LangGraph, scikit-learn, pandas,
rasterio, pysheds, shapely, networkx, pyosmium, rapidfuzz, httpx. Next.js 15, React 19, MapLibre
GL 4.7, TypeScript. SQLite by default (Postgres supported).
