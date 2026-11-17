"""Build the district and tehsil alias tables used to read PDMA place names.

Writes:
- `data/reference/district_aliases.csv` (alias, district_slug, source): every KP
  district in its PDMA spelling, its COD-AB spelling and known variants.
- `data/reference/tehsil_aliases.csv` (level, alias, district_slug, tehsil_id,
  source, note): COD-AB tehsil names, plus 2023 census tehsil and sub-division
  names mapped to the COD-AB tehsil they fall in.

Census units do not always match COD-AB polygons (Buner has 6 census tehsils
and 4 COD-AB tehsils; Upper Dir has 4 census sub-divisions and 7 COD-AB
tehsils). A census name is mapped by, in order:
  1. the same name key as a COD-AB tehsil in that district ("census_same"),
  2. a near-identical spelling ("census_fuzzy", ratio >= 80; each district has
     under 10 tehsils, and every fuzzy match is listed in the report),
  3. its headquarters place: the gazetteer place with that name in the
     district, located in a COD-AB polygon ("census_hq_point"),
  4. otherwise left unresolved (listed in the report for manual review).

`data/reference/manual_aliases.csv` is maintained by hand and read alongside.

Usage: python -m pipelines.reference.build_aliases
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz

from backend.app.config import get_settings
from backend.app.geo import TehsilLocator, name_key
from pipelines.reference.admin_names import EXTRA_DISTRICT_ALIASES, district_slug

FUZZY_SAME = 80
FEATURE_RANK = {"city": 0, "town": 1, "pplc": 0, "ppla": 0, "ppla2": 0, "ppla3": 1, "ppl": 3,
                "suburb": 2, "village": 3, "pplx": 4, "hamlet": 5}

TEHSIL_FIELDS = ["level", "alias", "district_slug", "tehsil_id", "source", "note"]


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_district_aliases(kp_admin: list[dict]) -> list[dict]:
    rows: dict[tuple[str, str], dict] = {}

    def add(alias: str, slug: str, source: str) -> None:
        rows.setdefault((name_key(alias), slug), {"alias": alias, "district_slug": slug, "source": source})

    for r in kp_admin:
        add(r["district"], r["district_slug"], "pdma")
        add(r["district_cod"], r["district_slug"], "cod")
    for canonical, extras in EXTRA_DISTRICT_ALIASES.items():
        for extra in extras:
            add(extra, district_slug(canonical), "variant")
    return sorted(rows.values(), key=lambda r: (r["district_slug"], r["alias"]))


def _hq_point(name: str, district: str, places: list[dict], locator: TehsilLocator):
    key = name_key(name)
    hits = [p for p in places if p["district_slug"] == district and (
        name_key(p["name"]) == key or any(name_key(a) == key for a in p["alt_names"].split("|") if a)
    )]
    if not hits:
        return None
    hits.sort(key=lambda p: (FEATURE_RANK.get(p["feature"], 6), -(int(p["population"] or 0))))
    best = hits[0]
    region = locator.locate(float(best["lat"]), float(best["lon"]))
    if region is None:
        return None
    return region.tehsil_id, f"HQ '{best['name']}' ({best['feature']}) at {best['lat']},{best['lon']}"


def build_tehsil_aliases(
    regions, census: list[dict], places: list[dict], locator: TehsilLocator,
    district_lookup: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    by_district: dict[str, list] = defaultdict(list)
    for region in regions:
        district = region.tehsil_id.split("__")[0]
        by_district[district].append(region)
        rows.append({"level": "tehsil", "alias": region.tehsil, "district_slug": district,
                     "tehsil_id": region.tehsil_id, "source": "cod", "note": region.pcode or ""})

    unresolved: list[dict] = []
    for unit in census:
        district = district_lookup.get(name_key(unit["district"]))
        if district not in by_district:
            continue  # outside the region
        name, key = unit["tehsil"], name_key(unit["tehsil"])
        cod = by_district[district]
        same = [r for r in cod if name_key(r.tehsil) == key]
        if same:
            match, source, note = same[0].tehsil_id, "census_same", ""
        else:
            scored = sorted(((fuzz.ratio(name_key(r.tehsil), key), r) for r in cod),
                            key=lambda t: -t[0])
            if scored and scored[0][0] >= FUZZY_SAME:
                match, source = scored[0][1].tehsil_id, "census_fuzzy"
                note = f"matches '{scored[0][1].tehsil}' ({scored[0][0]:.0f})"
            else:
                hq = _hq_point(name, district, places, locator)
                if hq is None:
                    unresolved.append({"district_slug": district, "census_name": name,
                                       "unit_type": unit["unit_type"]})
                    continue
                match, note = hq
                source = "census_hq_point"
        rows.append({"level": "tehsil", "alias": name, "district_slug": district,
                     "tehsil_id": match, "source": source,
                     "note": f"census 2023 {unit['unit_type']}; {note}".strip("; ")})
    return rows, unresolved


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    ref = settings.data_dir / "reference"
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref-dir", type=Path, default=ref)
    args = parser.parse_args(argv)
    ref = args.ref_dir

    kp_admin = _read_csv(ref / "kp_admin.csv")
    districts = build_district_aliases(kp_admin)
    with (ref / "district_aliases.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["alias", "district_slug", "source"])
        writer.writeheader()
        writer.writerows(districts)

    locator = TehsilLocator.from_geojson(ref / "tehsils.geojson")
    district_lookup = {name_key(d["alias"]): d["district_slug"] for d in districts}
    rows, unresolved = build_tehsil_aliases(
        locator.regions, _read_csv(ref / "census2023_kp_tehsils.csv"),
        _read_csv(ref / "gazetteer.csv"), locator, district_lookup,
    )
    with (ref / "tehsil_aliases.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TEHSIL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    manual_path = ref / "manual_aliases.csv"
    manual = {(r["district_slug"], name_key(r["alias"])) for r in _read_csv(manual_path)} if manual_path.exists() else set()
    still_open = [u for u in unresolved if (u["district_slug"], name_key(u["census_name"])) not in manual]
    (ref / "_alias_unresolved.json").write_text(json.dumps(still_open, indent=2), encoding="utf-8")
    print(f"{len(districts)} district aliases, {len(rows)} tehsil aliases")
    print(f"Unresolved census names (not in manual_aliases.csv): {still_open or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
