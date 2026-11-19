# Reference data

Small reference layers committed to the repo. Rebuild them with the commands
below (raw downloads go to the gitignored `data/raw/`).

| File | What it is | Built by | Source and licence |
|---|---|---|---|
| `tehsils.geojson` | Tehsil polygons for the 9 candidate districts (`in_scope: true`) and Upper/Lower Chitral (`in_scope: false`, kept for geocoding). Properties follow the `TehsilRegion` contract. | `pipelines.reference.build_tehsils` | OCHA COD-AB Pakistan adm3, valid on 2022-09-09 ([HDX](https://data.humdata.org/dataset/cod-ab-pak)), CC BY-IGO |
| `kp_admin.csv` | Every KP district and tehsil name with P-codes (153 tehsils) | `build_tehsils` | same |
| `census2023_kp_tehsils.csv` | 2023 census tehsils and sub-divisions for KP: area, population 2023 and 2017, urban share | `pipelines.reference.census2023` | PBS Census 2023, Table 1 ([xlsx](https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_kp_districts.xlsx)) |
| `gazetteer.csv` | 11,466 named places in the region, each assigned to a tehsil | `pipelines.reference.build_gazetteer` | OpenStreetMap via Overpass (ODbL); GeoNames PK dump (CC BY 4.0) |
| `district_aliases.csv` | District spellings (PDMA, COD-AB, variants) -> `district_slug` | `pipelines.reference.build_aliases` | derived |
| `tehsil_aliases.csv` | Tehsil spellings (COD-AB, census 2023) -> `tehsil_id`, with the method used | `build_aliases` | derived |
| `manual_aliases.csv` | Hand-maintained tehsil aliases, each with the evidence in `note` | edited by hand | derived |
| `_alias_unresolved.json` | Census names that could not be mapped and are not in the manual file | `build_aliases` | derived |

Rebuild in order:

```powershell
.venv\Scripts\python -m pipelines.reference.census2023
.venv\Scripts\python -m pipelines.reference.build_tehsils
.venv\Scripts\python -m pipelines.reference.build_gazetteer      # add --fetch-osm to refresh OSM
.venv\Scripts\python -m pipelines.reference.build_aliases
```

## Known mismatches

- **COD-AB is from 2022; the 2023 census uses different units in places.** The
  risk unit is the COD-AB tehsil polygon (the newest open polygons). Census
  names are aliases that point to COD-AB tehsils.
  - Buner: census has 6 tehsils (adds Chagharzai and Gadezai); COD-AB has 4.
    **Chagharzai and Gadezai are not mapped yet**: neither name is in OSM or
    GeoNames, and the areas fit more than one split.
  - Swat: census "Matta" = Matta Kharirai + Matta Sebujni; census "Behrain"
    covers Bahrain + Kalam. Both names map to both tehsils.
  - Lower Dir (4 census sub-divisions vs 6 COD-AB tehsils), Upper Dir (4 vs 7),
    Shangla (5 vs 6), Chitral (3 vs 5): census names map to the COD-AB tehsil
    with the same or nearest spelling; the remaining COD-AB tehsils have no
    census name.
  - Malakand: census "Swat Rani Zai" = Bat Khela, "Sam Rani Zai" = Dargai
    (matched by area; see `manual_aliases.csv`).
  - Battagram: census "Ai" is Allai.
- **District spellings differ between sources** (Batagram/Battagram, Chitral
  Upper/Upper Chitral, D. I. Khan/Dera Ismail Khan, Tor Ghar/Torghar).
  `district_aliases.csv` covers them; the canonical spelling is PDMA's.
- **South Waziristan** is one district in COD-AB but Upper and Lower in PDMA
  reports; both PDMA names map to `south_waziristan`.
- **Gazetteer** places come mostly from GeoNames (9,443 of 11,466). Positions
  are approximate and some names are duplicated under different spellings
  more than 1 km apart.

## tehsil_grid.csv (M2)

Weather grid cells for each tehsil: the 0.25° ERA5 / ECMWF cells that overlap
the tehsil polygon, with `weight` = the cell's share of the tehsil's area
(weights sum to 1 per tehsil; slivers under 2% are dropped). 197 rows, 80
unique cells, 53 tehsils. Built from `tehsils.geojson` by
`backend/app/hydromet/grid.py`.

## village_exposure.csv (M3)

One row per populated gazetteer place in the DEM box (10,525). `hand_m` is the
height above the nearest stream (draining at least 10 km²) at the point;
`hand_min_m` is the lowest value within about 180 m, which sets
`exposure_band` (high: under 5 m next to a river draining at least 50 km²;
medium: under 8 m; low: otherwise). Copernicus GLO-90 DEM. Bands only, never
flood depths. See reports/m3_terrain_qa.md for the validation.

## facilities.csv (M4b)

Shelter candidates (OSM schools, colleges, government buildings; mosques as
priority 2), suggested higher ground (derived from the DEM, not buildings),
health facilities, police, fire and Rescue 1122. All `verified=false`.
OSM data © OpenStreetMap contributors (ODbL).

## rescue1122_manual.csv (M4b)

Rescue 1122 stations named in news reports or on the Rescue 1122 KP site,
placed at the town centre by `build_facilities`. Status says whether a station
was reported or only the district service is known.
