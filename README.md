# Nigehban (نگہبان)

Flash-flood early warning for northern Khyber Pakhtunkhwa. Nigehban gives every tehsil a
flash-flood risk level for today and the next three days. It sends Urdu and English alerts to
people who subscribe, answers questions about risk and safety, and gives PDMA, district
administrations and Rescue 1122 a risk board with ready-to-print advisories.

It supports official warnings and never replaces them. Risk is estimated per tehsil, not per house,
and some floods will be missed.


## What it does

| For | Feature |
|---|---|
| Everyone | Risk level per tehsil (Low, Moderate, High, Very high) for days 0–3, with the reasons |
| Everyone | "Am I in a danger zone?": checks a point for low ground beside a large river, with a walking route to higher ground |
| Everyone | Ask Nigehban: questions in Urdu or English, answered only from Nigehban's data and official guidance, with sources and Urdu voice |
| Subscribers | Alerts when their place turns high, in their language, with an Urdu voice note; no duplicates |
| Authorities | Risk board: ranked tehsils, exposed villages, shelters, Rescue 1122, river flow, satellite rain, advisory drafts, replays of past days |

Coverage: 48 tehsils in 9 districts (Swat, Buner, Shangla, Upper Dir, Lower Dir, Bajaur, Malakand,
Mansehra, Battagram).

## How it works, in one paragraph

Every three hours Nigehban takes the ECMWF, GFS and ICON rain forecasts for each tehsil, plus soil
moisture and recent rain. It feeds them, with two terrain and exposure inputs, to a calibrated
logistic model trained on seven monsoon seasons of PDMA flood reports. Fixed probability
thresholds turn the result into a level for each day. A river check (GloFAS) can raise, never
lower, a level. Alerts follow fixed rules; the LLM only writes the wording, and code checks it. In
tests on real archived forecasts for 2024–2025 the system caught 22 of 41 flood events (19 of them
three days ahead), against 16 for a plain rain threshold at the same false-alarm rate.

## Quick start (Windows, PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env      # then fill in the keys (see docs/CONFIGURATION.md)
cd frontend; npm install; cd ..
```

Run the API and the website in two terminals:

```powershell
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend; npm run dev
```

Open http://localhost:3000 (website) and http://localhost:3000/board (board). Run the alert
cycle with `python -m pipelines.alerts.run_cycle` (once) or `--every-hours 3`. Tests:

```powershell
.venv\Scripts\python -m pytest -q
```

The runtime data (terrain rasters, weather history, road tiles) is built by the pipelines in
`pipelines/`; see [docs/DATA.md](docs/DATA.md). Reference tables and the trained model are in git.

## Documentation

| Document | Contents |
|---|---|
| [docs/GUIDE.md](docs/GUIDE.md) | Run it yourself, a 15-minute test walkthrough, what each feature does |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, components, data flow, code map, key decisions |
| [docs/MODEL.md](docs/MODEL.md) | Risk model: data, features, model choice, levels, evaluation, limits |
| [docs/DATA.md](docs/DATA.md) | Data sources, licences, pipelines and rebuild order, privacy |
| [docs/API.md](docs/API.md) | Every HTTP endpoint with request and response |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Running it, the alert cycle, every setting |
| [frontend/README.md](frontend/README.md) | Website pages, motion and frontend code |
| [reports/](reports/) | Results of each build step (QA, model, backtest, agent, alerts, IMERG) |

## Repository layout

```
backend/app/     FastAPI backend: api, hydromet, risk, agent, knowledge, alerts, geo, db, llm, config
frontend/        Next.js website (/, /map, /area, /ask, /alerts, /safety) and authority board (/board)
pipelines/       Offline jobs: PDMA events, weather history, terrain, reference data, training,
                 backtest, knowledge index, alert cycle and replay
data/            Reference tables in git; large and private data gitignored (data/contracts/README.md)
reports/         Generated QA and evaluation reports
tests/           Unit and integration tests (pytest)
docs/            Project documentation
```

## Status

All modules are complete and tested (192 backend tests). Open items: an SMS route (code ready;
needs an Android gateway phone or a paid provider) and WhatsApp (code ready; needs a Meta test
number). See the roadmap in [docs/GUIDE.md](docs/GUIDE.md#1-status).

## Data sources

PDMA Khyber Pakhtunkhwa daily situation reports; Open-Meteo (ECMWF, GFS, ICON, ERA5, GloFAS);
NASA GPM IMERG; Copernicus DEM GLO-30/90; OpenStreetMap (ODbL); GeoNames (CC BY); WorldPop
(CC BY 4.0); Pakistan Census 2023; PDMA, NDMA and NIH guidance documents. Licences per file are in
`data/reference/README.md`.
