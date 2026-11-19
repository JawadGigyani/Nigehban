# M5 risk model QA

Generated 2026-11-19 by `python -m pipelines.risk.train`. Model artifact:
`backend/app/risk/artifacts/v1/` (model.joblib + Platt calibration in meta.json).

## Gate G2

**Passed.** The model
(seasons held out) must beat the best single rain threshold on hit rate at the same false-alert
rate (2.5 per tehsil per season) and on PR-AUC.

## Data

- 40,992 tehsil-days (48 in-scope tehsils, Jun–Sep 2019–2025); 40,119 used for training.
- 89 positive tehsil-days (89 tehsil-level flood events in these months).
- Left out of training: the day either side of an event, and districts on days PDMA named only the district.

| year | positives | tehsil_days |
|---|---|---|
| 2019 | 11 | 5856 |
| 2020 | 8 | 5856 |
| 2021 | 12 | 5856 |
| 2022 | 14 | 5856 |
| 2023 | 3 | 5856 |
| 2024 | 10 | 5856 |
| 2025 | 31 | 5856 |

## Feature sets x model types (exploration, `python -m pipelines.risk.experiment`)

| features | model | seasons hit | seasons PR-AUC | districts hit | districts PR-AUC |
|---|---|---|---|---|---|
| all | logistic | 0.37 | 0.0209 | 0.30 | 0.0125 |
| all | lightgbm | 0.28 | 0.011 | 0.37 | 0.0157 |
| all | extra_trees | 0.32 | 0.0079 | 0.42 | 0.0165 |
| rain core + 2 terrain | logistic | 0.42 | 0.0197 | 0.37 | 0.0178 |
| rain core + 2 terrain | lightgbm | 0.18 | 0.0075 | 0.27 | 0.0124 |
| rain core + 2 terrain | extra_trees | 0.29 | 0.0104 | 0.30 | 0.0116 |
| rain core only | logistic | 0.42 | 0.0158 | 0.38 | 0.0152 |
| rain core only | lightgbm | 0.24 | 0.0069 | 0.28 | 0.0117 |
| rain core only | extra_trees | 0.30 | 0.0096 | 0.27 | 0.0106 |
| rain core + terrain | logistic | 0.39 | 0.0213 | 0.37 | 0.0171 |
| rain core + terrain | lightgbm | 0.23 | 0.0081 | 0.26 | 0.0108 |
| rain core + terrain | extra_trees | 0.28 | 0.0091 | 0.39 | 0.0126 |

With all 19 features, tree models latched onto season, temperature and
population and lost to a plain rain threshold. A small rain-centred set with a logistic
model generalised best, so that set is used below.

## Model types compared on the chosen features (same folds, same false-alert rate)

| model | seasons held out: hit rate | seasons held out: PR-AUC | seasons held out: ROC-AUC | districts held out: hit rate | districts held out: PR-AUC |
|---|---|---|---|---|---|
| logistic | 0.42 | 0.0193 | 0.81 | 0.37 | 0.0176 |
| random_forest | 0.25 | 0.0084 | 0.74 | 0.28 | 0.0102 |
| extra_trees | 0.30 | 0.0105 | 0.80 | 0.30 | 0.0115 |
| lightgbm | 0.34 | 0.0106 | 0.77 | 0.35 | 0.0123 |
| xgboost | 0.33 | 0.0116 | 0.79 | 0.34 | 0.0105 |

Chosen: **logistic** (best average hit rate over held-out seasons and held-out districts;
PR-AUC breaks ties). Hit rate = share of tehsil-level events caught at 2.5 false alerts
per tehsil per season.

## Chosen model against the baselines (same false-alert rate)

| method | ROC-AUC | PR-AUC | hit rate at 2.5 false alerts | false alerts / tehsil-season | events |
|---|---|---|---|---|---|
| logistic (rain + terrain), seasons held out | 0.81 | 0.0193 | 0.42 | 2.49 | 89 |
| logistic (rain + terrain), districts held out | 0.82 | 0.0176 | 0.37 | 2.47 | 89 |
| logistic ERA5-only rain model, seasons held out | 0.81 | 0.0158 | 0.42 | 2.49 | 89 |
| Rain threshold (precip_cell_max) | 0.81 | 0.0129 | 0.37 | 2.47 | 89 |

How alerts are scored: an event counts as caught if an alert was on the day before, the day, or the
day after. A false alert is a run of alert days in a tehsil with no event within a day. Rates are per
tehsil per season (122 days).

## Alert levels (calibrated probability)

| level | probability | target_false_alerts_per_tehsil_season | hit_rate | false_alerts_per_tehsil_season |
|---|---|---|---|---|
| moderate | 0.00431 | 8.00 | 0.71 | 8.00 |
| high | 0.0119 | 2.50 | 0.42 | 2.49 |
| very_high | 0.0273 | 0.50 | 0.10 | 0.48 |

`high` uses `NIGEHBAN_ALERT_FALSE_ALARM_TARGET_PER_SEASON` (2.5). Levels come only from the
model and these fixed thresholds, never from the LLM.

## Calibration (seasons held out, Platt scaling)

ROC-AUC 0.812, PR-AUC 0.019, Brier 0.00220
(base rate 0.0022).

| predicted (mean) | observed rate | rows | events |
|---|---|---|---|
| 0.000172 | 0.000199 | 5015 | 1 |
| 0.000335 | 0.000199 | 5015 | 1 |
| 0.000528 | 0.000997 | 5015 | 5 |
| 0.000801 | 0.000399 | 5014 | 2 |
| 0.00122 | 0.000598 | 5015 | 3 |
| 0.00192 | 0.00259 | 5015 | 13 |
| 0.00323 | 0.00379 | 5015 | 19 |
| 0.00965 | 0.00897 | 5015 | 45 |

## With real forecasts (2024–2025, archived runs, season held out)

Same model and "high" threshold, fed with what each weather model forecast 0–3 days ahead,
compared with feeding it ERA5 (what actually fell, known only afterwards).

| year | lead | source | events | hits | hit_rate | false_alerts_per_tehsil_season |
|---|---|---|---|---|---|---|
| 2024 | 0 | 3-model mean | 10 | 0 | 0.00 | 0.38 |
| 2024 | 0 | ecmwf | 10 | 0 | 0.00 | 0.33 |
| 2024 | 0 | gfs | 10 | 1 | 0.10 | 1.27 |
| 2024 | 0 | icon | 10 | 0 | 0.00 | 0.15 |
| 2024 | 1 | 3-model mean | 10 | 1 | 0.10 | 0.40 |
| 2024 | 1 | ecmwf | 10 | 0 | 0.00 | 0.12 |
| 2024 | 1 | gfs | 10 | 2 | 0.20 | 1.44 |
| 2024 | 1 | icon | 10 | 0 | 0.00 | 0.52 |
| 2024 | 2 | 3-model mean | 10 | 0 | 0.00 | 0.0833 |
| 2024 | 2 | ecmwf | 10 | 0 | 0.00 | 0.0625 |
| 2024 | 2 | gfs | 10 | 1 | 0.10 | 0.83 |
| 2024 | 2 | icon | 10 | 0 | 0.00 | 0.44 |
| 2024 | 3 | 3-model mean | 10 | 0 | 0.00 | 0.17 |
| 2024 | 3 | ecmwf | 10 | 0 | 0.00 | 0.50 |
| 2024 | 3 | gfs | 10 | 0 | 0.00 | 0.65 |
| 2024 | 3 | icon | 10 | 0 | 0.00 | 0.25 |
| 2024 | analysis | ERA5 (what actually fell) | 10 | 3 | 0.30 | 2.00 |
| 2025 | 0 | 3-model mean | 31 | 8 | 0.26 | 1.00 |
| 2025 | 0 | ecmwf | 31 | 12 | 0.39 | 1.23 |
| 2025 | 0 | gfs | 31 | 8 | 0.26 | 2.04 |
| 2025 | 0 | icon | 31 | 13 | 0.42 | 1.29 |
| 2025 | 1 | 3-model mean | 31 | 6 | 0.19 | 0.40 |
| 2025 | 1 | ecmwf | 31 | 10 | 0.32 | 1.02 |
| 2025 | 1 | gfs | 31 | 8 | 0.26 | 2.19 |
| 2025 | 1 | icon | 31 | 1 | 0.0323 | 0.33 |
| 2025 | 2 | 3-model mean | 31 | 6 | 0.19 | 0.48 |
| 2025 | 2 | ecmwf | 31 | 5 | 0.16 | 0.67 |
| 2025 | 2 | gfs | 31 | 5 | 0.16 | 1.38 |
| 2025 | 2 | icon | 31 | 5 | 0.16 | 0.56 |
| 2025 | 3 | 3-model mean | 31 | 3 | 0.0968 | 0.44 |
| 2025 | 3 | ecmwf | 31 | 4 | 0.13 | 0.67 |
| 2025 | 3 | gfs | 31 | 8 | 0.26 | 1.81 |
| 2025 | 3 | icon | 31 | 2 | 0.0645 | 0.85 |
| 2025 | analysis | ERA5 (what actually fell) | 31 | 17 | 0.55 | 5.10 |

## What the model leans on (share of influence)

| feature | share |
|---|---|
| soil_moisture_0_7 | 0.24 |
| log_precip_cell_max | 0.22 |
| log_precip_7d_antecedent | 0.19 |
| log_precip_3d | 0.17 |
| log_population | 0.0889 |
| log_precip_max_1h | 0.0518 |
| log_high_villages | 0.0394 |

## Limits

- About 89 positive days: the model is pooled across tehsils and kept simple
  (monotone in rain and soil moisture, shallow trees).
- Labels are PDMA reports: floods that hurt nobody, or happened in remote places, are missing,
  so some "false alerts" are real floods nobody reported.
- ERA5 is 25 km; local cloudbursts are smoothed, which caps what any rain-based model can catch.
- Archived forecasts exist only from 2024, so the forecast check rests on two seasons.
