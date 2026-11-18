# M1 report: PDMA flood event dataset

Built 2026-11-18 from 3216 cached reports (last report date 2023-12-14).
All figures are counts; the event file itself is private (`data/events/`, gitignored).

## Gate G1

| Check | Value | Threshold | Pass |
|---|---|---|---|
| Unique positive district-days, candidate districts | 10 | >= 100 | no |
| Positive events at tehsil level or better, candidate districts | 60% | >= 60% | yes |

All KP: 24 positive events on 24 district-days.

## Events by type (all KP, after de-duplication)

| Type | Events |
|---|---|
| roof_collapse | 640 |
| landslide | 130 |
| flash_flood | 16 |
| drowning | 7 |
| flood | 1 |
| other | 1 |

Positives = flash_flood, flood, cloudburst, drowning. Landslides and roof collapses are stored but are not positives.

## Positive events by year (all KP)

| Year | Events |
|---|---|
| 2019 | 24 |

## Positive events by district (all KP)

| District | Events |
|---|---|
| Bajaur | 3 |
| Buner | 3 |
| South Waziristan Lower | 3 |
| Lower Chitral | 2 |
| Upper Chitral | 2 |
| Battagram | 1 |
| Bannu | 1 |
| Abbottabad | 1 |
| Karak | 1 |
| Haripur | 1 |
| Dera Ismail Khan | 1 |
| Khyber | 1 |
| Lower Dir | 1 |
| Lakki Marwat | 1 |
| Malakand | 1 |
| Upper Dir | 1 |

## Geocode level, positive events in candidate districts

| Level | Events |
|---|---|
| district | 4 |
| tehsil | 3 |
| village | 3 |

## Positive events per tehsil (candidate districts, top 25)

| Tehsil | Events |
|---|---|
| bajaur__utman_khel | 2 |
| bajaur__mamund | 1 |
| buner__daggar | 1 |
| lower_dir__lalqila | 1 |
| malakand__bat_khela | 1 |

## Extraction notes

| Item | Count |
|---|---|
| LLM records (report x district) | 29 |
| LLM records with no incident | 0 |
| Incident dates taken from text | 29 |
| Incident dates out of range, report date used | 1 |
| Landslide rows from tables | 145 |
| Collapse rows from tables | 892 |
| Drafts before de-duplication | 1067 |
| Events after de-duplication | 795 |

Name safety: villages are stored only as gazetteer names; water-body strings with name markers are dropped; no free text is stored.
