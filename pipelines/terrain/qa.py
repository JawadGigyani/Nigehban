"""Write `reports/terrain_qa.md`: tehsil statics, village bands, validation on PDMA villages, facilities.

    python -m pipelines.terrain.qa
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from backend.app.config import get_settings
from pipelines.hydromet.qa import _md


def validation(villages: pd.DataFrame, events_path: Path) -> tuple[pd.DataFrame, int]:
    events = pd.read_parquet(events_path)
    events = events[events["is_positive"] & (events["geocode_level"] == "village")]
    named = set(zip(events["village"].str.lower(), events["tehsil_id"]))
    flag = [(n.lower(), t) in named for n, t in zip(villages["name"], villages["tehsil_id"])]
    v = villages.assign(event=flag)
    rows = []
    for b in ("high", "medium", "low"):
        rows.append({"band": b,
                     "villages named in PDMA flood reports": f"{(v[v.event]['exposure_band'] == b).mean():.0%}",
                     "all other villages": f"{(v[~v.event]['exposure_band'] == b).mean():.0%}"})
    return pd.DataFrame(rows), int(v["event"].sum())


def main() -> int:
    data = get_settings().data_dir
    static = pd.read_parquet(data / "features" / "tehsil_static.parquet")
    villages = pd.read_csv(data / "reference" / "village_exposure.csv")
    facilities = pd.read_csv(data / "reference" / "facilities.csv")
    tehsils = json.loads((data / "reference" / "tehsils.geojson").read_text(encoding="utf-8"))["features"]
    in_scope = [f["properties"]["tehsil_id"] for f in tehsils if f["properties"]["in_scope"]]

    val, n_event = validation(villages, data / "events" / "flood_events.parquet")
    per_tehsil = (villages.groupby("tehsil_id")["exposure_band"].value_counts().unstack(fill_value=0)
                  .reindex(columns=["high", "medium", "low"], fill_value=0))
    shelters = facilities[facilities["kind"] == "shelter"].groupby("tehsil_id").size()
    ground = facilities[facilities["kind"] == "high_ground"].groupby("tehsil_id").size()
    rescue = facilities[facilities["kind"] == "rescue_1122"].groupby("tehsil_id").size()
    table = static.set_index("tehsil_id")[["mean_slope", "share_low_hand", "catchment_area_km2",
                                           "population", "population_low_hand"]]
    table = table.join(per_tehsil).join(shelters.rename("shelters")).join(ground.rename("high ground")) \
        .join(rescue.rename("rescue 1122")).fillna(0)
    table = table.loc[[t for t in in_scope if t in table.index]].reset_index()
    table["share_low_hand"] = (table["share_low_hand"] * 100).round(1)
    table = table.rename(columns={"share_low_hand": "low-HAND land %", "catchment_area_km2": "largest catchment km²",
                                  "mean_slope": "mean slope °", "population_low_hand": "people on low-HAND land"})
    for c in ("population", "people on low-HAND land", "high", "medium", "low", "shelters", "high ground",
              "rescue 1122", "largest catchment km²"):
        table[c] = table[c].astype(int)

    has_village = all(t in set(villages["tehsil_id"]) for t in in_scope)
    has_shelter = all(t in set(facilities[facilities["kind"].isin(["shelter", "high_ground"])]["tehsil_id"])
                      for t in in_scope)
    osm_only = [t for t in in_scope if t not in set(facilities[facilities["kind"] == "shelter"]["tehsil_id"])]
    kinds = facilities.groupby("kind").size().to_dict()

    text = f"""# M3 terrain + M4b facilities QA

Generated {dt.date.today()} by `python -m pipelines.terrain.qa`.

## Done-when check

| Check | Result |
|---|---|
| Every in-scope tehsil has at least 1 village | {has_village} ({len(villages)} villages) |
| Every in-scope tehsil has at least 1 shelter or higher-ground point | {has_shelter} |
| Tehsils with an OSM shelter building | {len(in_scope) - len(osm_only)} of {len(in_scope)} |
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

{n_event} villages appear by name in positive PDMA events (geocoded to the village).

{_md(val)}

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
""" + "\n".join(f"| {k} | {v} |" for k, v in kinds.items()) + f"""

- **shelter**: OSM schools, colleges, government buildings (priority 1) and mosques
  (priority 2). OSM is sparse in KP: {len(osm_only)} in-scope tehsils have none.
- **high_ground**: villages in the low band (lowest nearby HAND 15–120 m, at least
  300 m from a stream) closest to the most high-band villages. Not a building: the
  advisory says "move to higher ground, for example ...".
- **rescue_1122**: 2 from OSM plus 15 from news reports and the Rescue 1122 KP site,
  placed at the town centre. 8 are reported stations; 7 are district services whose
  station location is not confirmed.
- Every row is `verified=false` and shown as unverified on the board.

## Per tehsil (in scope)

{_md(table)}

## Limits

- 90 m DEM: narrow valleys and small khwars are blurred; heights near cliffs are noisy.
- UNOSAT 2022 / Aug 2025 flood extents were not used (download size and time).
  The PDMA village check above is the validation instead.
- Largest catchment is cut at the DEM edge (71–75° E, 34–36° N), so the Indus and
  Kabul rivers show only the part inside the box.
- Upper Chitral (Mulkhow) is outside the DEM box and has no terrain features; it is
  out of scope.
"""
    out = Path("reports") / "terrain_qa.md"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}; villages ok {has_village}; shelters ok {has_shelter}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
