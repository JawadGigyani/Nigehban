# M6 GloFAS river levels

Generated 2026-11-19 by `python -m pipelines.rivers.qa`. Source: Copernicus GloFAS via the
Open-Meteo Flood API (CC BY 4.0). Method: Gumbel fit to Apr-Oct yearly peaks 1997-2025 at the main-channel GloFAS cell (highest mean discharge within 0.1 degrees).

## River points

| point | tehsils | cell moved (km) | q2 | q5 | q20 | 2022 peak | 2022 rank of 29 |
|---|---|---|---|---|---|---|---|
| Swat River at Kalam | swat__kalam | 11.1 | 185 | 237 | 305 | 162 | 21 |
| Swat River at Bahrain | swat__bahrain | 12.0 | 291 | 370 | 472 | 232 | 24 |
| Swat River at Khwazakhela | swat__khwaza_khela, swat__matta_kharirai, swat__matta_sebujni, swat__charbagh | 14.4 | 306 | 389 | 497 | 238 | 25 |
| Swat River at Mingora (Fizagat) | swat__babuzai, swat__kabal | 9.20 | 318 | 407 | 523 | 241 | 25 |
| Swat River at Barikot | swat__barikot | 9.20 | 325 | 417 | 537 | 248 | 25 |
| Swat River at Chakdara | lower_dir__adenzai, malakand__bat_khela, malakand__dargai | 9.20 | 335 | 430 | 552 | 261 | 25 |
| Panjkora River at Timergara | lower_dir__timergara, lower_dir__balambat, lower_dir__munda | 14.4 | 130 | 185 | 256 | 170 | 9 |
| Indus River at Besham | shangla__bisham | 11.1 | 10067 | 12428 | 15491 | 12022 | 8 |
| Kunhar River at Balakot | mansehra__bala_kot | 14.4 | 426 | 568 | 753 | 302 | 25 |
| Barandu River at Daggar | buner__daggar, buner__gagra | 10.7 | 57.8 | 95.7 | 145 | 34.0 | 22 |

"Cell moved" is the distance from the named place to the chosen GloFAS cell: the cell with the most
water within 0.1° (about 11 km), which tends to sit a little downstream.

## How GloFAS saw known floods

| point | 2022-08-26 | 2022-08-27 | 2025-06-27 | 2025-08-15 |
|---|---|---|---|---|
| barandu_daggar | 56% | 59% | 19% | 68% |
| indus_besham | 50% | 55% | 98% | 58% |
| kunhar_balakot | 29% | 30% | 64% | 43% |
| panjkora_timergara | 90% | 106% | 45% | 82% |
| swat_bahrain | 48% | 52% | 67% | 42% |
| swat_barikot | 66% | 71% | 64% | 65% |
| swat_chakdara | 69% | 73% | 65% | 69% |
| swat_kalam | 42% | 46% | 67% | 38% |
| swat_khwazakhela | 57% | 62% | 65% | 54% |
| swat_mingora | 64% | 69% | 65% | 62% |

Values are the day's GloFAS flow as a share of the 2-year flow.

## Finding

GloFAS does not see the floods that matter here. The Aug 2022 Swat flood, which destroyed parts of
Kalam, Bahrain and Mingora, ranks low among GloFAS's 29 yearly peaks at every Swat point, and on the
two 2025 demo days the river flows are ordinary. In the M7 backtest the river flag added no caught
events in any season. It stays in the system as a secondary signal (it almost never fires), and the
alert rule remains "model high or above, or river flag".

Better river input for later: the observed gauge flows in the Flood Forecasting Division's daily
bulletins (for example Swat at Chakdara and Munda) during the monsoon.
