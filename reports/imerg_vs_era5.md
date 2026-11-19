# IMERG vs ERA5 on PDMA flood days

Generated 2026-11-20 by `python -m pipelines.hydromet.imerg_history`. IMERG Final (daily, 0.1°),
Jun–Sep 2019–2025, 40,992 tehsil-days. Each rain value alone, as a flood-day signal
(tehsil-level PDMA events, same rows as the M5 training table).

| rain source | ROC-AUC | PR-AUC | mean on flood days (mm) | mean other days (mm) |
|---|---|---|---|---|
| ERA5 tehsil mean | 0.81 | 0.0129 | 17.9 | 4.24 |
| ERA5 wettest cell | 0.81 | 0.0129 | 24.6 | 6.01 |
| IMERG tehsil mean | 0.79 | 0.00985 | 12.6 | 3.11 |
| IMERG wettest cell | 0.79 | 0.00978 | 23.1 | 6.56 |

Daily correlation between ERA5 and IMERG tehsil means: 0.32.

Buner, 15 Aug 2025 (IMERG):

| tehsil_id | date | imerg_precip | imerg_cell_max |
|---|---|---|---|
| buner__daggar | 2025-08-15 | 18.6 | 37.1 |
| buner__gagra | 2025-08-15 | 15.6 | 45.6 |
| buner__khado_khel | 2025-08-15 | 1.46 | 4.07 |
| buner__mandanr | 2025-08-15 | 6.80 | 16.6 |

## Does IMERG improve the risk model? (logistic model, same folds and false-alert rate as M5)

| Model inputs | Hit rate, seasons held out | Hit rate, districts held out |
|---|---|---|
| Current (ERA5 / forecasts) | 0.416 | 0.371 |
| + IMERG on the day itself (wettest cell, 3-day) | 0.472 | 0.427 |
| + IMERG on past days only | 0.382 | 0.371 |

- Same-day satellite rain adds about 5–6 points, but it exists only after the rain has fallen, so it
  cannot be used to forecast 1–3 days ahead.
- Past days' satellite rain (the only part available at forecast time) does not help.
- Decision: IMERG is **not** added to the forecast model. Its honest use is as an observed-rain
  nowcast for today (IMERG Early, available a few hours after the rain), and as an independent check
  on ERA5 (daily correlation only 0.32 at tehsil level, so they often disagree on local storms).
