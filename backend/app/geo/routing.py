"""Route to the nearest safer place (M10).

Engines:
- OpenRouteService (free key, `NIGEHBAN_ORS_API_KEY`), when set;
- otherwise a built-in router on OpenStreetMap roads and paths (networkx). Roads
  are fetched per 0.25° tile from the Overpass API and cached on disk. Segments
  on low ground beside streams (HAND under 3 m) cost five times more, so the
  route prefers higher roads but can still cross a bridge.

Destinations: the nearest shelters and higher ground not in the high-exposure
band. All are unverified, and the answer says so.
"""

from __future__ import annotations

import gzip
import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import networkx as nx
import numpy as np

log = logging.getLogger(__name__)

TILE = 0.1  # small tiles keep each Overpass request light
OVERPASS_URLS = ("https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
                 "https://overpass.kumi.systems/api/interpreter")
HIGHWAYS = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|road|"
            "track|path|footway|steps|bridleway|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link")
DRIVE_KMH = {"motorway": 70, "trunk": 60, "primary": 50, "secondary": 40, "tertiary": 30, "unclassified": 20,
             "residential": 20, "living_street": 10, "service": 15, "road": 20, "track": 10}
WALK_KMH = 4.0
LOW_GROUND_M = 3.0
LOW_GROUND_PENALTY = 5.0


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


@dataclass
class Route:
    engine: str
    destination: dict
    distance_m: float
    duration_s: float
    geometry: list[list[float]]  # [[lon, lat], ...]
    low_ground_share: float | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"engine": self.engine, "destination": self.destination, "distance_m": round(self.distance_m),
                "duration_min": round(self.duration_s / 60, 1),
                "geometry": {"type": "LineString", "coordinates": self.geometry},
                "low_ground_share": None if self.low_ground_share is None else round(self.low_ground_share, 2),
                "notes": self.notes}


class RoadTiles:
    """OSM ways per 0.25° tile, fetched once and cached (gzip JSON)."""

    def __init__(self, cache_dir: Path, user_agent: str = "nigehban-research/0.1") -> None:
        self.cache_dir = cache_dir
        self.user_agent = user_agent

    def _path(self, ty: int, tx: int) -> Path:
        return self.cache_dir / f"roads_{ty}_{tx}.json.gz"

    def tile(self, ty: int, tx: int) -> list[dict]:
        path = self._path(ty, tx)
        if path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                return json.load(fh)
        south, west = ty * TILE, tx * TILE
        query = (f'[out:json][timeout:120];way["highway"~"^({HIGHWAYS})$"]'
                 f"({south},{west},{south + TILE},{west + TILE});out geom tags;")
        data = None
        for attempt in range(4):
            url = OVERPASS_URLS[attempt % len(OVERPASS_URLS)]
            try:
                r = httpx.post(url, data={"data": query}, timeout=180, headers={"User-Agent": self.user_agent})
                r.raise_for_status()
                data = r.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("Overpass tile %s,%s failed (%s); retrying", ty, tx, exc.__class__.__name__)
                time.sleep(10 * (attempt + 1))
        if data is None:
            raise RuntimeError("OpenStreetMap roads are unavailable right now.")
        ways = [{"hw": el["tags"].get("highway", ""), "pts": [[p["lon"], p["lat"]] for p in el["geometry"]]}
                for el in data.get("elements", []) if el.get("type") == "way" and el.get("geometry")]
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(ways, fh)
        return ways

    def ways_for_bbox(self, south: float, west: float, north: float, east: float, max_tiles: int = 30) -> list[dict]:
        tiles = [(ty, tx) for ty in range(math.floor(south / TILE), math.floor(north / TILE) + 1)
                 for tx in range(math.floor(west / TILE), math.floor(east / TILE) + 1)]
        if len(tiles) > max_tiles:
            raise ValueError("Route area too large.")
        ways: list[dict] = []
        for ty, tx in tiles:
            ways += self.tile(ty, tx)
        return ways


class LowGround:
    """HAND lookup: the 30 m Swat raster where it exists, else the 90 m one."""

    def __init__(self, paths: list[Path]) -> None:
        import rasterio

        self.sources = [rasterio.open(p) for p in paths if p.is_file()]

    def hand(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        out = np.full(len(lons), np.nan)
        for src in self.sources:
            todo = np.isnan(out)
            if not todo.any():
                break
            b = src.bounds
            inside = todo & (lons >= b.left) & (lons <= b.right) & (lats >= b.bottom) & (lats <= b.top)
            if inside.any():
                vals = np.array([v[0] for v in src.sample(list(zip(lons[inside], lats[inside], strict=True)))],
                                dtype=float)
                vals[vals < -1000] = np.nan
                out[inside] = vals
        return out


def build_graph(ways: list[dict], mode: str, low_ground: LowGround | None) -> nx.Graph:
    graph = nx.Graph()
    segs = []
    for way in ways:
        hw = way["hw"]
        if mode == "drive" and hw not in DRIVE_KMH:
            continue
        speed = DRIVE_KMH.get(hw, 15) if mode == "drive" else WALK_KMH
        pts = way["pts"]
        for (lon1, lat1), (lon2, lat2) in zip(pts, pts[1:], strict=False):
            segs.append((round(lon1, 6), round(lat1, 6), round(lon2, 6), round(lat2, 6), speed))
    if not segs:
        return graph
    arr = np.array([s[:4] for s in segs])
    mid_hand = (low_ground.hand((arr[:, 0] + arr[:, 2]) / 2, (arr[:, 1] + arr[:, 3]) / 2)
                if low_ground else np.full(len(segs), np.nan))
    for (lon1, lat1, lon2, lat2, speed), h in zip(segs, mid_hand, strict=True):
        length = km(lat1, lon1, lat2, lon2) * 1000
        low = bool(np.isfinite(h) and h < LOW_GROUND_M)
        seconds = length / (speed / 3.6)
        graph.add_edge((lon1, lat1), (lon2, lat2), length=length, seconds=seconds, low=low,
                       cost=seconds * (LOW_GROUND_PENALTY if low else 1.0))
    return graph


class SafeRouter:
    def __init__(self, tiles: RoadTiles, low_ground: LowGround | None, facilities, ors_key: str | None = None) -> None:
        self.tiles = tiles
        self.low_ground = low_ground
        self.facilities = facilities
        self.ors_key = ors_key

    def candidates(self, lat: float, lon: float, k: int = 4, max_km: float = 12.0) -> list[dict]:
        f = self.facilities
        f = f[f["kind"].isin(["shelter", "high_ground"]) & (f["exposure_band"] != "high")].copy()
        f["km"] = [km(lat, lon, a, b) for a, b in zip(f["lat"], f["lon"], strict=True)]
        f = f[f["km"] <= max_km].nsmallest(k, "km")
        return [{"id": r.facility_id, "kind": r.kind, "name": r.name if isinstance(r.name, str) else "",
                 "subtype": r.subtype if isinstance(r.subtype, str) else "", "lat": float(r.lat), "lon": float(r.lon),
                 "straight_km": round(float(r.km), 2)} for r in f.itertuples(index=False)]

    def route(self, lat: float, lon: float, mode: str = "walk") -> Route | None:
        dests = self.candidates(lat, lon)
        if not dests:
            return None
        if self.ors_key:
            try:
                return self._route_ors(lat, lon, dests, mode)
            except Exception as exc:  # fall back to the built-in router
                log.warning("ORS failed: %s", exc.__class__.__name__)
        return self._route_osm(lat, lon, dests, mode)

    def _route_osm(self, lat: float, lon: float, dests: list[dict], mode: str) -> Route | None:
        from scipy.spatial import cKDTree

        lats = [lat, *(d["lat"] for d in dests)]
        lons = [lon, *(d["lon"] for d in dests)]
        margin = 0.03
        ways = self.tiles.ways_for_bbox(min(lats) - margin, min(lons) - margin, max(lats) + margin, max(lons) + margin)
        graph = build_graph(ways, mode, self.low_ground)
        if graph.number_of_nodes() == 0:
            return None
        # Keep the part of the network connected to the start.
        nodes = list(graph.nodes)
        tree = cKDTree(np.array(nodes))
        _, i0 = tree.query([lon, lat])
        start = nodes[int(i0)]
        dist, paths = nx.single_source_dijkstra(graph, start, weight="cost")
        best = None
        for d in dests:
            _, j = tree.query([d["lon"], d["lat"]])
            node = nodes[int(j)]
            if node in dist and (best is None or dist[node] < best[0]):
                best = (dist[node], d, paths[node])
        if best is None:
            return None
        _, dest, path = best
        edges = [graph.edges[a, b] for a, b in zip(path, path[1:], strict=False)]
        length = sum(e["length"] for e in edges)
        seconds = sum(e["seconds"] for e in edges)
        low = sum(e["length"] for e in edges if e["low"]) / length if length else 0.0
        start_gap = km(lat, lon, start[1], start[0]) * 1000
        notes = ["Destination location is unverified."]
        if start_gap > 300:
            notes.append(f"Nearest mapped road or path is about {start_gap:.0f} m away.")
        if low > 0.2:
            notes.append("Part of this route runs on low ground beside a stream: cross quickly, never through water.")
        return Route("osm", dest, length + start_gap, seconds + start_gap / (WALK_KMH / 3.6),
                     [[lon, lat], *[[p[0], p[1]] for p in path], [dest["lon"], dest["lat"]]], low, notes)

    def _route_ors(self, lat: float, lon: float, dests: list[dict], mode: str) -> Route:
        profile = "foot-walking" if mode == "walk" else "driving-car"
        best = None
        for d in dests[:3]:
            r = httpx.post(f"https://api.openrouteservice.org/v2/directions/{profile}/geojson",
                           json={"coordinates": [[lon, lat], [d["lon"], d["lat"]]]},
                           headers={"Authorization": self.ors_key}, timeout=20)
            r.raise_for_status()
            feat = r.json()["features"][0]
            summary = feat["properties"]["summary"]
            if best is None or summary["duration"] < best[0]["duration"]:
                best = (summary, d, feat["geometry"]["coordinates"])
        summary, dest, coords = best
        return Route("openrouteservice", dest, summary["distance"], summary["duration"], coords, None,
                     ["Destination location is unverified."])
