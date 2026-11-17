# Data contracts

Offline modules exchange data through these files. Each row matches a pydantic
model in `backend/app/contracts/`. Sample rows are in `tests/fixtures/contracts/`.

| File | Contract | Written by | Committed? |
|---|---|---|---|
| `data/reference/tehsils.geojson` | `TehsilRegion` (feature properties) + polygon geometry | M4a | Yes (small) |
| `data/reference/tehsil_aliases.csv` | `pdma_name, district, tehsil_id` | M4a / M1 | Yes |
| `data/raw/pdma_dsr/*.html.gz` + `_index.jsonl` | raw PDMA reports | M0 scraper | **No (private)** |
| `data/events/flood_events.parquet` | `FloodEvent` | M1 | **No (private)** |
| `data/features/hydromet_daily.parquet` | `HydrometDaily` | M2 | No (rebuildable) |
| `data/features/tehsil_static.parquet` | `TehsilStatic` | M3 | Optional |
| `data/reference/village_exposure.csv` | `VillageExposure` | M3 | Yes (small) |
| `data/reference/river_points_thresholds.json` | `RiverThresholds` | M6 | Yes |
| `models/flash_flood/<version>/` | model, calibrator, features, metrics | M5 | No |

## Rules

- **Positive labels** are decided in one place: `contracts.enums.POSITIVE_EVENT_TYPES`
  (flash flood, flood, cloudburst, drowning in a stream or flood). Landslides and
  roof collapses are kept as their own types and are not positives.
- **No personal names** anywhere in processed data. PDMA reports name victims;
  only place, date, event type and counts are kept.
- **`tehsil_id`** is `<district_slug>__<tehsil_slug>` (see `config.region.make_tehsil_id`).
- **Exposure** is reported as bands (low / medium / high), never as depths.
- **Risk levels** come from the model and fixed thresholds, never from the LLM.
