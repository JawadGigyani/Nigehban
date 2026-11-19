"""Riverbank danger-zone check for a point (M11).

A point is in the danger zone when either:
- it sits on low ground right beside a large river: the lowest height above the
  nearest stream within about 100 m is under 3 m, and a stream draining at least
  50 km² is within about 150 m; or
- it is at a riverside tourist spot (OSM picnic sites, viewpoints, camp sites,
  attractions, parks) that is itself on low ground beside a stream.

Combined with the model's level for today and tomorrow:
- high or very high + danger zone  -> "move_away"
- moderate + danger zone           -> "be_ready"
- otherwise                        -> "stay_alert" (in zone) or "normal"
The level always comes from the risk model; this check only adds where you stand.
"""

from __future__ import annotations

import gzip
import json
import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

log = logging.getLogger(__name__)

LOW_HAND_M = 3.0
BIG_RIVER_KM2 = 50.0
NEAR_RIVER_M = 150.0
LOW_WINDOW_M = 100.0
SPOT_RADIUS_M = 150.0
SPOT_TAGS = ('node["tourism"~"^(picnic_site|viewpoint|camp_site|attraction)$"]',
             'node["leisure"~"^(picnic_table|park)$"]', 'way["tourism"~"^(picnic_site|camp_site)$"]')


@dataclass(frozen=True)
class RasterSet:
    hand: object
    upstream: object
    name: str


def _open_sets(data_dir: Path) -> list[RasterSet]:
    import rasterio

    out = []
    for name, folder in (("glo30", data_dir / "interim" / "terrain" / "swat30"), ("glo90", data_dir / "interim" / "terrain")):
        h, u = folder / "hand.tif", folder / "stream_upstream_km2.tif"
        if h.is_file() and u.is_file():
            out.append(RasterSet(rasterio.open(h), rasterio.open(u), name))
    return out


def _window(src, lat: float, lon: float, radius_m: float):
    """Values within a square around the point, plus each cell's distance (m) to it."""

    from rasterio.windows import Window

    res_deg = abs(src.transform.a)
    cell_m = res_deg * 111_320 * math.cos(math.radians(lat))
    n = max(1, int(math.ceil(radius_m / cell_m)))
    row, col = src.index(lon, lat)
    win = Window(col - n, row - n, 2 * n + 1, 2 * n + 1)
    values = src.read(1, window=win, boundless=True, fill_value=np.nan if src.dtypes[0].startswith("float") else 0)
    ys, xs = np.mgrid[-n:n + 1, -n:n + 1]
    dist = np.hypot(ys * abs(src.transform.e) * 111_320, xs * res_deg * 111_320 * math.cos(math.radians(lat)))
    return values.astype(float), dist


class DangerChecker:
    def __init__(self, data_dir: Path, locator, user_agent: str = "nigehban-research/0.1") -> None:
        self.sets = _open_sets(data_dir)
        self.locator = locator
        self.spots_path = data_dir / "raw" / "osm" / "riverside_spots_overpass.json.gz"
        self.user_agent = user_agent
        self._spots: np.ndarray | None = None
        self._last_try = 0.0

    # ---- OSM tourist spots -----------------------------------------------------------------

    def spots(self) -> np.ndarray:
        """[[lon, lat, kind_index], ...] for the in-scope area (fetched once)."""

        if self._spots is not None:
            return self._spots
        if not self.spots_path.is_file() and time.time() - self._last_try < 600:
            return np.zeros((0, 2))  # fetch failed recently; the riverbank check still works
        if not self.spots_path.is_file():
            self._last_try = time.time()
            body = "".join(f"{t}(34.0,71.0,36.0,74.5);" for t in SPOT_TAGS)
            query = f"[out:json][timeout:120];({body});out center;"
            for attempt in range(3):
                try:
                    r = httpx.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=180,
                                   headers={"User-Agent": self.user_agent})
                    r.raise_for_status()
                    self.spots_path.parent.mkdir(parents=True, exist_ok=True)
                    with gzip.open(self.spots_path, "wt", encoding="utf-8") as fh:
                        fh.write(r.text)
                    break
                except httpx.HTTPError:
                    time.sleep(5 * (attempt + 1))
            if not self.spots_path.is_file():
                return np.zeros((0, 2))  # try again later; do not cache the empty result
        rows = []
        if self.spots_path.is_file():
            with gzip.open(self.spots_path, "rt", encoding="utf-8") as fh:
                for el in json.load(fh).get("elements", []):
                    lat = el.get("lat", el.get("center", {}).get("lat"))
                    lon = el.get("lon", el.get("center", {}).get("lon"))
                    if lat is not None:
                        rows.append((lon, lat))
        self._spots = np.array(rows) if rows else np.zeros((0, 2))
        return self._spots

    # ---- check -----------------------------------------------------------------------------

    def terrain_at(self, lat: float, lon: float) -> dict | None:
        for rs in self.sets:
            b = rs.hand.bounds
            if not (b.left <= lon <= b.right and b.bottom <= lat <= b.top):
                continue
            hand, hdist = _window(rs.hand, lat, lon, LOW_WINDOW_M)
            ups, udist = _window(rs.upstream, lat, lon, NEAR_RIVER_M)
            centre = hand[hand.shape[0] // 2, hand.shape[1] // 2]
            near_low = hand[(hdist <= LOW_WINDOW_M) & np.isfinite(hand)]
            big = (ups >= BIG_RIVER_KM2) & (udist <= NEAR_RIVER_M)
            return {
                "dem": rs.name,
                "hand_m": None if not np.isfinite(centre) else round(float(centre), 1),
                "lowest_hand_100m": None if near_low.size == 0 else round(float(near_low.min()), 1),
                "river_distance_m": None if not big.any() else round(float(udist[big].min())),
                "river_upstream_km2": None if not big.any() else round(float(ups[big].max())),
            }
        return None

    def check(self, lat: float, lon: float) -> dict:
        terrain = self.terrain_at(lat, lon)
        reasons: list[str] = []
        riverbank = bool(terrain and terrain["lowest_hand_100m"] is not None
                         and terrain["lowest_hand_100m"] < LOW_HAND_M and terrain["river_distance_m"] is not None)
        if riverbank:
            reasons.append(f"low ground ({terrain['lowest_hand_100m']} m above the stream) about "
                           f"{terrain['river_distance_m']} m from a river draining {terrain['river_upstream_km2']:,.0f} km²")
        spot = False
        pts = self.spots()
        if len(pts):
            d = np.hypot((pts[:, 1] - lat) * 111_320, (pts[:, 0] - lon) * 111_320 * math.cos(math.radians(lat)))
            near = d <= SPOT_RADIUS_M
            if near.any() and terrain and terrain["lowest_hand_100m"] is not None and terrain["lowest_hand_100m"] < 5:
                spot = True
                reasons.append(f"riverside picnic or tourist spot about {d[near].min():.0f} m away")
        region = self.locator.locate(lat, lon) if self.locator else None
        return {"tehsil_id": region.tehsil_id if region else None, "in_danger_zone": riverbank or spot,
                "riverbank": riverbank, "tourist_spot": spot, "reasons": reasons, "terrain": terrain}


def advice(in_zone: bool, level: str | None) -> str:
    if in_zone and level in ("high", "very_high"):
        return "move_away"
    if in_zone and level == "moderate":
        return "be_ready"
    return "stay_alert" if in_zone else "normal"
