# M2 hydromet QA

Generated 2026-11-19 by `python -m pipelines.hydromet.qa`.

## Done-when check

| Check | Result |
|---|---|
| ERA5 history Jun–Sep, years | 2019–2026 (8 seasons) |
| Candidate tehsils covered | 48 (every season complete: True) |
| All tehsils in the table | 53 |
| Live call, all tehsils x 3 models x lead 0–3 | 2.9 s, 636 rows (target < 30 s) |
| Buner 15 Aug 2025, ERA5 (planning check about 44 mm) | see below |
| Buner 15 Aug 2025, ECMWF 1 day ahead (planning check about 34 mm) | see below |
| **M2 gate** | **passed** |

## How features are made

- Grid: the 0.25° cells overlapping each tehsil, weighted by area share
  (`data/reference/tehsil_grid.csv`, 80 cells for 53 tehsils).
- Daily = local day (Asia/Karachi). `precip_sum` is the tehsil mean,
  `precip_cell_max` the wettest cell, `precip_max_1h` the wettest hour in any cell.
- `precip_3d` = the day and the 2 days before; `precip_7d_antecedent` = the 7 days before.
- Forecast rows use only what was known at issue time: days before the issue
  date come from ERA5, later days from the same forecast.
- Soil moisture (0–7 and 7–28 cm) is ERA5. For archived forecasts it is ERA5 on
  the day before the issue date. Live: ECMWF's own value (GFS and ICON do not
  provide these layers, so they use ECMWF's).
- `t2m_anomaly` = daily max temperature minus the 2019–2025 ERA5 mean for that
  tehsil and time of year (±15 days). Months outside the history have no anomaly.

## Coverage

| model | lead_days | rows | first | last | missing_rain | missing_soil |
|---|---|---|---|---|---|---|
| ecmwf | 0 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| ecmwf | 1 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| ecmwf | 2 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| ecmwf | 3 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| era5 | 0 | 61056 | 2019-05-20 | 2026-10-10 | 0.0% | 0.0% |
| gfs | 0 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| gfs | 1 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| gfs | 2 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| gfs | 3 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| icon | 0 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| icon | 1 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| icon | 2 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |
| icon | 3 | 12932 | 2024-06-01 | 2025-09-30 | 0.0% | 0.0% |

## Planning checks (tehsil values)

| case | date | source | lead (days) | tehsil mean (mm) | wettest cell (mm) | 3-day (mm) | 7 days before (mm) |
|---|---|---|---|---|---|---|---|
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | ecmwf | 0 | 44.3 | 61.2 | 59.0 | 31.2 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | ecmwf | 1 | 35.1 | 40.8 | 56.6 | 38.0 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | ecmwf | 2 | 30.2 | 34.8 | 49.0 | 35.3 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | ecmwf | 3 | 25.5 | 30.0 | 41.6 | 34.1 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | era5 | 0 | 45.4 | 55.3 | 60.1 | 31.2 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | gfs | 0 | 14.6 | 18.4 | 29.3 | 31.2 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | gfs | 1 | 23.7 | 32.1 | 50.4 | 43.2 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | gfs | 2 | 28.7 | 66.5 | 66.3 | 54.1 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | gfs | 3 | 14.6 | 22.8 | 34.4 | 39.4 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | icon | 0 | 89.9 | 134.7 | 104.6 | 31.2 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | icon | 1 | 5.8 | 6.6 | 28.2 | 38.9 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | icon | 2 | 6.9 | 8.9 | 14.2 | 23.7 |
| Buner cloudburst (Pir Baba / Daggar) | 2025-08-15 | icon | 3 | 22.0 | 30.0 | 35.2 | 33.9 |
| Swat River flood, Babuzai | 2025-06-27 | ecmwf | 0 | 10.9 | 16.8 | 39.8 | 58.5 |
| Swat River flood, Babuzai | 2025-06-27 | ecmwf | 1 | 5.3 | 8.4 | 48.1 | 72.5 |
| Swat River flood, Babuzai | 2025-06-27 | ecmwf | 2 | 6.5 | 8.7 | 19.9 | 43.1 |
| Swat River flood, Babuzai | 2025-06-27 | ecmwf | 3 | 7.3 | 8.7 | 23.8 | 43.8 |
| Swat River flood, Babuzai | 2025-06-27 | era5 | 0 | 3.4 | 3.5 | 32.2 | 58.5 |
| Swat River flood, Babuzai | 2025-06-27 | gfs | 0 | 29.7 | 39.8 | 58.6 | 58.5 |
| Swat River flood, Babuzai | 2025-06-27 | gfs | 1 | 18.4 | 23.3 | 44.6 | 55.9 |
| Swat River flood, Babuzai | 2025-06-27 | gfs | 2 | 27.4 | 28.7 | 53.3 | 55.5 |
| Swat River flood, Babuzai | 2025-06-27 | gfs | 3 | 10.8 | 11.4 | 46.7 | 62.1 |
| Swat River flood, Babuzai | 2025-06-27 | icon | 0 | 0.4 | 1.2 | 29.3 | 58.5 |
| Swat River flood, Babuzai | 2025-06-27 | icon | 1 | 0.5 | 1.1 | 16.5 | 45.7 |
| Swat River flood, Babuzai | 2025-06-27 | icon | 2 | 1.5 | 2.2 | 25.2 | 53.3 |
| Swat River flood, Babuzai | 2025-06-27 | icon | 3 | 1.5 | 3.7 | 14.8 | 39.4 |
| day before, Babuzai | 2025-06-26 | ecmwf | 0 | 33.9 | 62.7 | 46.5 | 38.6 |
| day before, Babuzai | 2025-06-26 | ecmwf | 1 | 7.0 | 9.3 | 17.0 | 36.1 |
| day before, Babuzai | 2025-06-26 | ecmwf | 2 | 6.1 | 6.9 | 17.7 | 37.6 |
| day before, Babuzai | 2025-06-26 | ecmwf | 3 | 9.8 | 12.0 | 17.0 | 32.1 |
| day before, Babuzai | 2025-06-26 | era5 | 0 | 19.9 | 22.4 | 32.5 | 38.6 |
| day before, Babuzai | 2025-06-26 | gfs | 0 | 17.3 | 17.7 | 29.9 | 38.6 |
| day before, Babuzai | 2025-06-26 | gfs | 1 | 17.5 | 18.5 | 29.5 | 38.0 |
| day before, Babuzai | 2025-06-26 | gfs | 2 | 22.1 | 24.4 | 36.1 | 40.1 |
| day before, Babuzai | 2025-06-26 | gfs | 3 | 18.0 | 19.1 | 28.9 | 34.6 |
| day before, Babuzai | 2025-06-26 | icon | 0 | 7.1 | 16.5 | 19.7 | 38.6 |
| day before, Babuzai | 2025-06-26 | icon | 1 | 19.8 | 26.4 | 27.3 | 33.5 |
| day before, Babuzai | 2025-06-26 | icon | 2 | 6.0 | 14.5 | 13.4 | 33.4 |
| day before, Babuzai | 2025-06-26 | icon | 3 | 7.6 | 12.1 | 16.8 | 33.2 |

## Forecast vs ERA5, Jun–Sep (archived forecasts, 2024 onward)

| model | lead | days x tehsils | bias (mm) | MAE (mm) | correlation | ERA5 >= 20 mm days | caught (fc >= 10 mm) |
|---|---|---|---|---|---|---|---|
| ecmwf | 0 | 12932 | -1.3 | 3.2 | 0.6 | 598 | 61% |
| ecmwf | 1 | 12932 | -1.8 | 3.5 | 0.5 | 598 | 43% |
| ecmwf | 2 | 12932 | -2.2 | 3.4 | 0.5 | 598 | 38% |
| ecmwf | 3 | 12932 | -2.1 | 3.6 | 0.5 | 598 | 43% |
| gfs | 0 | 12932 | 0.4 | 4.4 | 0.4 | 598 | 69% |
| gfs | 1 | 12932 | 0.8 | 4.7 | 0.4 | 598 | 69% |
| gfs | 2 | 12932 | 0.4 | 4.6 | 0.4 | 598 | 63% |
| gfs | 3 | 12932 | 0.3 | 4.6 | 0.4 | 598 | 67% |
| icon | 0 | 12932 | -2.6 | 3.9 | 0.4 | 598 | 39% |
| icon | 1 | 12932 | -2.4 | 4.0 | 0.4 | 598 | 38% |
| icon | 2 | 12932 | -2.3 | 4.1 | 0.3 | 598 | 32% |
| icon | 3 | 12932 | -2.5 | 4.1 | 0.3 | 598 | 30% |

Forecasts are compared with ERA5, which is itself smooth over a 0.25° cell, so
both understate rain in the wettest valleys. "Caught" = forecast of at least
10 mm on days when ERA5 had at least 20 mm in the tehsil.

## Does rain line up with events?

| rows | n | mean rain (mm) | median 3-day (mm) | share with 3-day >= 20 mm | mean soil moisture 0–7 cm |
|---|---|---|---|---|---|
| event days (tehsil-level positives) | 136 | 12.8 | 15.9 | 43% | 0.3 |
| all Jun–Sep tehsil-days | 51728 | 4.1 | 6.2 | 19% | 0.3 |

## Limits and open items

- **IMERG (satellite rain):** not tested yet. It needs a Google Earth Engine
  project tied to a Google account. `pipelines/hydromet/imerg_colab_test.py`
  runs the access test in Colab. Per the plan, ERA5 plus forecasts are enough
  for the MVP if it fails.
- **GloFAS (river discharge):** the client works (`OpenMeteoClient.flood`). It
  snaps to the nearest 0.05° cell, which is often beside the main channel (a
  test near Mingora returned about 200 m³/s during the Aug 2022 flood). Picking
  the right cell per river is M6, so `glofas_discharge` is empty for now.
- ERA5 is 0.25° (about 25 km): small tehsils get one cell, and short
  convective bursts are smoothed. The wettest-cell column helps a little.
- Archived forecasts start in March 2024, so the forecast-vs-ERA5 gap rests on
  two or three seasons.
