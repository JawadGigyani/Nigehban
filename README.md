# Nigehban (نگہبان)

[![ci](https://github.com/JawadGigyani/Nigehban/actions/workflows/ci.yml/badge.svg)](https://github.com/JawadGigyani/Nigehban/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB)
![Next.js 15](https://img.shields.io/badge/Next.js-15-000000)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**Flash-flood early warning for northern Khyber Pakhtunkhwa, Pakistan.** Nigehban gives each of 48
tehsils a flash-flood risk level for today and the next three days, explains why, and tells people
what to do, in English and Urdu. It is a full-stack web app: a calibrated risk model on live weather
forecasts, a grounded question-answering agent, an alert engine with an in-app inbox, and a risk
board for authorities.

![Home page during the 14 Aug 2025 replay, the day before the Buner cloudburst](docs/images/home.png)

> Nigehban is guidance, not an official warning. Risk is estimated per tehsil, not per house, and
> some floods will be missed.

## Features

| | |
|---|---|
| **Risk per tehsil, 3 days ahead** | Low / Moderate / High / Very high for days 0–3, from a calibrated model averaged over the ECMWF, GFS and ICON forecasts, with plain-language reasons ("heavy rain forecast", "ground already wet") |
| **Am I in a danger zone?** | Checks a point against height-above-stream terrain (30 m in Swat, 90 m elsewhere) and gives a walking route to the nearest higher ground or shelter on OpenStreetMap roads |
| **Ask Nigehban** | Questions in Urdu or English, answered only from Nigehban's data and PDMA/NDMA/NIH guidance; every claim cites evidence and is checked in code before it is shown; Urdu voice playback |
| **Alerts** | Fixed rules (High or above within 2 days), no duplicates, messages in English and Urdu checked in code, Urdu voice notes, delivered to an in-app inbox; contacts encrypted, delete-my-data built in |
| **Authority board** | Ranked tehsils, exposed villages, shelters, Rescue 1122 and district control rooms, river flow, satellite rain, and ready-to-print advisory drafts |
| **Replays** | Any day since March 2024, using the forecasts exactly as they were issued, to see what Nigehban would have said before a real flood |

<table>
<tr>
<td><img src="docs/images/area.png" alt="My area: 4-day risk, what to do, safer places"></td>
<td><img src="docs/images/map.png" alt="Risk map with ranked tehsils"></td>
</tr>
<tr>
<td align="center">My area: levels, advice, reasons, safer places</td>
<td align="center">Risk map: every tehsil, ranked</td>
</tr>
</table>

![Urdu, right to left](docs/images/home-ur.png)

## Results

Backtested on the archived ECMWF, GFS and ICON forecasts of June–September 2024–2025, each season
predicted by a model trained without it, at about 2.5–3 false alerts per tehsil per season:

| Rule | Floods caught (of 41) | Caught 3 days ahead |
|---|---|---|
| **Nigehban model** | **22** | **19** |
| Rain threshold (33 mm, wettest cell) | 16 | 14 |

The model is a Platt-calibrated logistic regression on 7 features, chosen over LightGBM, XGBoost,
random forest and extra trees, which overfit the 89 tehsil-level flood days (ROC-AUC 0.81 on
held-out seasons). Details: [docs/MODEL.md](docs/MODEL.md).

## How it works

```
 PDMA situation reports ──► LLM extraction ──► flood events (labels)
 ERA5 + archived forecasts ──► weather per tehsil ─┐
 Copernicus DEM ──► height above stream, exposure ─┼──► logistic model ──► level per tehsil and day
 GloFAS rivers, NASA IMERG ──► river flag, rain layer ┘          │
                                                                ├──► alert engine ──► web inbox
                                                                ├──► Ask Nigehban (LangGraph agent)
                                                                └──► website and authority board
```

- **Data**: 4,922 PDMA daily reports turned into a geocoded flood-event dataset (names redacted
  before any LLM call); seven monsoon seasons of ERA5 weather on a 0.25° grid, area-weighted per
  tehsil; terrain from Copernicus DEM with pysheds; villages, shelters and roads from OpenStreetMap.
- **Levels** come only from the model and fixed thresholds tuned per lead day, never from the LLM.
- **Agent**: LangGraph pipeline (understand → locate → gather evidence → compose → validate) with
  retries and a template fallback; LLM access through LangChain with Groq first and Gemini as backup.

More in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

**Backend**: Python 3.11, FastAPI, Pydantic v2, SQLModel (SQLite; Postgres supported), LangChain,
LangGraph, scikit-learn, pandas, rasterio, pysheds, shapely, networkx, pyosmium.
**Frontend**: Next.js 15, React 19, TypeScript, MapLibre GL.
**Data**: Open-Meteo (ECMWF, GFS, ICON, ERA5, GloFAS), NASA GPM IMERG, Copernicus DEM, OpenStreetMap,
GeoNames, WorldPop, Pakistan Census 2023, PDMA KP reports.
**Quality**: 187 backend tests (pytest), 13 frontend tests (Vitest), CI on GitHub Actions.

## Quick start

Requires Python 3.11 and Node.js 20.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # on macOS/Linux: .venv/bin/python
cp .env.example .env                                  # add keys as needed (below)
cd frontend && npm install && cd ..
```

Run the API and the website:

```bash
.venv/Scripts/python -m uvicorn backend.app.main:app --port 8000
cd frontend && npm run dev
```

Open http://localhost:3000. Try a replay: http://localhost:3000/?replay=2025-08-14 (the day before
the Buner cloudburst). Run the tests with `python -m pytest -q` and `cd frontend && npm test`.

What works without any keys: risk for every tehsil (live and replays), the maps, place search,
safety guide. Optional keys in `.env`:

| Feature | Setting |
|---|---|
| Ask Nigehban, alert wording, advisories | `GROQ_API_KEY` (free tier) and/or `GEMINI_API_KEY` |
| Alerts sign-up | `NIGEHBAN_CONTACT_ENCRYPTION_KEY`, `NIGEHBAN_CONTACT_HASH_KEY` (generate: see [docs/CONFIGURATION.md](docs/CONFIGURATION.md)) |
| Authority board | `NIGEHBAN_BOARD_PASSWORD` |
| Urdu voice | `NIGEHBAN_ELEVENLABS_API_KEY` |
| Satellite rain layer | `NIGEHBAN_EARTHDATA_TOKEN` |

The danger-zone check and routes need terrain rasters and road tiles, which are large and built by
the pipelines ([docs/DATA.md](docs/DATA.md), section 4). Without them those two features return a
clear "not available" message and everything else works.

Alerts run with `python -m pipelines.alerts.run_cycle` (once) or `--every-hours 3`.

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, data flows, code map, key design decisions |
| [docs/MODEL.md](docs/MODEL.md) | Training data, features, model comparison, levels, evaluation, limits |
| [docs/DATA.md](docs/DATA.md) | Sources and licences, pipelines and rebuild order, privacy |
| [docs/API.md](docs/API.md) | Every endpoint with request and response |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Running, the alert cycle, every setting |
| [docs/GUIDE.md](docs/GUIDE.md) | Walkthrough of every feature, status and future work |
| [reports/](reports/) | Generated QA and evaluation reports for each build step |

## Repository layout

```
backend/app/   FastAPI app: api, hydromet, risk, agent, knowledge, alerts, geo, db, llm, config
frontend/      Next.js website (/, /map, /area, /ask, /alerts, /safety) and board (/board)
pipelines/     Offline jobs: PDMA events, weather history, terrain, reference data, training,
               backtest, knowledge index, alert cycle and replay
data/          Reference tables and small runtime files (large and private data is gitignored)
reports/       QA and evaluation reports
tests/         Backend tests
docs/          Documentation and screenshots
```

## Future work

- Delivery channels beyond the web inbox (SMS, WhatsApp, browser push, a mobile app) can be
  integrated as one channel class each; the alert engine is channel-agnostic.
- Real river gauge readings in place of GloFAS, and more flood labels from NDMA reports and news.
- Re-run the backtest as new seasons of PDMA reports and archived forecasts accumulate.

## Privacy

Raw PDMA reports contain personal names; they and the derived event files stay out of the
repository, and names are redacted before any text is sent to an LLM. Subscriber contacts are
encrypted at rest and never returned by the API.

## License

Code: [MIT](LICENSE). Data keeps its source licences (OpenStreetMap: ODbL; GeoNames, WorldPop,
Open-Meteo, GloFAS: CC BY 4.0; Copernicus DEM licence); see `data/reference/README.md`.
