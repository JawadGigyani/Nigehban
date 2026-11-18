# M1 report: PDMA flood event dataset

Built 2026-11-18 from 4922 cached reports (last report date 2026-04-19).
All figures are counts; the event file itself is private (`data/events/`, gitignored).

## Gate G1

| Check | Value | Threshold | Pass |
|---|---|---|---|
| Unique positive district-days, candidate districts | 129 | >= 100 | yes |
| Positive events at tehsil level or better, candidate districts | 68% | >= 60% | yes |

All KP: 376 positive events on 362 district-days.

## Events by type (all KP, after de-duplication)

| Type | Events |
|---|---|
| roof_collapse | 1268 |
| flash_flood | 249 |
| landslide | 219 |
| drowning | 68 |
| flood | 57 |
| other | 30 |
| cloudburst | 2 |

Positives = flash_flood, flood, cloudburst, drowning. Landslides and roof collapses are stored but are not positives.

## Positive events by year (all KP)

| Year | Events |
|---|---|
| 2019 | 34 |
| 2020 | 30 |
| 2021 | 31 |
| 2022 | 94 |
| 2023 | 37 |
| 2024 | 55 |
| 2025 | 93 |
| 2026 | 2 |

## Positive events by district (all KP)

| District | Events |
|---|---|
| Upper Chitral | 32 |
| Swat | 30 |
| Lower Chitral | 27 |
| Upper Dir | 23 |
| Dera Ismail Khan | 20 |
| Bajaur | 19 |
| Buner | 17 |
| Upper Kohistan | 16 |
| South Waziristan Lower | 15 |
| Mansehra | 15 |
| Abbottabad | 12 |
| Lower Dir | 12 |
| Tank | 12 |
| Swabi | 11 |
| Khyber | 11 |
| Mohmand | 10 |
| Shangla | 10 |
| Malakand | 9 |
| Lakki Marwat | 8 |
| Karak | 7 |
| Kurram | 6 |
| Battagram | 6 |
| Torghar | 6 |
| Nowshera | 6 |
| Haripur | 5 |
| Mardan | 4 |
| Lower Kohistan | 4 |
| North Waziristan | 4 |
| Bannu | 3 |
| Peshawar | 3 |
| Kohistan Kolai Pallas | 3 |
| Charsadda | 3 |
| Hangu | 2 |
| Kohat | 2 |
| Orakzai | 2 |
| South Waziristan Upper | 1 |

## Geocode level, positive events in candidate districts

| Level | Events |
|---|---|
| district | 45 |
| tehsil | 22 |
| village | 74 |

## Positive events per tehsil (candidate districts, top 25)

| Tehsil | Events |
|---|---|
| bajaur__mamund | 7 |
| swat__babuzai | 6 |
| mansehra__bala_kot | 5 |
| bajaur__salarzai | 4 |
| malakand__bat_khela | 4 |
| swat__khwaza_khela | 4 |
| buner__daggar | 4 |
| bajaur__utman_khel | 3 |
| swat__barikot | 3 |
| upper_dir__wari | 3 |
| buner__gagra | 3 |
| buner__khado_khel | 3 |
| swat__bahrain | 3 |
| swat__kabal | 3 |
| upper_dir__larjam | 2 |
| battagram__batagram | 2 |
| upper_dir__dir | 2 |
| upper_dir__kalkot | 2 |
| shangla__bisham | 2 |
| shangla__alpuri | 2 |
| lower_dir__samarbagh | 2 |
| malakand__dargai | 2 |
| lower_dir__munda | 2 |
| lower_dir__lalqila | 2 |
| upper_dir__shrengal | 2 |

## Extraction notes

| Item | Count |
|---|---|
| LLM records (report x district) | 720 |
| LLM records with no incident | 8 |
| Incident dates taken from text | 1019 |
| Incident dates out of range, report date used | 29 |
| Landslide rows from tables | 222 |
| Collapse rows from tables | 1620 |
| Drafts before de-duplication | 2890 |
| Events after de-duplication | 1893 |

Name safety: villages are stored only as gazetteer names; water-body strings with name markers are dropped; no free text is stored.

## Checks and known limits

- **Demo events present:** 15 Aug 2025 (Buner cloudburst at Daggar with
  "Pir Baba Khwar", Gagra; same day Bajaur Salarzai, five Swat tehsils,
  Mansehra); 27 Jun 2025 (Swat, Babuzai, River Swat, merged from 3 reports);
  24–28 Aug 2022 (Swat: Babuzai, Charbagh, Khwaza Khela).
- **Name scan:** zero name markers (s/o, d/o, w/o, Mr., Mst.) in the output.
- **Infrastructure-only floods are under-counted.** PDMA tables record human
  losses and houses; floods that mostly damaged hotels, roads and bridges
  (for example upper Swat, Bahrain and Kalam, Aug 2022) may be missing.
- **Per-event deaths are unreliable** when one report row covers several
  incidents (the LLM splits them and some counts are lost). Do not quote
  event-level deaths; use the summary table for district-day totals. Deaths
  are not used for training.
- **Tehsil-level positives are few:** 96 positive events at tehsil or village
  level across 48 in-scope tehsils over 7 seasons (max 7 in one tehsil). The
  model (M5) must pool tehsils and can use district-level events as weaker
  labels.
- **Pending:** 19 report rows not yet extracted (free LLM quotas ran out);
  2 are in the monsoon window (Upper Dir 16 Sep 2025, Buner 19 Sep 2025), the
  rest are Feb–Apr 2026. A rerun of `extract` fills them in.
- **Spot check:** `data/events/spot_check.csv` lists 50 random positive events
  with links to the PDMA reports, to be checked by a person (target: 90% or
  more with the correct date and district).
