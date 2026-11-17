# Nigehban

Flash-flood early warning for northern Khyber Pakhtunkhwa. Nigehban estimates
flash-flood risk for each tehsil for the next one to three days, sends Urdu
alerts to people who subscribe, and gives authorities a risk board.

It supports official warnings and never replaces them. Risk is estimated per
tehsil, not per house, and some events will be missed.

## Setup (Windows, Python 3.11+)

```bash
py -3.11 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env   # then fill in the keys
```

## Run

```bash
.venv/Scripts/python -m pytest              # unit tests
.venv/Scripts/uvicorn backend.app.main:app  # API on http://127.0.0.1:8000/health
```

Live LLM tests are opt-in: set `NIGEHBAN_RUN_LIVE=1`.

## Data pipelines

PDMA KP daily situation reports (polite, resumable, cached; 2 s between requests):

```bash
.venv/Scripts/python -m pipelines.pdma.fetch_dsr --start 1 --end 8200
```

Raw reports contain personal names. They stay in the gitignored `data/raw/`
folder and are never committed. See `data/contracts/README.md` for every data
file and its contract.

## Layout

```
backend/app/   contracts/ config/ db/ llm/ main.py   (more modules added per phase)
pipelines/     offline data jobs (pdma, ...)
tests/         unit tests and contract fixtures
data/          contracts notes and small reference files (the rest is gitignored)
```

## Data sources

PDMA Khyber Pakhtunkhwa daily situation reports; Open-Meteo (ECMWF, GFS, ICON,
ERA5, GloFAS); Copernicus DEM GLO-30; OpenStreetMap (ODbL); GeoNames (CC BY);
WorldPop (CC BY 4.0). Licences are listed per file in `data/reference/README.md`.
