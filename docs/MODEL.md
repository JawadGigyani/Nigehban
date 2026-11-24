# Risk model

**In one line:** a calibrated logistic regression on 7 inputs predicts, for each tehsil and day, the
chance of a flash flood as PDMA would report it.

## At a glance

| | |
|:--|:--|
| **Predicts** | Flood or no flood, per tehsil, today and the next 3 days |
| **Area** | 48 tehsils in 9 districts of northern Khyber Pakhtunkhwa |
| **Season** | June to September |
| **Trained on** | 40,119 tehsil-days (2019–2025), 89 of them with a flood |
| **Model** | Logistic regression, Platt-calibrated (`backend/app/risk/artifacts/v1/`) |
| **Result** | 22 of 41 floods caught on real forecasts, against 16 for a rain threshold |

## The data

- **Floods:** 4,922 PDMA daily reports (July 2019 to April 2026), read by an LLM into a fixed form,
  geocoded to tehsils and de-duplicated. Personal names are removed first. Counted as floods: flash
  floods, floods, cloudbursts and drownings.
- **Weather:** ERA5 for training (the rain that fell). Archived ECMWF, GFS and ICON forecasts
  (from March 2024) for tuning and testing.
- **Land:** height above the nearest stream, from the Copernicus elevation model; population from
  WorldPop, scaled to the 2023 census.

## The 7 inputs

| Input | Meaning |
|:--|:--|
| Heaviest rain in the tehsil | Rain in its wettest 0.25° cell that day |
| Rain over 3 days | Rain in the last three days |
| Heaviest hour | The most intense hour of rain |
| Rain the week before | How wet the past week was |
| Topsoil wetness | Soil moisture, 0–7 cm |
| People | Population of the tehsil |
| Villages on low ground | Villages beside large streams, on low ground |

Rain values are log-scaled. 19 inputs were tried; more inputs made the model worse.

## Why this model

All compared at the same false-alarm rate, on seasons and districts the model never saw.

| Model | Floods caught (seasons held out) | Floods caught (districts held out) |
|:--|:--:|:--:|
| **Logistic regression** | **42%** | **37%** |
| LightGBM | 34% | 35% |
| XGBoost | 33% | 34% |
| Extra trees | 30% | 30% |
| Random forest | 25% | 28% |
| Rain threshold | 37% | — |

With only 89 flood days, tree models learned noise. The simple model held up best.

## From probability to level

The three weather models are scored separately and averaged. Fixed thresholds, tuned on real
forecasts, set the level:

| Days ahead | Moderate | High | Very high |
|:--:|:--:|:--:|:--:|
| 1 | 0.0037 | 0.0075 | 0.0115 |
| 2 | 0.0034 | 0.0066 | 0.0106 |
| 3 | 0.0036 | 0.0070 | 0.0108 |

Today uses the 1-day thresholds. High is set for about 2.5 false alerts per tehsil per season.

## How well it works

**Backtest** on real archived forecasts, June–September 2024–2025, each season predicted by a model
that never saw it:

| Method | Floods caught (of 41) | 3 days early | 2+ days early |
|:--|:--:|:--:|:--:|
| **Nigehban** | **22** | **19** | **20** |
| Rain threshold (33 mm) | 16 | 14 | 15 |

**Real floods replayed:**

- **Buner, 15 Aug 2025** (cloudburst): flagged from the forecasts of 14 Aug.
- **Swat River, 27 Jun 2025:** missed. The forecast rain the day before was too low.

**Tried and dropped:**

| Idea | What happened |
|:--|:--|
| GloFAS river flow as an input | No extra floods caught; kept only as a flag |
| NASA satellite rain as an input | Helps only after rain falls; shown as a map layer instead |
| All 19 inputs, tree models | Overfit |

## Limits

- 89 flood days is a small sample.
- PDMA misses some floods in remote places, so some "false alarms" may be real.
- Weather models see about 9–25 km; small cloudbursts are the hardest case.
- About half of past floods were missed. Use alongside official warnings.

## Retrain

```bash
python -m pipelines.risk.experiment     # compare inputs and models
python -m pipelines.risk.train          # train and calibrate
python -m pipelines.backtest.run        # test on archived forecasts
python -m pipelines.risk.replay_check   # replay known floods
```

Full tables: [risk_model.md](../reports/risk_model.md) · [backtest.md](../reports/backtest.md) ·
[rivers_glofas.md](../reports/rivers_glofas.md) · [imerg_vs_era5.md](../reports/imerg_vs_era5.md)
