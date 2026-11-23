# Risk model

How Nigehban turns weather forecasts into a flash-flood level per tehsil and day, and how well it
works. Full tables are in `reports/m5_risk_qa.md`, `reports/m7_backtest.md`,
`reports/m6_glofas.md` and `reports/imerg_vs_era5.md`.

## The question it answers

"Will this tehsil have a flash flood (as PDMA would report it) on this day?" for days 0–3 ahead,
for 48 tehsils in 9 districts of northern Khyber Pakhtunkhwa, in the June–September season.

## Training data

- **Labels**: PDMA KP daily situation reports, July 2019 to April 2026 (4,922 reports). An LLM read
  each flood-like district row into a fixed form; events were geocoded to tehsils and merged.
  Positives are flash floods, floods, cloudbursts and drownings; landslides and roof collapses are
  kept but are not positives. See `reports/m1_events_qa.md` (gate G1 passed).
- **Rows**: 40,992 tehsil-days (48 tehsils × June–September 2019–2025); 40,119 used. 89 positive
  tehsil-days. Left out: the days either side of an event, and districts on days PDMA named only
  the district.
- **Weather**: ERA5 for training (what fell), on the 0.25° grid, area-weighted per tehsil plus the
  wettest cell; archived ECMWF, GFS and ICON forecasts (lead 0–3) from March 2024 for tuning and
  testing.
- **Static**: terrain from Copernicus DEM (HAND, slope, catchment), population from WorldPop scaled
  to the 2023 census.

## Features (7)

| Feature | Meaning |
|---|---|
| `log_precip_cell_max` | rain in the wettest 0.25° cell of the tehsil that day (log) |
| `log_precip_3d` | rain over the last 3 days (log) |
| `log_precip_max_1h` | heaviest hour of rain (log) |
| `log_precip_7d_antecedent` | rain in the week before (log) |
| `soil_moisture_0_7` | topsoil wetness (0–7 cm) |
| `log_population` | people living in the tehsil (log) |
| `log_high_villages` | villages on low ground beside large streams (log) |

19 candidate features were tried (`backend/app/risk/features.py`, `ALL_FEATURES`). With all 19,
tree models latched onto season, temperature and population and lost to a plain rain threshold.

## Model choice

Compared with the same folds and the same false-alarm rate (2.5 false alerts per tehsil per
season). "Hit rate" is the share of flood events with an alert on the day before, the day, or the
day after.

| Model | Hit rate, seasons held out | ROC-AUC | Hit rate, districts held out |
|---|---|---|---|
| **Logistic regression** | **0.42** | **0.81** | **0.37** |
| LightGBM | 0.34 | 0.77 | 0.35 |
| XGBoost | 0.33 | 0.79 | 0.34 |
| Extra trees | 0.30 | 0.80 | 0.30 |
| Random forest | 0.25 | 0.74 | 0.28 |
| Rain threshold (wettest cell) | 0.37 | 0.81 | — |

Logistic regression was chosen (gate G2 passed: it beats the best single rain threshold on hit rate
and PR-AUC). Probabilities are Platt-calibrated (Brier 0.0022 at a base rate of 0.0022). The
artefact is `backend/app/risk/artifacts/v1/` (`model.joblib`, `meta.json`).

## From probability to level

Each forecast model (ECMWF, GFS, ICON) is scored separately and the three probabilities are
averaged. Thresholds per lead day, tuned on the archived forecasts of 2024–2025
(`artifacts/v1/forecast_levels.json`), target about 8 / 2.5 / 0.5 false alerts per tehsil-season:

| Lead | Moderate | High | Very high |
|---|---|---|---|
| 1 day | 0.0037 | 0.0075 | 0.0115 |
| 2 days | 0.0034 | 0.0066 | 0.0106 |
| 3 days | 0.0036 | 0.0070 | 0.0108 |

Lead 0 uses the lead-1 thresholds. The "High" target is `NIGEHBAN_ALERT_FALSE_ALARM_TARGET_PER_SEASON`.
Levels come only from the model and these thresholds, never from the LLM.

**Reasons**: for each feature, the drop in log-odds when it is set to its median. The largest
become the plain-language reasons shown with every level.

## Evaluation

### Backtest on real forecasts (Jun–Sep 2024–2025, each season predicted by a model trained without it)

| Rule | Events | Caught at any lead | Caught 3 days ahead | Caught 2+ days ahead |
|---|---|---|---|---|
| **Nigehban model** | 41 | **22** | **19** | **20** |
| Model or river flag | 41 | 22 | 19 | 20 |
| Rain threshold (33 mm, wettest cell) | 41 | 16 | 14 | 15 |

At about 2.5–3 false alerts per tehsil per season. Levels tuned on ERA5 instead of forecasts fired
far too rarely (7 of 41 at lead 1), which is why levels are tuned on forecasts.

### Replays of known floods

- **Buner, 15 Aug 2025** (cloudburst): flagged from the forecasts issued on 14 Aug; the alert
  engine sends Buner alerts once, with no duplicates (`reports/m9_alerts_replay.md`).
- **Swat River, 27 Jun 2025**: missed; the forecast rain the day before was too low. GloFAS also
  missed it (`reports/m5_replay_check.md`, `reports/m6_glofas.md`).

### What was tried and not kept

| Idea | Result |
|---|---|
| GloFAS river flag | Adds no extra hits in the backtest (kept as a flag that triggers alerts and "be ready" advice) |
| NASA IMERG satellite rain | Same-day IMERG raises hits from 0.42 to 0.47, but exists only after the rain; past days lower it to 0.38. Not used for forecasting; shown as an observed-rain layer |
| All 19 features / tree models | Overfit with 89 positives |

## Limits

- 89 positive days is a small sample; confidence intervals are wide.
- PDMA reports under-record floods in remote places, so some "false alerts" may be real events.
- Weather models are coarse (about 9–25 km); small cloudbursts are the hardest case.
- 90 m terrain blurs narrow valleys (30 m is used for Swat village bands).
- About half of past floods were missed in the backtest. Nigehban must be used alongside
  official warnings.

## Retraining

```powershell
.venv\Scripts\python -m pipelines.risk.experiment     # compare feature sets and models
.venv\Scripts\python -m pipelines.risk.train          # train, calibrate, write artifacts/v1 and reports/m5_risk_qa.md
.venv\Scripts\python -m pipelines.backtest.run        # backtest on archived forecasts -> reports/m7_backtest.md
.venv\Scripts\python -m pipelines.risk.replay_check   # replays of known floods -> reports/m5_replay_check.md
```
