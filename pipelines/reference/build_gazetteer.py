"""Build a place-name gazetteer for the region from OSM and GeoNames.

Sources:
- OpenStreetMap place nodes/ways via the Overpass API (ODbL), cached at
  `data/raw/osm/places_overpass.json` (fetched with `--fetch-osm`).
- GeoNames Pakistan dump PK.txt (CC BY 4.0), feature class P (populated places),
  from https://download.geonames.org/export/dump/PK.zip.

Each place is assigned to a tehsil by point-in-polygon against
`data/reference/tehsils.geojson`; places outside the region are dropped. Places
in the same tehsil are merged when they share a name key within 2 km, or
have a near-identical spelling within 1 km.

Writes `data/reference/gazetteer.csv`.

Usage: python -m pipelines.reference.build_gazetteer [--fetch-osm]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from rapidfuzz import fuzz

from backend.app.config import get_settings
from backend.app.geo import TehsilLocator, name_key

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
QUERY_BBOX = (34.0, 71.0, 37.0, 74.3)  # south, west, north, east; covers all kept tehsils
PLACE_TYPES = "city|town|village|hamlet|suburb|neighbourhood|quarter|locality|isolated_dwelling"
MERGE_KM = 2.0
FUZZY_MERGE_KM = 1.0
FUZZY_MERGE_RATIO = 88
_LATIN = re.compile(r"^[A-Za-z0-9 .,'()\-]+$")

GEONAMES_COLUMNS = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1", "admin2",
    "admin3", "admin4", "population", "elevation", "dem", "timezone", "modified",
]


@dataclass
class Place:
    place_id: str
    name: str
    lat: float
    lon: float
    feature: str
    source: str
    alt_names: set[str] = field(default_factory=set)
    name_ur: str | None = None
    population: int | None = None
    district_slug: str | None = None
    tehsil_id: str | None = None
    merged_ids: list[str] = field(default_factory=list)


def fetch_osm(path: Path, user_agent: str) -> None:
    s, w, n, e = QUERY_BBOX
    query = (
        f'[out:json][timeout:180];(nwr["place"~"^({PLACE_TYPES})$"]({s},{w},{n},{e}););'
        "out center tags;"
    )
    response = httpx.post(OVERPASS_URL, data={"data": query}, timeout=300,
                          headers={"User-Agent": user_agent})
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def _int(value) -> int | None:
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def read_osm(path: Path) -> list[Place]:
    data = json.loads(path.read_text(encoding="utf-8"))
    places: list[Place] = []
    for element in data["elements"]:
        tags = element.get("tags", {})
        name = tags.get("name:en") or tags.get("name")
        if not name:
            continue
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        alts = {tags[k] for k in ("name", "alt_name", "old_name", "official_name", "short_name")
                if k in tags}
        for k in ("alt_name", "old_name"):
            if k in tags:
                alts.update(part.strip() for part in tags[k].split(";"))
        places.append(Place(
            place_id=f"osm:{element['type'][0]}{element['id']}",
            name=name.strip(),
            lat=float(lat), lon=float(lon),
            feature=tags.get("place", "place"),
            source="osm",
            alt_names={a for a in alts if a and a != name and _LATIN.match(a)},
            name_ur=tags.get("name:ur") or (tags.get("name") if not _LATIN.match(tags.get("name", "a")) else None),
            population=_int(tags.get("population")),
        ))
    return places


def read_geonames(path: Path) -> list[Place]:
    s, w, n, e = QUERY_BBOX
    places: list[Place] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = dict(zip(GEONAMES_COLUMNS, line.rstrip("\n").split("\t")))
            if row["feature_class"] != "P":
                continue
            lat, lon = float(row["latitude"]), float(row["longitude"])
            if not (s <= lat <= n and w <= lon <= e):
                continue
            alts = {a for a in row["alternatenames"].split(",") if a and _LATIN.match(a)}
            name = row["asciiname"] or row["name"]
            alts.discard(name)
            places.append(Place(
                place_id=f"gn:{row['geonameid']}",
                name=name, lat=lat, lon=lon,
                feature=row["feature_code"].lower(),
                source="geonames",
                alt_names=alts,
                population=_int(row["population"]) or None,
            ))
    return places


def _km(a: Place, b: Place) -> float:
    dlat = (a.lat - b.lat) * 111.0
    dlon = (a.lon - b.lon) * 111.0 * math.cos(math.radians((a.lat + b.lat) / 2))
    return math.hypot(dlat, dlon)


def assign_and_merge(places: list[Place], locator: TehsilLocator) -> list[Place]:
    located: list[Place] = []
    for place in places:
        region = locator.locate(place.lat, place.lon)
        if region is None:
            continue
        place.tehsil_id = region.tehsil_id
        place.district_slug = region.tehsil_id.split("__")[0]
        located.append(place)

    # OSM first so its names win; GeoNames fills gaps and adds alternate names.
    # Same tehsil and either the same name key within 2 km, or a near-identical
    # spelling (fuzzy ratio >= 88) within 1 km, counts as the same place.
    located.sort(key=lambda p: (p.source != "osm", p.place_id))
    by_tehsil: dict[str, list[tuple[str, Place]]] = defaultdict(list)
    merged: list[Place] = []
    for place in located:
        key = name_key(place.name)
        target = None
        for other_key, other in by_tehsil[place.tehsil_id]:
            distance = _km(other, place)
            if (other_key == key and distance <= MERGE_KM) or (
                distance <= FUZZY_MERGE_KM and fuzz.ratio(other_key, key) >= FUZZY_MERGE_RATIO
            ):
                target = other
                break
        if target is None:
            by_tehsil[place.tehsil_id].append((key, place))
            merged.append(place)
            continue
        target.merged_ids.append(place.place_id)
        target.alt_names |= place.alt_names | ({place.name} - {target.name})
        target.population = target.population or place.population
        target.name_ur = target.name_ur or place.name_ur
    return merged


def write(places: list[Place], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["place_id", "name", "alt_names", "name_ur", "feature", "lat", "lon",
                         "district_slug", "tehsil_id", "population", "sources"])
        for p in sorted(places, key=lambda p: (p.tehsil_id, p.name)):
            sources = sorted({p.source} | {m.split(":")[0].replace("gn", "geonames") for m in p.merged_ids})
            writer.writerow([
                p.place_id, p.name, "|".join(sorted(p.alt_names)), p.name_ur or "",
                p.feature, round(p.lat, 5), round(p.lon, 5), p.district_slug, p.tehsil_id,
                p.population or "", "+".join(sources),
            ])


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    raw = settings.data_dir / "raw"
    ref = settings.data_dir / "reference"
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-osm", action="store_true", help="refresh the Overpass cache")
    parser.add_argument("--osm", type=Path, default=raw / "osm" / "places_overpass.json")
    parser.add_argument("--geonames", type=Path, default=raw / "geonames" / "PK.txt")
    parser.add_argument("--out", type=Path, default=ref / "gazetteer.csv")
    args = parser.parse_args(argv)

    if args.fetch_osm or not args.osm.exists():
        fetch_osm(args.osm, settings.pdma_user_agent)
    locator = TehsilLocator.from_geojson(ref / "tehsils.geojson")
    osm, gn = read_osm(args.osm), read_geonames(args.geonames)
    places = assign_and_merge(osm + gn, locator)
    write(places, args.out)

    per_tehsil = Counter(p.tehsil_id for p in places)
    empty = [r.tehsil_id for r in locator.regions if per_tehsil[r.tehsil_id] == 0]
    print(f"OSM {len(osm)}, GeoNames {len(gn)} -> {len(places)} places in the region")
    print(f"Tehsils with no place: {empty or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
