# M3 terrain + M4b facilities QA

Generated 2026-11-19 by `python -m pipelines.terrain.qa`.

## Done-when check

| Check | Result |
|---|---|
| Every in-scope tehsil has at least 1 village | True (10511 villages) |
| Every in-scope tehsil has at least 1 shelter or higher-ground point | True |
| Tehsils with an OSM shelter building | 30 of 48 |
| HAND overlap report | below (validated on PDMA-named villages; UNOSAT extents not used, see limits) |

## Method

- DEM: Copernicus GLO-90 (90 m), 8 tiles, run on a laptop (about 5 minutes).
  The 30 m DEM for the whole region does not fit in this machine's memory; a
  30 m run for Swat alone is possible with
  `python -m pipelines.terrain.fetch_dem --res 30 --bbox 72.0 34.6 72.9 35.9`
  and the same build script (Colab if needed).
- Swat village bands use a 30 m run (Copernicus GLO-30, `--tag swat30`, merged by
  `pipelines.terrain.merge_detail`); it agreed with 90 m for 92% of Swat villages and moved
  the rest mostly up a band (narrow side streams). Tehsil statics stay at 90 m everywhere.
- Flow routing with pysheds (pits and depressions filled, flats resolved, D8).
- HAND reference streams: cells draining at least 10 km². Drainage density uses 1 km².
- Village band: lowest HAND within about 180 m of the village point (5 × 5 cells),
  because the point is the village centre while flooding starts at its riverside edge.
  - **high**: lowest nearby HAND under 5 m, next to a river draining at least 50 km²
  - **medium**: lowest nearby HAND under 8 m (any stream)
  - **low**: otherwise
- Population: WorldPop 2020 (1 km), spread over 90 m cells, scaled to the 2023 census tehsil totals.

## Validation on villages named in PDMA flood reports (M1)

84 villages appear by name in positive PDMA events (geocoded to the village).

| band | villages named in PDMA flood reports | all other villages |
|---|---|---|
| high | 26% | 13% |
| medium | 24% | 14% |
| low | 50% | 73% |

Villages that flooded are about twice as likely to be in the high band as other
villages. Half are still in the low band: many PDMA village names are where the
victim lived, the gazetteer point can be hundreds of metres off, and 90 m cells
blur narrow valley floors. The bands are a guide for the advisory, not a flood map.

The plan's first thresholds (point HAND < 3 m high, 3–8 m medium) put only 3% of
villages in the high band and showed no difference between flooded and other
villages, so they were replaced by the rule above.

## Facilities

| Kind | Rows |
|---|---|
| fire | 1 |
| health | 56 |
| high_ground | 142 |
| police | 37 |
| rescue_1122 | 17 |
| shelter | 496 |

- **shelter**: OSM schools, colleges, government buildings (priority 1) and mosques
  (priority 2). OSM is sparse in KP: 18 in-scope tehsils have none.
- **high_ground**: villages in the low band (lowest nearby HAND 15–120 m, at least
  300 m from a stream) closest to the most high-band villages. Not a building: the
  advisory says "move to higher ground, for example ...".
- **rescue_1122**: 2 from OSM plus 15 from news reports and the Rescue 1122 KP site,
  placed at the town centre. 8 are reported stations; 7 are district services whose
  station location is not confirmed.
- Every row is `verified=false` and shown as unverified on the board.

## Per tehsil (in scope)

| tehsil_id | mean slope ° | low-HAND land % | largest catchment km² | population | people on low-HAND land | high | medium | low | shelters | high ground | rescue 1122 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bajaur__bar_chamarkand | 22.6 | 0.90 | 17 | 3574 | 55 | 0 | 1 | 2 | 0 | 1 | 0 |
| bajaur__barang | 24.2 | 2.30 | 12514 | 90082 | 2208 | 7 | 13 | 109 | 1 | 3 | 0 |
| bajaur__khar | 8.39 | 6.80 | 894 | 301778 | 29461 | 25 | 16 | 126 | 1 | 3 | 1 |
| bajaur__mamund | 15.1 | 3.10 | 248 | 358190 | 14956 | 5 | 24 | 85 | 0 | 3 | 0 |
| bajaur__nawagai | 17.8 | 2.20 | 63 | 93850 | 2605 | 1 | 10 | 33 | 0 | 3 | 0 |
| bajaur__salarzai | 15.9 | 3.90 | 674 | 316767 | 15799 | 14 | 27 | 76 | 0 | 3 | 0 |
| bajaur__utman_khel | 19.0 | 4.10 | 5952 | 123719 | 9169 | 18 | 5 | 69 | 0 | 3 | 0 |
| battagram__allai | 29.1 | 1.60 | 22685 | 218149 | 4358 | 52 | 50 | 413 | 75 | 3 | 0 |
| battagram__batagram | 23.9 | 2.40 | 23314 | 335984 | 12090 | 27 | 58 | 352 | 16 | 3 | 1 |
| buner__daggar | 20.4 | 6.20 | 475 | 192776 | 19459 | 34 | 51 | 155 | 26 | 3 | 1 |
| buner__gagra | 20.9 | 5.30 | 1059 | 179087 | 15740 | 26 | 35 | 209 | 9 | 3 | 0 |
| buner__khado_khel | 13.5 | 3.30 | 222 | 136560 | 10117 | 4 | 16 | 46 | 0 | 3 | 0 |
| buner__mandanr | 18.0 | 4.90 | 1091 | 185031 | 15842 | 31 | 37 | 126 | 1 | 3 | 0 |
| lower_dir__adenzai | 15.1 | 7.70 | 6139 | 378915 | 61745 | 11 | 31 | 139 | 3 | 3 | 0 |
| lower_dir__balambat | 18.4 | 2.20 | 4181 | 216507 | 9158 | 6 | 21 | 188 | 36 | 3 | 0 |
| lower_dir__lalqila | 19.3 | 1.90 | 208 | 247381 | 8825 | 4 | 29 | 192 | 1 | 3 | 0 |
| lower_dir__munda | 12.9 | 5.00 | 5665 | 105400 | 9528 | 14 | 5 | 42 | 0 | 3 | 0 |
| lower_dir__samarbagh | 17.9 | 2.50 | 273 | 427714 | 25164 | 7 | 18 | 159 | 1 | 3 | 0 |
| lower_dir__timergara | 18.6 | 4.20 | 12142 | 596173 | 69487 | 5 | 15 | 102 | 4 | 3 | 1 |
| malakand__bat_khela | 18.4 | 4.20 | 12386 | 472959 | 44481 | 8 | 38 | 142 | 13 | 3 | 1 |
| malakand__dargai | 5.04 | 6.10 | 215 | 353291 | 29404 | 7 | 23 | 93 | 9 | 3 | 0 |
| mansehra__baffa_pakhal | 21.0 | 3.00 | 2293 | 460090 | 29124 | 56 | 20 | 238 | 24 | 3 | 0 |
| mansehra__bala_kot | 28.6 | 2.30 | 2470 | 310339 | 14293 | 96 | 128 | 617 | 7 | 3 | 0 |
| mansehra__darband | 19.5 | 11.0 | 26345 | 51702 | 3862 | 18 | 6 | 122 | 0 | 3 | 0 |
| mansehra__mansehra | 13.2 | 3.40 | 1341 | 723325 | 34689 | 52 | 89 | 596 | 25 | 3 | 1 |
| mansehra__oghi | 18.9 | 2.30 | 342 | 251721 | 10514 | 20 | 37 | 312 | 6 | 3 | 0 |
| shangla__alpuri | 29.3 | 1.50 | 603 | 366772 | 8069 | 31 | 27 | 267 | 1 | 3 | 1 |
| shangla__bisham | 29.9 | 2.90 | 23338 | 121279 | 6743 | 20 | 10 | 142 | 3 | 3 | 0 |
| shangla__chakisar | 27.6 | 2.00 | 23523 | 128238 | 3532 | 0 | 5 | 88 | 0 | 3 | 0 |
| shangla__makhuzai | 27.1 | 2.00 | 58 | 38969 | 1036 | 1 | 10 | 36 | 0 | 3 | 0 |
| shangla__martoong | 25.4 | 5.30 | 24167 | 103205 | 5595 | 7 | 8 | 93 | 0 | 3 | 0 |
| shangla__puran | 23.5 | 2.10 | 226 | 171758 | 4826 | 8 | 3 | 86 | 0 | 3 | 0 |
| swat__babuzai | 22.1 | 4.30 | 4851 | 696697 | 80888 | 34 | 25 | 135 | 45 | 3 | 1 |
| swat__bahrain | 30.3 | 1.80 | 3238 | 270623 | 8352 | 107 | 77 | 283 | 6 | 3 | 1 |
| swat__barikot | 18.4 | 6.60 | 5431 | 220148 | 31759 | 4 | 19 | 40 | 0 | 3 | 1 |
| swat__charbagh | 19.9 | 3.10 | 4184 | 159358 | 9259 | 5 | 12 | 82 | 1 | 3 | 1 |
| swat__kabal | 14.7 | 5.00 | 5069 | 480827 | 49952 | 8 | 32 | 145 | 10 | 3 | 2 |
| swat__kalam | 30.2 | 2.00 | 2046 | 141413 | 4144 | 100 | 33 | 40 | 1 | 3 | 0 |
| swat__khwaza_khela | 21.2 | 2.40 | 3704 | 307300 | 16544 | 23 | 25 | 171 | 0 | 3 | 1 |
| swat__matta_kharirai | 19.3 | 2.90 | 3715 | 552431 | 32099 | 30 | 10 | 131 | 3 | 3 | 1 |
| swat__matta_sebujni | 23.3 | 2.50 | 4208 | 230215 | 13494 | 28 | 29 | 146 | 3 | 3 | 0 |
| upper_dir__barawal | 24.6 | 1.70 | 466 | 125309 | 3700 | 23 | 21 | 76 | 0 | 3 | 0 |
| upper_dir__dir | 25.3 | 1.80 | 2717 | 384667 | 10908 | 22 | 26 | 94 | 5 | 3 | 1 |
| upper_dir__kalkot | 29.4 | 1.90 | 1768 | 157374 | 4456 | 52 | 32 | 104 | 1 | 3 | 0 |
| upper_dir__khall | 21.1 | 2.20 | 3753 | 143530 | 8306 | 7 | 11 | 94 | 1 | 3 | 0 |
| upper_dir__larjam | 26.6 | 1.80 | 3117 | 119396 | 2939 | 7 | 15 | 64 | 0 | 3 | 0 |
| upper_dir__shrengal | 29.6 | 1.50 | 1867 | 210356 | 3434 | 27 | 40 | 93 | 0 | 3 | 0 |
| upper_dir__wari | 22.4 | 1.60 | 3505 | 369147 | 8916 | 12 | 23 | 208 | 0 | 3 | 0 |

## Limits

- 90 m DEM: narrow valleys and small khwars are blurred; heights near cliffs are noisy.
- UNOSAT 2022 / Aug 2025 flood extents were not used (download size and time).
  The PDMA village check above is the validation instead.
- Largest catchment is cut at the DEM edge (71–75° E, 34–36° N), so the Indus and
  Kabul rivers show only the part inside the box.
- Upper Chitral (Mulkhow) is outside the DEM box and has no terrain features; it is
  out of scope.
