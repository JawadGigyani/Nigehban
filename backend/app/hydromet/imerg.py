"""NASA GPM IMERG daily satellite rain per tehsil (via GES DISC OPeNDAP, Earthdata token).

- Runs: "early" (about 4 hours after the day; for live use), "late" (about 14 hours),
  "final" (about 3.5 months; for history and training).
- Only the in-scope box is requested (OPeNDAP subset), not global files.
- 0.1° grid (cell centres at x.x5); each tehsil is the area-weighted mean over the cells it
  overlaps, plus the wettest cell.
- Needs `NIGEHBAN_EARTHDATA_TOKEN` and, once per account, approving "NASA GESDISC DATA ARCHIVE"
  under Earthdata profile -> Applications -> Authorized Apps.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import re
from pathlib import Path

import httpx
import numpy as np

BASE = "https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3"
PRODUCTS = {
    "early": ("GPM_3IMERGDE.07", "3B-DAY-E.MS.MRG.3IMERG.{d}-S000000-E235959.V07B.nc4"),
    "late": ("GPM_3IMERGDL.07", "3B-DAY-L.MS.MRG.3IMERG.{d}-S000000-E235959.V07B.nc4"),
    "final": ("GPM_3IMERGDF.07", "3B-DAY.MS.MRG.3IMERG.{d}-S000000-E235959.V07B.nc4"),
}
BOX = (34.0, 71.0, 36.1, 74.6)  # south, west, north, east
STEP = 0.1


class ImergError(RuntimeError):
    pass


def _index(value: float, origin: float) -> int:
    return int(round((value - origin) / STEP))


LON0, LON1 = _index(BOX[1], -179.95), _index(BOX[3], -179.95)
LAT0, LAT1 = _index(BOX[0], -89.95), _index(BOX[2], -89.95)
LONS = np.round(-179.95 + STEP * np.arange(LON0, LON1 + 1), 2)
LATS = np.round(-89.95 + STEP * np.arange(LAT0, LAT1 + 1), 2)


def parse_ascii(text: str) -> np.ndarray:
    """OPeNDAP ASCII for precipitation[time][lon][lat] -> array [lon, lat] (mm/day)."""

    rows = []
    for line in text.splitlines():
        m = re.match(r"^\s*\[0\]\[(\d+)\],\s*(.*)$", line)
        if m:
            rows.append([float(v) for v in m.group(2).split(",") if v.strip()])
    if not rows:
        raise ImergError("No precipitation values in the OPeNDAP response.")
    arr = np.array(rows, dtype=float)
    arr[arr < 0] = np.nan  # fill values
    return arr


class ImergClient:
    def __init__(self, token: str | None, cache_dir: Path, http: httpx.Client | None = None) -> None:
        self.token = token
        self.cache_dir = cache_dir
        self.http = http or httpx.Client(timeout=120, follow_redirects=True)

    @classmethod
    def from_settings(cls, settings) -> ImergClient:
        token = settings.earthdata_token.get_secret_value() if settings.earthdata_token else None
        return cls(token, settings.data_dir / "cache" / "imerg")

    def url(self, day: dt.date, run: str) -> str:
        product, pattern = PRODUCTS[run]
        name = pattern.format(d=day.strftime("%Y%m%d"))
        return (f"{BASE}/{product}/{day:%Y}/{day:%m}/{name}.ascii?"
                f"precipitation[0:0][{LON0}:{LON1}][{LAT0}:{LAT1}]")

    def day(self, day: dt.date, run: str = "final") -> np.ndarray | None:
        """Grid [lon, lat] in mm for the local box, or None if the file does not exist yet."""

        path = self.cache_dir / f"{run}_{day:%Y%m%d}.json.gz"
        if path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                data = json.load(fh)
            return None if data is None else np.array(data, dtype=float)
        if not self.token:
            raise ImergError("Set NIGEHBAN_EARTHDATA_TOKEN.")
        r = self.http.get(self.url(day, run), headers={"Authorization": f"Bearer {self.token}"})
        if r.status_code == 404:
            return None  # not produced yet (latency) or missing
        if r.status_code == 401:
            raise ImergError("Earthdata refused the token: approve 'NASA GESDISC DATA ARCHIVE' under "
                             "Earthdata profile -> Applications -> Authorized Apps, or renew the token.")
        if r.status_code != 200:
            raise ImergError(f"GES DISC returned {r.status_code}.")
        grid = parse_ascii(r.text)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(np.where(np.isnan(grid), -1, grid).round(2).tolist(), fh)
        return grid


def tehsil_weights(tehsils_geojson: Path, in_scope_only: bool = True) -> dict[str, list[tuple[int, int, float]]]:
    """tehsil_id -> [(lon_idx, lat_idx, weight)] over the local IMERG box."""

    from shapely.geometry import box, shape

    data = json.loads(tehsils_geojson.read_text(encoding="utf-8"))
    out = {}
    for f in data["features"]:
        p = f["properties"]
        if in_scope_only and not p.get("in_scope"):
            continue
        geom = shape(f["geometry"])
        minx, miny, maxx, maxy = geom.bounds
        cells = []
        for i, lon in enumerate(LONS):
            if lon + STEP / 2 < minx or lon - STEP / 2 > maxx:
                continue
            for j, lat in enumerate(LATS):
                if lat + STEP / 2 < miny or lat - STEP / 2 > maxy:
                    continue
                a = geom.intersection(box(lon - STEP / 2, lat - STEP / 2, lon + STEP / 2, lat + STEP / 2)).area
                if a > 0:
                    cells.append((i, j, a))
        total = sum(a for *_, a in cells)
        out[p["tehsil_id"]] = [(i, j, a / total) for i, j, a in cells]
    return out


def tehsil_values(grid: np.ndarray, weights: dict[str, list[tuple[int, int, float]]]) -> dict[str, tuple[float, float]]:
    """tehsil_id -> (area-weighted mean mm, wettest cell mm)."""

    out = {}
    for tehsil_id, cells in weights.items():
        vals = [(grid[i, j], w) for i, j, w in cells if 0 <= i < grid.shape[0] and 0 <= j < grid.shape[1]
                and np.isfinite(grid[i, j])]
        if not vals:
            continue
        wsum = sum(w for _, w in vals)
        out[tehsil_id] = (round(sum(v * w for v, w in vals) / wsum, 2), round(max(v for v, _ in vals), 2))
    return out
