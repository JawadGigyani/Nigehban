# Data

Where the data comes from, how to rebuild it, and how private data stays private.

## Sources

| Source | Used for | Licence |
|:--|:--|:--|
| PDMA KP daily reports | Flood history (labels) | Public; raw text kept private |
| Open-Meteo: ERA5, ECMWF, GFS, ICON | Rain, soil moisture, temperature | CC BY 4.0 |
| Open-Meteo: GloFAS | River flow | CC BY 4.0 |
| NASA GPM IMERG | Satellite rain layer | NASA open data |
| Copernicus DEM (30 m, 90 m) | Terrain, streams, low ground | Copernicus DEM licence |
| OpenStreetMap | Villages, shelters, roads | ODbL |
| GeoNames | Place names | CC BY 4.0 |
| WorldPop, Census 2023 | Population | CC BY 4.0, public |
| PDMA, NDMA, NIH guidance | Answers and advisories | Public |

Per-file licences: `data/reference/README.md`.

## What's in git, and what isn't

| Folder | In git? | Contents |
|:--|:--:|:--|
| `data/reference/` | ✅ | Tehsils, place names, villages, shelters, rivers, Urdu names, Rescue 1122 |
| `data/features/` (3 files) | ✅ | Weather history and tehsil features, so a fresh clone works |
| `data/raw/`, `data/events/` | ❌ | PDMA reports and flood events (private); one small OSM file is kept |
| `data/interim/`, `data/cache/` | ❌ | Terrain rasters, road tiles, API caches (large) |

Without the terrain files, everything works except the danger check, which says so clearly.

## Rebuild

Each step resumes where it stopped and caches its downloads. Run from the repository root.

| Step | Command | Output |
|:--|:--|:--|
| 1. Reference data | `python -m pipelines.reference.build_tehsils` (then `census2023`, `build_gazetteer --fetch-osm`, `build_aliases`) | `data/reference/` |
| 2. Flood events | `python -m pipelines.pdma.fetch_dsr --start 1 --end 8200`, then `extract`, then `build_events` | `data/events/` (private) |
| 3. Weather history | `python -m pipelines.hydromet.build_history` | `data/features/` |
| 4. Terrain | `python -m pipelines.terrain.fetch_dem`, then `build_terrain` | `data/interim/terrain/` |
| 5. Facilities and roads | `python -m pipelines.reference.build_facilities --fetch`, then `extract_roads` | shelters, road tiles |
| 6. Rivers | `python -m pipelines.rivers.build_thresholds` | river flood levels |
| 7. Model | see [Risk model](MODEL.md#retrain) | `backend/app/risk/artifacts/` |
| 8. Guidance index | `python -m pipelines.knowledge.build_index` | `backend/app/knowledge/index/` |

<details>
<summary>Extra options</summary>

- **Swat at 30 m:** `fetch_dem --res 30 --bbox 72.0 34.6 72.9 35.9`, `build_terrain --tag swat30`,
  `merge_detail --tag swat30 --district swat`.
- **All months of weather:** `build_history --scope all` (not needed by the app; uses the free daily
  quota, so it can take days).
- **Satellite rain history:** `python -m pipelines.hydromet.imerg_history`.
- **Quality reports:** `pipelines.hydromet.qa`, `pipelines.terrain.qa`, `pipelines.rivers.qa`.

</details>

## Privacy

- PDMA reports contain names. They never leave `data/raw/`, and names are removed before any text goes
  to a language model.
- Subscriber contacts are encrypted and never returned by the API. Users can delete all their data.
- API keys live only in `.env`, which git ignores.

## Files you might edit by hand

| File | Note |
|:--|:--|
| `data/reference/urdu_names.csv` | Urdu names for districts and tehsils. In Excel, save as **CSV UTF-8**. |
| `data/reference/manual_places.csv` | Places the maps miss or misplace |
| `data/reference/rescue1122_*.csv` | Rescue 1122 stations and district numbers |
