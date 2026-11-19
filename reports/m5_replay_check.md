# M5 replay check

Generated 2026-11-19 by `python -m pipelines.risk.replay_check`. Forecasts as they were issued 1–3 days before each demo day (Open-Meteo archived runs, ECMWF + GFS + ICON averaged), scored by the shipped model with the forecast-tuned levels.

## Buner cloudburst, 2025-08-15

Tehsils with a PDMA flood report that day: bajaur__mamund, bajaur__salarzai, buner__daggar, buner__gagra, mansehra__baffa_pakhal, mansehra__mansehra, swat__babuzai, swat__bahrain, swat__barikot, swat__kabal, swat__khwaza_khela, swat__matta_kharirai.
Flooded tehsils at high or above: ['buner__gagra (lead 1)', 'buner__gagra (lead 2)', 'mansehra__baffa_pakhal (lead 1)', 'mansehra__baffa_pakhal (lead 2)', 'mansehra__baffa_pakhal (lead 3)', 'mansehra__mansehra (lead 1)', 'mansehra__mansehra (lead 2)', 'mansehra__mansehra (lead 3)', 'swat__babuzai (lead 1)', 'swat__babuzai (lead 2)', 'swat__babuzai (lead 3)', 'swat__barikot (lead 1)', 'swat__barikot (lead 2)', 'swat__barikot (lead 3)', 'swat__kabal (lead 1)', 'swat__kabal (lead 2)', 'swat__kabal (lead 3)', 'swat__khwaza_khela (lead 1)', 'swat__matta_kharirai (lead 1)', 'swat__matta_kharirai (lead 3)']

| issued | lead (days) | tehsil | PDMA flood that day | level | probability | top reasons |
|---|---|---|---|---|---|---|
| 2025-08-14 | 1 | swat__kabal | yes | very_high | 0.0173 | rain in the wettest part of the tehsil: 49 mm; rain over 3 days: 66 mm; wet topsoil (0.40 m³/m³) |
| 2025-08-14 | 1 | shangla__chakisar |  | very_high | 0.0154 | rain in the wettest part of the tehsil: 43 mm; rain over 3 days: 70 mm; wet topsoil (0.40 m³/m³) |
| 2025-08-14 | 1 | mansehra__mansehra | yes | very_high | 0.015 | rain in the wettest part of the tehsil: 76 mm; rain over 3 days: 75 mm; population |
| 2025-08-14 | 1 | swat__babuzai | yes | very_high | 0.0147 | rain in the wettest part of the tehsil: 30 mm; wet topsoil (0.40 m³/m³); rain over 3 days: 48 mm |
| 2025-08-14 | 1 | shangla__alpuri |  | very_high | 0.0142 | rain in the wettest part of the tehsil: 46 mm; rain over 3 days: 73 mm; wet topsoil (0.40 m³/m³) |
| 2025-08-14 | 1 | shangla__puran |  | very_high | 0.0133 | rain in the wettest part of the tehsil: 43 mm; rain over 3 days: 67 mm; wet topsoil (0.40 m³/m³) |
| 2025-08-14 | 1 | mansehra__baffa_pakhal | yes | very_high | 0.0119 | rain in the wettest part of the tehsil: 41 mm; rain over 3 days: 63 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-14 | 1 | swat__matta_kharirai | yes | very_high | 0.0118 | rain in the wettest part of the tehsil: 48 mm; rain over 3 days: 50 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-14 | 1 | swat__barikot | yes | very_high | 0.0116 | rain in the wettest part of the tehsil: 40 mm; rain over 3 days: 56 mm; wet topsoil (0.38 m³/m³) |
| 2025-08-14 | 1 | shangla__martoong |  | high | 0.0095 | rain in the wettest part of the tehsil: 48 mm; rain over 3 days: 63 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-14 | 1 | swat__matta_sebujni |  | high | 0.0095 | rain in the wettest part of the tehsil: 48 mm; rain over 3 days: 68 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-14 | 1 | shangla__bisham |  | high | 0.0093 | rain in the wettest part of the tehsil: 46 mm; rain over 3 days: 68 mm; wet topsoil (0.39 m³/m³) |
| 2025-08-14 | 1 | buner__mandanr |  | high | 0.0087 | rain in the wettest part of the tehsil: 60 mm; rain over 3 days: 62 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-14 | 1 | buner__khado_khel |  | high | 0.0085 | rain in the wettest part of the tehsil: 52 mm; rain over 3 days: 59 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-14 | 1 | swat__charbagh |  | high | 0.0084 | rain in the wettest part of the tehsil: 22 mm; wet topsoil (0.40 m³/m³); rain over 3 days: 43 mm |
| 2025-08-14 | 1 | swat__khwaza_khela | yes | high | 0.0082 | rain in the wettest part of the tehsil: 18 mm; wet topsoil (0.39 m³/m³); rain over 3 days: 48 mm |
| 2025-08-14 | 1 | shangla__makhuzai |  | high | 0.0081 | rain in the wettest part of the tehsil: 43 mm; wet topsoil (0.40 m³/m³); rain over 3 days: 46 mm |
| 2025-08-14 | 1 | buner__gagra | yes | high | 0.008 | rain in the wettest part of the tehsil: 48 mm; rain over 3 days: 51 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-14 | 1 | mansehra__oghi |  | moderate | 0.0073 | rain in the wettest part of the tehsil: 71 mm; rain over 3 days: 88 mm; population |
| 2025-08-14 | 1 | mansehra__bala_kot |  | moderate | 0.0067 | rain in the wettest part of the tehsil: 47 mm; rain over 3 days: 39 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-14 | 1 | buner__daggar | yes | moderate | 0.0058 | rain in the wettest part of the tehsil: 26 mm; rain over 3 days: 45 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-14 | 1 | bajaur__utman_khel |  | moderate | 0.0054 | rain in the wettest part of the tehsil: 20 mm; rain over 3 days: 41 mm; wet topsoil (0.35 m³/m³) |
| 2025-08-14 | 1 | mansehra__darband |  | moderate | 0.0052 | rain in the wettest part of the tehsil: 72 mm; rain over 3 days: 75 mm; wet topsoil (0.30 m³/m³) |
| 2025-08-14 | 1 | swat__bahrain | yes | moderate | 0.0043 | rain in the wettest part of the tehsil: 46 mm; rain over 3 days: 33 mm; wet topsoil (0.30 m³/m³) |
| 2025-08-14 | 1 | bajaur__khar |  | moderate | 0.004 | rain in the wettest part of the tehsil: 20 mm; rain over 3 days: 32 mm; population |
| 2025-08-14 | 1 | bajaur__mamund | yes | moderate | 0.0038 | rain in the wettest part of the tehsil: 11 mm; rain over 3 days: 29 mm; population |
| 2025-08-14 | 1 | bajaur__barang |  | low | 0.0034 | rain in the wettest part of the tehsil: 22 mm; rain over 3 days: 30 mm; villages on low ground by rivers |
| 2025-08-14 | 1 | bajaur__salarzai | yes | low | 0.0033 | rain over 3 days: 31 mm; rain in the wettest part of the tehsil: 10 mm; population |
| 2025-08-14 | 1 | bajaur__nawagai |  | low | 0.0019 | rain over 3 days: 24 mm; rain in the wettest part of the tehsil: 6 mm; villages on low ground by rivers |
| 2025-08-14 | 1 | bajaur__bar_chamarkand |  | low | 0.0006 | rain over 3 days: 24 mm; villages on low ground by rivers; rain in the wettest part of the tehsil: 6 mm |
| 2025-08-14 | 1 | swat__kalam |  | low | 0.0006 | rain in the wettest part of the tehsil: 6 mm; rain over 3 days: 11 mm; rain in the week before: 17 mm |
| 2025-08-13 | 2 | swat__babuzai | yes | very_high | 0.0157 | rain in the wettest part of the tehsil: 41 mm; wet topsoil (0.39 m³/m³); rain over 3 days: 55 mm |
| 2025-08-13 | 2 | mansehra__baffa_pakhal | yes | very_high | 0.0147 | rain in the wettest part of the tehsil: 76 mm; rain over 3 days: 77 mm; wet topsoil (0.35 m³/m³) |
| 2025-08-13 | 2 | shangla__chakisar |  | very_high | 0.0145 | rain in the wettest part of the tehsil: 57 mm; rain over 3 days: 91 mm; wet topsoil (0.38 m³/m³) |
| 2025-08-13 | 2 | swat__kabal | yes | very_high | 0.0133 | rain in the wettest part of the tehsil: 41 mm; rain over 3 days: 50 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-13 | 2 | mansehra__mansehra | yes | very_high | 0.0131 | rain in the wettest part of the tehsil: 63 mm; rain over 3 days: 65 mm; population |
| 2025-08-13 | 2 | shangla__puran |  | very_high | 0.0125 | rain in the wettest part of the tehsil: 57 mm; rain over 3 days: 87 mm; wet topsoil (0.38 m³/m³) |
| 2025-08-13 | 2 | shangla__alpuri |  | very_high | 0.0118 | rain in the wettest part of the tehsil: 59 mm; rain over 3 days: 55 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-13 | 2 | swat__barikot | yes | high | 0.0096 | rain in the wettest part of the tehsil: 30 mm; rain over 3 days: 51 mm; wet topsoil (0.36 m³/m³) |
| 2025-08-13 | 2 | swat__charbagh |  | high | 0.0095 | rain in the wettest part of the tehsil: 34 mm; wet topsoil (0.38 m³/m³); rain over 3 days: 47 mm |
| 2025-08-13 | 2 | shangla__martoong |  | high | 0.0091 | rain in the wettest part of the tehsil: 65 mm; rain over 3 days: 73 mm; wet topsoil (0.36 m³/m³) |
| 2025-08-13 | 2 | shangla__bisham |  | high | 0.0087 | rain in the wettest part of the tehsil: 66 mm; rain over 3 days: 74 mm; wet topsoil (0.36 m³/m³) |
| 2025-08-13 | 2 | shangla__makhuzai |  | high | 0.0082 | rain in the wettest part of the tehsil: 57 mm; wet topsoil (0.39 m³/m³); rain over 3 days: 60 mm |
| 2025-08-13 | 2 | buner__gagra | yes | high | 0.0076 | rain in the wettest part of the tehsil: 65 mm; rain over 3 days: 49 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-13 | 2 | mansehra__bala_kot |  | high | 0.0076 | rain in the wettest part of the tehsil: 64 mm; rain over 3 days: 36 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-13 | 2 | buner__khado_khel |  | moderate | 0.0065 | rain in the wettest part of the tehsil: 24 mm; rain over 3 days: 46 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-13 | 2 | buner__daggar | yes | moderate | 0.0061 | rain in the wettest part of the tehsil: 37 mm; rain over 3 days: 43 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-13 | 2 | swat__matta_kharirai | yes | moderate | 0.006 | rain in the wettest part of the tehsil: 15 mm; rain over 3 days: 27 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-13 | 2 | buner__mandanr |  | moderate | 0.0058 | rain in the wettest part of the tehsil: 32 mm; rain over 3 days: 46 mm; wet topsoil (0.32 m³/m³) |
| 2025-08-13 | 2 | mansehra__oghi |  | moderate | 0.0055 | rain in the wettest part of the tehsil: 45 mm; rain over 3 days: 65 mm; population |
| 2025-08-13 | 2 | swat__matta_sebujni |  | moderate | 0.0055 | rain in the wettest part of the tehsil: 34 mm; rain over 3 days: 36 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-13 | 2 | bajaur__utman_khel |  | moderate | 0.0051 | rain in the wettest part of the tehsil: 23 mm; rain over 3 days: 54 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-13 | 2 | swat__khwaza_khela | yes | moderate | 0.0042 | wet topsoil (0.36 m³/m³); rain over 3 days: 26 mm; rain in the wettest part of the tehsil: 8 mm |
| 2025-08-13 | 2 | bajaur__khar |  | moderate | 0.0038 | rain in the wettest part of the tehsil: 23 mm; rain over 3 days: 33 mm; population |
| 2025-08-13 | 2 | mansehra__darband |  | moderate | 0.0037 | rain in the wettest part of the tehsil: 45 mm; rain over 3 days: 54 mm |
| 2025-08-13 | 2 | bajaur__mamund | yes | moderate | 0.0035 | rain in the wettest part of the tehsil: 16 mm; rain over 3 days: 28 mm; population |
| 2025-08-13 | 2 | bajaur__barang |  | low | 0.0033 | rain in the wettest part of the tehsil: 23 mm; rain over 3 days: 31 mm; villages on low ground by rivers |
| 2025-08-13 | 2 | swat__bahrain | yes | low | 0.0033 | rain in the wettest part of the tehsil: 24 mm; rain over 3 days: 22 mm; wet topsoil (0.30 m³/m³) |
| 2025-08-13 | 2 | bajaur__salarzai | yes | low | 0.0031 | rain in the wettest part of the tehsil: 16 mm; rain over 3 days: 33 mm; population |
| 2025-08-13 | 2 | bajaur__nawagai |  | low | 0.0015 | rain over 3 days: 19 mm; villages on low ground by rivers; rain in the wettest part of the tehsil: 6 mm |
| 2025-08-13 | 2 | bajaur__bar_chamarkand |  | low | 0.0005 | villages on low ground by rivers; rain over 3 days: 19 mm; rain in the wettest part of the tehsil: 6 mm |
| 2025-08-13 | 2 | swat__kalam |  | low | 0.0005 | rain in the wettest part of the tehsil: 5 mm; rain in the week before: 16 mm; rain over 3 days: 10 mm |
| 2025-08-12 | 3 | shangla__chakisar |  | very_high | 0.0133 | rain in the wettest part of the tehsil: 49 mm; rain over 3 days: 77 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-12 | 3 | swat__kabal | yes | very_high | 0.0122 | rain in the wettest part of the tehsil: 40 mm; rain over 3 days: 48 mm; wet topsoil (0.35 m³/m³) |
| 2025-08-12 | 3 | shangla__alpuri |  | very_high | 0.0113 | rain in the wettest part of the tehsil: 59 mm; rain over 3 days: 75 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | shangla__puran |  | very_high | 0.0113 | rain in the wettest part of the tehsil: 49 mm; rain over 3 days: 72 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-12 | 3 | swat__babuzai | yes | high | 0.0106 | rain in the wettest part of the tehsil: 20 mm; wet topsoil (0.37 m³/m³); rain over 3 days: 36 mm |
| 2025-08-12 | 3 | mansehra__baffa_pakhal | yes | high | 0.0086 | rain in the wettest part of the tehsil: 28 mm; rain over 3 days: 51 mm; wet topsoil (0.35 m³/m³) |
| 2025-08-12 | 3 | mansehra__mansehra | yes | high | 0.0083 | rain in the wettest part of the tehsil: 32 mm; rain over 3 days: 52 mm; population |
| 2025-08-12 | 3 | swat__matta_kharirai | yes | high | 0.0082 | rain in the wettest part of the tehsil: 39 mm; rain over 3 days: 38 mm; population |
| 2025-08-12 | 3 | swat__barikot | yes | high | 0.008 | rain in the wettest part of the tehsil: 26 mm; rain over 3 days: 40 mm; wet topsoil (0.35 m³/m³) |
| 2025-08-12 | 3 | shangla__martoong |  | high | 0.0077 | rain in the wettest part of the tehsil: 49 mm; rain over 3 days: 61 mm; wet topsoil (0.35 m³/m³) |
| 2025-08-12 | 3 | shangla__bisham |  | high | 0.0076 | rain in the wettest part of the tehsil: 61 mm; rain over 3 days: 64 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | shangla__makhuzai |  | moderate | 0.0069 | rain in the wettest part of the tehsil: 49 mm; rain over 3 days: 40 mm; wet topsoil (0.37 m³/m³) |
| 2025-08-12 | 3 | buner__gagra | yes | moderate | 0.0068 | rain in the wettest part of the tehsil: 49 mm; rain over 3 days: 41 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | swat__charbagh |  | moderate | 0.0067 | rain in the wettest part of the tehsil: 21 mm; rain over 3 days: 35 mm; wet topsoil (0.36 m³/m³) |
| 2025-08-12 | 3 | swat__khwaza_khela | yes | moderate | 0.0061 | rain in the wettest part of the tehsil: 20 mm; rain over 3 days: 38 mm; wet topsoil (0.32 m³/m³) |
| 2025-08-12 | 3 | mansehra__bala_kot |  | moderate | 0.006 | rain in the wettest part of the tehsil: 32 mm; rain over 3 days: 25 mm; wet topsoil (0.34 m³/m³) |
| 2025-08-12 | 3 | swat__matta_sebujni |  | moderate | 0.0059 | rain in the wettest part of the tehsil: 39 mm; rain over 3 days: 52 mm; wet topsoil (0.31 m³/m³) |
| 2025-08-12 | 3 | buner__daggar | yes | moderate | 0.005 | rain in the wettest part of the tehsil: 28 mm; rain over 3 days: 37 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | buner__mandanr |  | moderate | 0.0048 | rain in the wettest part of the tehsil: 25 mm; rain over 3 days: 38 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | swat__bahrain | yes | moderate | 0.0047 | rain in the wettest part of the tehsil: 59 mm; rain over 3 days: 22 mm; wet topsoil (0.29 m³/m³) |
| 2025-08-12 | 3 | buner__khado_khel |  | moderate | 0.0046 | rain in the wettest part of the tehsil: 16 mm; rain over 3 days: 28 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | mansehra__oghi |  | moderate | 0.0042 | rain in the wettest part of the tehsil: 32 mm; rain over 3 days: 60 mm; population |
| 2025-08-12 | 3 | bajaur__utman_khel |  | low | 0.0034 | rain in the wettest part of the tehsil: 12 mm; rain over 3 days: 32 mm; wet topsoil (0.33 m³/m³) |
| 2025-08-12 | 3 | bajaur__khar |  | low | 0.003 | rain in the wettest part of the tehsil: 14 mm; rain over 3 days: 23 mm; population |
| 2025-08-12 | 3 | mansehra__darband |  | low | 0.0029 | rain in the wettest part of the tehsil: 32 mm; rain over 3 days: 47 mm; wet topsoil (0.29 m³/m³) |
| 2025-08-12 | 3 | bajaur__mamund | yes | low | 0.0028 | rain in the wettest part of the tehsil: 10 mm; rain over 3 days: 22 mm; population |
| 2025-08-12 | 3 | bajaur__barang |  | low | 0.0025 | rain in the wettest part of the tehsil: 14 mm; rain over 3 days: 20 mm; villages on low ground by rivers |
| 2025-08-12 | 3 | bajaur__salarzai | yes | low | 0.0025 | rain in the wettest part of the tehsil: 10 mm; rain over 3 days: 28 mm; population |
| 2025-08-12 | 3 | bajaur__nawagai |  | low | 0.0013 | rain in the wettest part of the tehsil: 6 mm; villages on low ground by rivers; rain over 3 days: 16 mm |
| 2025-08-12 | 3 | swat__kalam |  | low | 0.0005 | rain in the week before: 12 mm; rain in the wettest part of the tehsil: 4 mm |
| 2025-08-12 | 3 | bajaur__bar_chamarkand |  | low | 0.0004 | villages on low ground by rivers; rain in the wettest part of the tehsil: 6 mm; rain over 3 days: 16 mm |

## Swat River flood, 2025-06-27

Tehsils with a PDMA flood report that day: bajaur__utman_khel, lower_dir__munda, swat__babuzai, swat__matta_kharirai.
Flooded tehsils at high or above: []

| issued | lead (days) | tehsil | PDMA flood that day | level | probability | top reasons |
|---|---|---|---|---|---|---|
| 2025-06-26 | 1 | swat__babuzai | yes | low | 0.0036 | rain over 3 days: 36 mm; rain in the wettest part of the tehsil: 11 mm; population |
| 2025-06-26 | 1 | swat__kabal |  | low | 0.0029 | rain over 3 days: 39 mm; rain in the wettest part of the tehsil: 11 mm; population |
| 2025-06-26 | 1 | swat__barikot |  | low | 0.0027 | rain over 3 days: 53 mm; rain in the wettest part of the tehsil: 14 mm; villages on low ground by rivers |
| 2025-06-26 | 1 | swat__matta_kharirai | yes | low | 0.0027 | rain in the wettest part of the tehsil: 10 mm; rain over 3 days: 23 mm; population |
| 2025-06-26 | 1 | swat__bahrain |  | low | 0.0026 | rain in the wettest part of the tehsil: 12 mm; rain over 3 days: 21 mm; wet topsoil (0.31 m³/m³) |
| 2025-06-26 | 1 | swat__charbagh |  | low | 0.0021 | rain over 3 days: 27 mm; rain in the wettest part of the tehsil: 7 mm; wet topsoil (0.30 m³/m³) |
| 2025-06-26 | 1 | swat__khwaza_khela |  | low | 0.0019 | rain over 3 days: 23 mm; rain in the wettest part of the tehsil: 6 mm; population |
| 2025-06-26 | 1 | swat__matta_sebujni |  | low | 0.0015 | rain in the wettest part of the tehsil: 10 mm; rain over 3 days: 24 mm |
| 2025-06-26 | 1 | swat__kalam |  | low | 0.0007 | rain in the week before: 9 mm; heaviest hourly rain: 0 mm |
| 2025-06-25 | 2 | swat__babuzai | yes | moderate | 0.0035 | rain in the wettest part of the tehsil: 13 mm; rain over 3 days: 33 mm; population |
| 2025-06-25 | 2 | swat__kabal |  | low | 0.0029 | rain in the wettest part of the tehsil: 13 mm; rain over 3 days: 32 mm; population |
| 2025-06-25 | 2 | swat__charbagh |  | low | 0.0025 | rain in the wettest part of the tehsil: 13 mm; rain over 3 days: 27 mm; villages on low ground by rivers |
| 2025-06-25 | 2 | swat__matta_kharirai | yes | low | 0.0025 | rain in the wettest part of the tehsil: 10 mm; rain over 3 days: 19 mm; population |
| 2025-06-25 | 2 | swat__barikot |  | low | 0.0024 | rain over 3 days: 41 mm; rain in the wettest part of the tehsil: 14 mm; villages on low ground by rivers |
| 2025-06-25 | 2 | swat__bahrain |  | low | 0.002 | rain in the wettest part of the tehsil: 12 mm; rain over 3 days: 9 mm; wet topsoil (0.30 m³/m³) |
| 2025-06-25 | 2 | swat__khwaza_khela |  | low | 0.0019 | rain in the wettest part of the tehsil: 8 mm; rain over 3 days: 20 mm; population |
| 2025-06-25 | 2 | swat__matta_sebujni |  | low | 0.0016 | rain in the wettest part of the tehsil: 14 mm; rain over 3 days: 21 mm |
| 2025-06-25 | 2 | swat__kalam |  | low | 0.0006 | rain in the week before: 8 mm; heaviest hourly rain: 0 mm |
| 2025-06-24 | 3 | swat__babuzai | yes | low | 0.0032 | rain in the wettest part of the tehsil: 8 mm; rain over 3 days: 28 mm; population |
| 2025-06-24 | 3 | swat__barikot |  | low | 0.0031 | rain in the wettest part of the tehsil: 14 mm; rain over 3 days: 39 mm; villages on low ground by rivers |
| 2025-06-24 | 3 | swat__kabal |  | low | 0.003 | rain in the wettest part of the tehsil: 12 mm; rain over 3 days: 31 mm; population |
| 2025-06-24 | 3 | swat__matta_kharirai | yes | low | 0.0022 | rain in the wettest part of the tehsil: 10 mm; population; rain over 3 days: 16 mm |
| 2025-06-24 | 3 | swat__charbagh |  | low | 0.0017 | rain over 3 days: 22 mm; rain in the wettest part of the tehsil: 6 mm; villages on low ground by rivers |
| 2025-06-24 | 3 | swat__matta_sebujni |  | low | 0.0015 | rain in the wettest part of the tehsil: 11 mm; rain over 3 days: 22 mm |
| 2025-06-24 | 3 | swat__khwaza_khela |  | low | 0.0014 | rain over 3 days: 17 mm; rain in the wettest part of the tehsil: 5 mm; population |
| 2025-06-24 | 3 | swat__bahrain |  | low | 0.0013 | rain in the wettest part of the tehsil: 5 mm; wet topsoil (0.31 m³/m³); population |
| 2025-06-24 | 3 | swat__kalam |  | low | 0.0006 | rain in the week before: 9 mm; heaviest hourly rain: 0 mm |

## Reading these results

- **Levels used here were tuned on the 2024-2025 forecasts, which include these days**, so these
  replays are flattering. The fair test is the cross-season backtest in reports/m7_backtest.md
  (each season's levels tuned on the other season).
- **Buner day (15 Aug 2025):** most flooded tehsils were at high 1-3 days ahead. The forecasts
  showed heavy rain across Swat, Buner and Mansehra.
- **Swat day (27 Jun 2025):** missed (moderate at best, 2 days ahead in Babuzai). Every forecast
  had only 10-14 mm for these tehsils, against about 57 mm that fell. The GloFAS river flag did not
  fire either: GloFAS showed an ordinary flow at Mingora that day.
- Probabilities look small because floods are rare (about 0.2% of tehsil-days); "high" means
  roughly 3-5 times the usual chance. The board and alerts show levels, not raw probabilities.
