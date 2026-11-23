# Data

Where Nigehban's data comes from, how to rebuild it, and how private data is kept private. File
contracts (columns and types) are in `data/contracts/README.md`; licences per file are in
`data/reference/README.md`.

## Sources

| Source | Used for | Access | Licence |
|---|---|---|---|
| PDMA KP daily situation reports (rms.pdma.gov.pk) | Flood event labels | Polite scraper, 2 s between requests, cached | Public reports; raw text kept private |
| Open-Meteo: ERA5, forecast (ECMWF IFS, GFS, ICON), previous runs | Rain, soil moisture, temperature | Free API, paced to stay inside the free quota | CC BY 4.0 |
| Open-Meteo Flood API (Copernicus GloFAS) | River flow and return periods | Free API | CC BY 4.0 |
| NASA GPM IMERG (GES DISC OPeNDAP) | Observed satellite rain layer, comparison with ERA5 | Earthdata token | NASA open data |
| Copernicus DEM GLO-90 / GLO-30 | HAND, slope, catchments, streams | AWS open data | Copernicus DEM licence |
| OpenStreetMap (Geofabrik Pakistan extract, Overpass) | Villages, shelters, mosques, health, roads | Download | ODbL |
| GeoNames | Place names and alternate names | Download | CC BY 4.0 |
| WorldPop 2020 (1 km) | Population per cell | Download | CC BY 4.0 |
| Pakistan Census 2023 | Tehsil population totals | PBS tables | Public |
| PDMA KP, NDMA, NIH guidance PDFs | Knowledge index for answers and advisories | Public documents | Public |
| Rescue 1122 KP directory and news reports | District control rooms, station points | Manual, marked unverified | Public |

## Data folders

```
data/reference/   small reference tables, in git (tehsils, grid weights, gazetteer, facilities,
                  village exposure, river points, Urdu names, Rescue 1122 contacts)
data/raw/         downloads and PDMA reports                         (gitignored, private)
data/interim/     intermediate files: LLM extractions, terrain rasters (gitignored)
data/events/      flood events and corrections                        (gitignored, private)
data/features/    hydromet_daily.parquet, imerg_daily.parquet         (gitignored)
data/cache/       API caches (Open-Meteo, IMERG, OSM road tiles)       (gitignored)
data/nigehban.db  local SQLite database                                 (gitignored)
```

## Rebuild order

Run from the `nigehban` folder. Each step is resumable and cached; most write a QA report in
`reports/`.

### 1. Reference data (M4a)

```powershell
.venv\Scripts\python -m pipelines.reference.build_tehsils
.venv\Scripts\python -m pipelines.reference.census2023
.venv\Scripts\python -m pipelines.reference.build_gazetteer --fetch-osm
.venv\Scripts\python -m pipelines.reference.build_aliases
```

### 2. Flood events from PDMA reports (M1)

```powershell
.venv\Scripts\python -m pipelines.pdma.fetch_dsr --start 1 --end 8200   # start or resume the download
.venv\Scripts\python -m pipelines.pdma.fetch_dsr --status               # progress
.venv\Scripts\python -m pipelines.pdma.extract --dry-run                # count the LLM work
.venv\Scripts\python -m pipelines.pdma.extract                          # LLM extraction (cached)
.venv\Scripts\python -m pipelines.pdma.build_events                     # dedupe, geocode, write events
```

- `extract` parses each report, keeps flood-like district rows, removes personal names from the
  text (`pipelines/pdma/redact.py`) and asks the LLM to fill a fixed form.
- `build_events` geocodes (village, then tehsil, then district), merges repeat reports, applies the
  private hand corrections in `data/events/event_corrections.csv`, and writes
  `data/events/flood_events.parquet` plus `reports/flood_events_qa.md`.

### 3. Weather history (M2)

```powershell
.venv\Scripts\python -m pipelines.hydromet.build_history              # Jun–Sep 2019–2025 (core)
.venv\Scripts\python -m pipelines.hydromet.build_history --scope all  # every month (optional)
.venv\Scripts\python -m pipelines.hydromet.build_history --status
.venv\Scripts\python -m pipelines.hydromet.qa                         # reports/weather_qa.md
.venv\Scripts\python -m pipelines.hydromet.imerg_history              # IMERG Jun–Sep 2019–2025
```

The Open-Meteo pacer keeps usage under the free limits (per minute, hour and day) and remembers
usage across runs (`data/cache/openmeteo/_pacer.json`). When the daily quota is used up the script
stops cleanly; run it again the next day.

### 4. Terrain and facilities (M3, M4b)

```powershell
.venv\Scripts\python -m pipelines.terrain.fetch_dem
.venv\Scripts\python -m pipelines.terrain.build_terrain
.venv\Scripts\python -m pipelines.terrain.fetch_dem --res 30 --bbox 72.0 34.6 72.9 35.9
.venv\Scripts\python -m pipelines.terrain.build_terrain --tag swat30
.venv\Scripts\python -m pipelines.terrain.merge_detail --tag swat30 --district swat
.venv\Scripts\python -m pipelines.terrain.qa                          # reports/terrain_qa.md
.venv\Scripts\python -m pipelines.reference.build_facilities --fetch
.venv\Scripts\python -m pipelines.reference.extract_roads             # OSM road tiles for routing
```

Village exposure band: the lowest HAND (height above nearest stream) within about 180 m of the
village; high = under 5 m beside a stream draining at least 50 km², medium = under 8 m.

### 5. Rivers (M6)

```powershell
.venv\Scripts\python -m pipelines.rivers.build_thresholds   # Gumbel fit to yearly GloFAS peaks 1997–2025
.venv\Scripts\python -m pipelines.rivers.qa                 # reports/rivers_glofas.md
```

### 6. Model and evaluation (M5, M7)

See [MODEL.md](MODEL.md#retraining).

### 7. Knowledge index (M8)

```powershell
.venv\Scripts\python -m pipelines.knowledge.build_index
```

Builds `backend/app/knowledge/index/passages.jsonl.gz` from the guidance PDFs (PDMA KP summer
hazards contingency plan, NDMP, Swat disaster risk mapping, PDMA flood do's and don'ts, NIH flood
guidelines). Lists of officials' names are filtered out.

### 8. Check

`GET /health` lists any runtime file still missing (`backend/app/runtime_data.py`, `RUNTIME_FILES`).

## Privacy

- Raw PDMA reports contain personal names. They stay in gitignored `data/raw/` and are never
  committed or bundled. Names are redacted before any text goes to an LLM.
- Event files, hand corrections and spot checks are private (`data/events/`).
- Subscriber contacts are encrypted at rest (Fernet) and looked up by keyed hash; the API never
  returns them. Users can delete all their data (`POST /me/delete`).
- API keys live only in `.env` (gitignored).

## Hand-edited reference files

| File | What to know |
|---|---|
| `data/reference/urdu_names.csv` | Fixed Urdu names for districts and tehsils, confirmed by a native speaker. UTF-8 with BOM; in Excel save as "CSV UTF-8" or the Urdu is corrupted. |
| `data/reference/manual_places.csv` | Places the gazetteer misses or misplaces (for example Fizagat). |
| `data/reference/rescue1122_manual.csv`, `rescue1122_district_contacts.csv` | Rescue 1122 stations and district control rooms; shown as unverified. |
| `data/events/event_corrections.csv` (private) | Corrections from the manual spot check, applied on every rebuild. |
