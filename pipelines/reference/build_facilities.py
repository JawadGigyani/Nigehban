"""Shelter candidates, health facilities and Rescue 1122 stations from OpenStreetMap.

- Source: OpenStreetMap via the Overpass API (ODbL). One query, cached at
  `data/raw/osm/facilities_overpass.json` (refresh with `--fetch`).
- Kinds: `shelter` (schools, colleges, universities, government offices, town
  halls, community centres), `health` (hospitals, clinics), `rescue_1122`
  (name or operator mentions 1122 / Rescue, or an ambulance station),
  `police`, `fire`.
- Every row is marked `verified=false`: OSM is incomplete and unchecked. The
  board shows them as "unverified" until PDMA or the district confirms.
- Each facility gets its tehsil and its HAND exposure band (from M3), so the
  advisory can prefer shelters on high ground.

    python -m pipelines.reference.build_facilities [--fetch]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import rasterio

from backend.app.config import get_settings
from backend.app.geo.locator import TehsilLocator
from pipelines.terrain.build_terrain import band

OVERPASS_URLS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
BBOX = (34.0, 71.0, 36.0, 74.5)  # south, west, north, east (in-scope tehsils)

QUERY = """
[out:json][timeout:240];
(
  nwr["amenity"~"^(school|college|university|townhall|community_centre)$"]({bbox});
  nwr["office"="government"]({bbox});
  nwr["building"~"^(school|college|university|government|public)$"]({bbox});
  nwr["amenity"="place_of_worship"]["religion"="muslim"]({bbox});
  nwr["amenity"~"^(hospital|clinic)$"]({bbox});
  nwr["healthcare"~"^(hospital|clinic)$"]({bbox});
  nwr["amenity"~"^(fire_station|police)$"]({bbox});
  nwr["emergency"="ambulance_station"]({bbox});
  nwr["name"~"1122|[Rr]escue"]({bbox});
  nwr["operator"~"1122|[Rr]escue"]({bbox});
);
out center tags;
"""


def classify(tags: dict) -> str | None:
    text = " ".join(str(tags.get(k, "")) for k in ("name", "name:en", "operator")).lower()
    amenity = tags.get("amenity", "")
    if "1122" in text or "rescue" in text or tags.get("emergency") == "ambulance_station":
        return "rescue_1122"
    if amenity in {"hospital", "clinic"} or tags.get("healthcare") in {"hospital", "clinic"}:
        return "health"
    if amenity == "fire_station":
        return "fire"
    if amenity == "police":
        return "police"
    if amenity in {"school", "college", "university", "townhall", "community_centre"} \
            or tags.get("office") == "government" \
            or tags.get("building") in {"school", "college", "university", "government", "public"}:
        return "shelter"
    if amenity == "place_of_worship":
        return "shelter"  # mosques: second choice, see shelter_priority
    return None


def shelter_priority(tags: dict) -> int | None:
    """1 = school, college or government building; 2 = mosque or other community building."""

    if classify(tags) != "shelter":
        return None
    return 2 if tags.get("amenity") == "place_of_worship" else 1


def fetch(path: Path, user_agent: str) -> None:
    south, west, north, east = BBOX
    query = QUERY.replace("{bbox}", f"{south},{west},{north},{east}")
    import time

    last: Exception | None = None
    for attempt in range(4):
        url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
        try:
            response = httpx.post(url, data={"data": query}, timeout=300, headers={"User-Agent": user_agent})
            response.raise_for_status()
            break
        except httpx.HTTPError as exc:  # busy servers answer 429/502/504
            last = exc
            time.sleep(20 * (attempt + 1))
    else:
        raise RuntimeError(f"Overpass failed: {last}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text, encoding="utf-8")


def build(raw: dict, locator: TehsilLocator, hand_path: Path | None) -> pd.DataFrame:
    hand_src = rasterio.open(hand_path) if hand_path and hand_path.is_file() else None
    rows = []
    try:
        for el in raw.get("elements", []):
            tags = el.get("tags", {})
            kind = classify(tags)
            if kind is None:
                continue
            lat = el.get("lat", el.get("center", {}).get("lat"))
            lon = el.get("lon", el.get("center", {}).get("lon"))
            if lat is None or lon is None:
                continue
            region = locator.locate(lat, lon)
            hand = None
            if hand_src is not None:
                value = next(hand_src.sample([(lon, lat)]))[0]
                hand = round(float(value), 1) if math.isfinite(value) else None  # lowest HAND within ~180 m
            rows.append({
                "facility_id": f"osm:{el['type'][0]}{el['id']}",
                "kind": kind,
                "subtype": tags.get("amenity") or tags.get("office") or tags.get("healthcare")
                or tags.get("emergency") or tags.get("building") or "",
                "shelter_priority": shelter_priority(tags),
                "name": tags.get("name:en") or tags.get("name") or "",
                "name_ur": tags.get("name:ur", ""),
                "lat": round(lat, 6), "lon": round(lon, 6),
                "tehsil_id": region.tehsil_id if region else "",
                "hand_min_m": hand,
                "exposure_band": band(hand) if hand is not None else "",
                "verified": False,
                "source": "osm",
            })
    finally:
        if hand_src is not None:
            hand_src.close()
    frame = pd.DataFrame(rows).drop_duplicates("facility_id")
    return frame[frame["tehsil_id"] != ""].sort_values(["tehsil_id", "kind", "name"]).reset_index(drop=True)


def rescue_from_manual(path: Path, gazetteer: pd.DataFrame, locator: TehsilLocator) -> pd.DataFrame:
    """Rescue 1122 entries from news reports, placed at the town centre (approximate)."""

    rows = []
    manual = pd.read_csv(path)
    for r in manual.itertuples(index=False):
        hits = gazetteer[(gazetteer["name"].str.lower() == r.town.lower())
                         & (gazetteer["district_slug"] == r.district_slug)]
        if hits.empty:
            continue
        best = hits.sort_values("population", ascending=False, na_position="last").iloc[0]
        region = locator.locate(best["lat"], best["lon"])
        rows.append({"facility_id": f"manual:rescue1122:{r.district_slug}:{r.town.lower().replace(' ', '_')}",
                     "kind": "rescue_1122", "subtype": r.status, "shelter_priority": None,
                     "name": f"Rescue 1122 {r.town}", "name_ur": "", "lat": round(best["lat"], 6),
                     "lon": round(best["lon"], 6), "tehsil_id": region.tehsil_id if region else best["tehsil_id"],
                     "hand_min_m": None, "exposure_band": "", "verified": False,
                     "source": f"news/official page; town-centre location; {r.source}"})
    return pd.DataFrame(rows)


def high_ground(villages: pd.DataFrame, tehsil_ids: list[str], per_tehsil: int = 3,
                radius_km: float = 3.0) -> pd.DataFrame:
    """Suggested higher ground: low-exposure villages close to the most high-exposure villages.

    Used when a tehsil has few or no known shelter buildings. Not a shelter: the
    advisory says "move to higher ground, for example ...".
    """

    rows = []
    for tehsil_id in tehsil_ids:
        part = villages[villages["tehsil_id"] == tehsil_id]
        safe = part[(part["exposure_band"] == "low") & part["hand_min_m"].between(15, 120)
                    & (part["dist_to_stream_m"] >= 300)]
        exposed = part[part["exposure_band"] == "high"]
        if safe.empty:
            continue
        if exposed.empty:
            exposed = part[part["exposure_band"] == "medium"]
        lat = np.radians(safe["lat"].to_numpy())[:, None]
        lon = np.radians(safe["lon"].to_numpy())[:, None]
        elat = np.radians(exposed["lat"].to_numpy())[None, :]
        elon = np.radians(exposed["lon"].to_numpy())[None, :]
        d = 6371 * np.arccos(np.clip(np.sin(lat) * np.sin(elat)
                                     + np.cos(lat) * np.cos(elat) * np.cos(lon - elon), -1, 1))
        served = (d <= radius_km).sum(axis=1) if exposed.size else np.zeros(len(safe))
        ranked = safe.assign(served=served).sort_values(["served", "hand_min_m"], ascending=[False, True])
        for r in ranked.head(per_tehsil).itertuples(index=False):
            rows.append({"facility_id": f"high_ground:{r.village_id}", "kind": "high_ground",
                         "subtype": f"serves {int(r.served)} high-exposure villages within {radius_km:g} km",
                         "shelter_priority": 3, "name": r.name, "name_ur": "", "lat": r.lat, "lon": r.lon,
                         "tehsil_id": tehsil_id, "hand_min_m": r.hand_min_m, "exposure_band": "low",
                         "verified": False, "source": "derived from DEM (M3); no known building"})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    data = settings.data_dir
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="refresh the Overpass cache")
    args = parser.parse_args(argv)
    raw_path = data / "raw" / "osm" / "facilities_overpass.json"
    if args.fetch or not raw_path.is_file():
        fetch(raw_path, settings.pdma_user_agent)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    locator = TehsilLocator.from_geojson(data / "reference" / "tehsils.geojson")
    frame = build(raw, locator, data / "interim" / "terrain" / "hand_min5.tif")
    gazetteer = pd.read_csv(data / "reference" / "gazetteer.csv")
    in_scope = [r.tehsil_id for r in locator.regions if r.in_scope]
    extra = [rescue_from_manual(data / "reference" / "rescue1122_manual.csv", gazetteer, locator)]
    villages_path = data / "reference" / "village_exposure.csv"
    if villages_path.is_file():
        extra.append(high_ground(pd.read_csv(villages_path), in_scope))
    frame = pd.concat([frame, *extra], ignore_index=True)
    out = data / "reference" / "facilities.csv"
    frame.to_csv(out, index=False)
    print(frame.groupby("kind").size().to_dict(), f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
