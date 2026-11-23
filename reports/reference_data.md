# M4a report: admin boundaries, gazetteer and aliases

Built on 18 Nov 2026. All numbers below come from the committed files in
`data/reference/`.

## Boundary source

| Source | Year | Units in KP | District column | Licence | Used |
|---|---|---|---|---|---|
| OCHA COD-AB Pakistan adm3 | valid 2022-09-09 (dataset updated Aug 2026) | 153 tehsils, 35 districts | yes, with P-codes | CC BY-IGO | **Yes** |
| geoBoundaries PAK ADM3 | 2017 census | (554 national) | no | ODbL | No |
| PBS Census 2023 Table 1 | 2023 | 148 tehsils and sub-divisions | yes | PBS public | Names and population only (no polygons published) |

COD-AB was chosen because it is newer than geoBoundaries, has district names
and P-codes, and already has the Chitral Upper/Lower and Kohistan splits.

## Coverage

| District | In scope | COD-AB tehsils | Census 2023 units | Pop. 2023 | Gazetteer places | With Urdu name |
|---|---|---|---|---|---|---|
| bajaur | yes | 7 | 7 | 1,287,960 | 666 | 21 |
| battagram | yes | 2 | 2 | 554,133 | 952 | 10 |
| buner | yes | 4 | 6 | 1,016,869 | 770 | 82 |
| lower_dir | yes | 6 | 4 | 1,650,183 | 990 | 73 |
| malakand | yes | 2 | 2 | 826,250 | 311 | 34 |
| mansehra | yes | 5 | 5 | 1,797,177 | 2,410 | 88 |
| shangla | yes | 6 | 5 | 891,252 | 842 | 78 |
| swat | yes | 9 | 7 | 2,687,384 | 1,788 | 170 |
| upper_dir | yes | 7 | 4 | 1,083,566 | 1,053 | 28 |
| lower_chitral | no | 3 | 2 | 320,407 | 1,015 | 33 |
| upper_chitral | no | 2 | 1 | 195,528 | 669 | 10 |
| **Total** | | **53 (48 in scope)** | | | **11,466** | |

- Every tehsil has a polygon and at least 3 gazetteer places.
- Gazetteer sources: GeoNames only 9,443; OSM only 1,170; both 853.
- In-scope bounds: 71.173–74.127 E, 34.150–35.899 N. `CANDIDATE_BBOX` was
  widened to 74.18 E because Mansehra reaches 74.13 E (planned edge was 73.8).

## Aliases

- 52 district aliases cover all 35 KP districts. All 35 district spellings
  seen in a sample of 400 PDMA reports resolve.
- 93 tehsil aliases: 53 COD-AB names, 31 census names with the same spelling,
  7 census names matched by close spelling, 2 by headquarters place, plus 5
  hand-written rows with area evidence (`manual_aliases.csv`).

Close-spelling matches (all checked by eye):

| Census name | COD-AB tehsil | Score |
|---|---|---|
| Bar Chamer Kand | Bar Chamarkand | 92 |
| Temergara | Timergara | 89 |
| Behrain | Bahrain (+ Kalam, manual) | 86 |
| Khawazakhela | Khwaza Khela | 96 |
| Martung | Martoong | 80 |
| Larjum | Larjam | 83 |
| Sharingal | Shrengal | 82 |

**Open:** Buner census tehsils **Chagharzai** and **Gadezai** are not mapped.
Neither name appears in OSM or GeoNames. By area, census Daggar + Gagra +
Chagharzai + Gadezai (1,197 km²) roughly equals COD-AB Daggar + Gagra
(1,133 km²), but either pairing is possible. PDMA reports usually name
villages too, which geocode through the gazetteer, so this does not block M1.

## Checks run

- `tests/test_reference_data.py`: unique tehsil ids, every district covered,
  contract validation of every feature, 10 known towns located in the right
  tehsil (Peshawar correctly outside), gazetteer consistency, every PDMA
  district spelling resolves, every alias points to a real tehsil.
