# M1 report: PDMA flood event dataset

Built 2026-11-19 from 4922 cached reports (last report date 2026-04-19).
All figures are counts; the event file itself is private (`data/events/`, gitignored).

## Gate G1

| Check | Value | Threshold | Pass |
|---|---|---|---|
| Unique positive district-days, candidate districts | 132 | >= 100 | yes |
| Positive events at tehsil level or better, candidate districts | 69% | >= 60% | yes |

All KP: 382 positive events on 368 district-days.

## Events by type (all KP, after de-duplication)

| Type | Events |
|---|---|
| roof_collapse | 1275 |
| flash_flood | 251 |
| landslide | 220 |
| drowning | 70 |
| flood | 59 |
| other | 32 |
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
| 2025 | 94 |
| 2026 | 7 |

## Positive events by district (all KP)

| District | Events |
|---|---|
| Upper Chitral | 32 |
| Swat | 30 |
| Lower Chitral | 26 |
| Upper Dir | 24 |
| Dera Ismail Khan | 21 |
| Bajaur | 20 |
| Buner | 18 |
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
| North Waziristan | 5 |
| Haripur | 5 |
| Bannu | 4 |
| Lower Kohistan | 4 |
| Mardan | 4 |
| Peshawar | 4 |
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
| tehsil | 24 |
| village | 75 |

## Positive events per tehsil (candidate districts, top 25)

| Tehsil | Events |
|---|---|
| bajaur__mamund | 7 |
| swat__babuzai | 6 |
| mansehra__bala_kot | 5 |
| buner__daggar | 5 |
| malakand__bat_khela | 4 |
| swat__khwaza_khela | 4 |
| bajaur__salarzai | 4 |
| bajaur__utman_khel | 4 |
| upper_dir__wari | 3 |
| swat__barikot | 3 |
| upper_dir__larjam | 3 |
| buner__khado_khel | 3 |
| swat__bahrain | 3 |
| swat__kabal | 3 |
| buner__gagra | 3 |
| battagram__batagram | 2 |
| upper_dir__dir | 2 |
| upper_dir__barawal | 2 |
| upper_dir__kalkot | 2 |
| shangla__bisham | 2 |
| lower_dir__samarbagh | 2 |
| malakand__dargai | 2 |
| lower_dir__munda | 2 |
| lower_dir__lalqila | 2 |
| upper_dir__shrengal | 2 |

## Extraction notes

| Item | Count |
|---|---|
| LLM records (report x district) | 739 |
| LLM records with no incident | 8 |
| Incident dates taken from text | 1047 |
| Incident dates out of range, report date used | 30 |
| Landslide rows from tables | 222 |
| Collapse rows from tables | 1620 |
| Drafts before de-duplication | 2919 |
| Events after de-duplication | 1909 |

Name safety: villages are stored only as gazetteer names; water-body strings with name markers are dropped; no free text is stored.

<!-- manual sections below: kept on rebuild -->

## Spot check (50 random positive events)

Second reader: each event was compared with the original report text (names
removed) by a reviewer separate from the extraction model. Rows needing a
human look are marked in `data/events/spot_check_reviewed.csv` (private).

| Check | Result |
|---|---|
| Event date correct | 49 / 50 (98%) |
| District correct | 49 / 50 (98%) |
| Tehsil, where one was assigned (23 events) | 18 correct, 1 wrong, 3 unverified, 1 victim's residence only |
| Tehsil named in report but not assigned | 4 (mostly Chitral villages missing from the gazetteer) |
| Event type wrong for a positive | 1 (river rise from glacier melt; report says no flooding) |

The one date and district error is the same event: a drowning in Bajaur
reported by Charsadda, where the body was found. Target (90% date and
district) is met.

**Follow-up (19 Nov 2026).** A team member checked the flagged rows against
the reports. The 3 unverified tehsils were looked up online:

| Village in report | Tehsil assigned | Finding |
|---|---|---|
| Tarpatar (Upper Dir) | Larjam | The report names only the village; the tehsil comes from the village location. Tarpatar (Taraptar) is a union council in the Usheri valley, which lies in Larjam tehsil. Kept. |
| Gandigar (Upper Dir) | Dir | The 2017 census lists Gandigar Bala, Gandigar Payeen and Kila Gandigar under Dir tehsil. Kept. |
| Zaith / Zait (Upper Chitral) | Mulkhow | News reports place Zait among the Reshun–Kuragh–Charun villages near the Mulkhow/Mastuj line. Still unverified; Upper Chitral is outside the candidate area. |

Three corrections were applied through `data/events/event_corrections.csv`
(private; applied on every rebuild): the Lower Chitral event moved from
Chitral to Drosh tehsil; the glacier-melt river rise is no longer a positive;
the Charsadda drowning moved to Utman Khel, Bajaur, dated 27 Jun 2025.

## Name redaction (privacy)

The first extraction runs used a redaction filter that only caught names
written with "s/o", "d/o", "w/o" or an honorific. The spot check showed that
names written other ways (numbered lists of house owners, "<name> resident
of", "<name> (Age 13)") were not removed, so some names were included in
text sent to the LLM providers (Groq, Gemini) for those runs. The stored
dataset was never affected: it holds no free text, villages come only from
the gazetteer, and the output name scan is zero.

The filter now also removes names before "resident of", before ages, before
"was flooded/drowned", after family words ("sons of", "widow of"), after
"owned by", in numbered lists (an item is kept only if it is a known place),
and groups containing common given names unless they read as a place (Khel,
Abad, Kili, Kalay, Kot, Colony...). On all 739 flood texts, possible leftover
names dropped from 98 texts to about 5 (an estimate from a given-name word
scan plus reading samples); 85% of the text is kept. Rows already extracted
were not re-sent.

## Checks and known limits

- **Demo events present:** 15 Aug 2025 (Buner cloudburst at Daggar with
  "Pir Baba Khwar", Gagra; same day Bajaur Salarzai, five Swat tehsils,
  Mansehra); 27 Jun 2025 (Swat, Babuzai, River Swat, merged from 3 reports);
  24–28 Aug 2022 (Swat: Babuzai, Charbagh, Khwaza Khela).
- **Name scan:** zero name markers in the output.
- **Infrastructure-only floods are under-counted.** PDMA tables record human
  losses and houses; floods that mostly damaged hotels, roads and bridges
  (for example upper Swat, Bahrain and Kalam, Aug 2022) may be missing.
- **Per-event deaths are unreliable** when one report row covers several
  incidents. Do not quote event-level deaths. Deaths are not used for training.
- **Tehsil-level positives are few** (max 7 in one tehsil). The model (M5)
  must pool tehsils and can use district-level events as weaker labels.
- **All 739 flood-like report rows are extracted** (Jul 2019 – Apr 2026).
