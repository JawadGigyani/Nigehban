# M7 backtest

Generated 2026-11-19 by `python -m pipelines.backtest.run`. Every season is predicted by a model
trained without it. Model: logistic; "high" at probability 0.0119; rain threshold
33 mm in the wettest cell; river flag at the 5-year GloFAS flow
(`NIGEHBAN_RIVER_FLAG_RETURN_PERIOD`).

## A. With the forecasts as they were issued (Jun–Sep 2024–2025)

### Levels tuned on forecasts (each season tuned on the other), 2.5 false alerts per tehsil-season

| rule | lead (days) | events | caught | false alerts / tehsil-season | hit rate |
|---|---|---|---|---|---|
| model | 1 | 41 | 16 | 3.02 | 0.39 |
| model | 2 | 41 | 14 | 2.65 | 0.34 |
| model | 3 | 41 | 19 | 3.14 | 0.46 |
| model or river | 1 | 41 | 16 | 3.03 | 0.39 |
| model or river | 2 | 41 | 14 | 2.66 | 0.34 |
| model or river | 3 | 41 | 19 | 3.15 | 0.46 |
| rain threshold | 1 | 41 | 14 | 2.65 | 0.34 |
| rain threshold | 2 | 41 | 11 | 2.62 | 0.27 |
| rain threshold | 3 | 41 | 14 | 2.38 | 0.34 |

| rule | events | caught at any lead | caught 3 days ahead | caught 2+ days ahead |
|---|---|---|---|---|
| rain threshold | 41 | 16 | 14 | 15 |
| model | 41 | 22 | 19 | 20 |
| model or river | 41 | 22 | 19 | 20 |

### Levels tuned on ERA5 (as in M5): too few alerts on forecasts

| rule | lead (days) | events | caught | false alerts / tehsil-season | hit rate |
|---|---|---|---|---|---|
| model (high+) | 1 | 41 | 7 | 0.40 | 0.17 |
| model (high+) | 2 | 41 | 6 | 0.28 | 0.15 |
| model (high+) | 3 | 41 | 3 | 0.30 | 0.0732 |
| model or river | 1 | 41 | 7 | 0.41 | 0.17 |
| model or river | 2 | 41 | 6 | 0.29 | 0.15 |
| model or river | 3 | 41 | 3 | 0.31 | 0.0732 |
| rain threshold | 1 | 41 | 13 | 1.27 | 0.32 |
| rain threshold | 2 | 41 | 10 | 1.04 | 0.24 |
| rain threshold | 3 | 41 | 8 | 0.89 | 0.20 |

### How early were events caught?

| rule | events | caught at any lead | caught 3 days ahead | caught 2+ days ahead | caught 1+ day ahead |
|---|---|---|---|---|---|
| rain threshold | 41 | 16 | 8 | 13 | 16 |
| model (high+) | 41 | 9 | 3 | 7 | 9 |
| model or river | 41 | 9 | 3 | 7 | 9 |

## B. Best case: if the forecast were perfect (ERA5, Jun–Sep 2019–2025)

| rule | events | caught | hit rate | false alerts / tehsil-season |
|---|---|---|---|---|
| rain threshold | 89 | 33 | 0.37 | 2.47 |
| model (high+) | 89 | 37 | 0.42 | 2.49 |
| model or river (>=2-yr flow) | 89 | 37 | 0.42 | 2.55 |
| model or river (>=5-yr flow) | 89 | 37 | 0.42 | 2.49 |
| model or river (>=10-yr flow) | 89 | 37 | 0.42 | 2.49 |
| river only (>=5-yr flow) | 89 | 0 | 0.00 | 0.00595 |

### Deployed rule (model high+ or river flag) by season

| season | events | caught | false alerts / tehsil-season |
|---|---|---|---|
| 2019 | 11 | 1 | 1.02 |
| 2020 | 8 | 0 | 1.75 |
| 2021 | 12 | 8 | 2.27 |
| 2022 | 14 | 7 | 3.90 |
| 2023 | 3 | 1 | 1.38 |
| 2024 | 10 | 3 | 2.02 |
| 2025 | 31 | 17 | 5.10 |

### By district

| district | events | caught | false alerts / tehsil-season |
|---|---|---|---|
| bajaur | 18 | 6 | 1.71 |
| battagram | 1 | 0 | 1.79 |
| buner | 10 | 4 | 2.11 |
| lower_dir | 8 | 2 | 3.74 |
| malakand | 6 | 3 | 3.00 |
| mansehra | 8 | 4 | 2.31 |
| shangla | 4 | 1 | 2.55 |
| swat | 22 | 13 | 3.05 |
| upper_dir | 12 | 4 | 1.84 |

## How to read this

- Hit rates are low in absolute terms, and that is the honest picture: many PDMA flood reports
  come from short local storms that 25 km weather data and global forecasts do not resolve.
- "Best case" shows the ceiling with today's inputs; the gap to "real forecasts" is the forecast error.
- The river flag uses the GloFAS reanalysis, so its contribution is also a best case.
- About 41 events in 2024–2025: one or two events change a hit rate by several points.
- Scoring follows M5: ±1 day window; false alerts are runs of alert days with no event, per tehsil
  per season (122 days).
