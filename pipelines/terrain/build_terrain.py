"""Terrain features from the Copernicus DEM: HAND, slope, streams, tehsil statics, village bands.

Steps
1. Condition the DEM (fill pits and depressions, resolve flats), D8 flow
   directions and flow accumulation (pysheds).
2. Streams: cells draining at least `--hand-stream-km2` (default 10 km²) are the
   reference channels for HAND; cells draining at least 1 km² count for
   drainage density.
3. HAND (height above nearest drainage, metres) and slope (degrees).
4. Per tehsil: mean and 90th-percentile slope, largest upstream area, drainage
   density, share of land with HAND < 3 m, and population (WorldPop 2020 1 km,
   scaled to the 2023 census tehsil totals) in total and on low-HAND land.
5. Per village (gazetteer): HAND at the point, distance to the nearest stream,
   that stream's upstream area, and a band: HAND < 3 m high, 3–8 m medium,
   > 8 m low. Bands only, never flood depths.

Outputs: data/features/tehsil_static.parquet, data/reference/village_exposure.csv,
data/interim/terrain/{hand,slope,streams}.tif, reports/terrain_qa.md (via qa).

    python -m pipelines.terrain.build_terrain
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import shape

from backend.app.config import get_settings

# Bands use the lowest HAND within about 180 m of the place (a 5 x 5 window of
# 90 m cells), because a village point is its centre while flooding starts at
# its riverside edge. Thresholds were tuned on villages named in PDMA flood
# reports (M1): see reports/terrain_qa.md.
HIGH_HAND_M = 5.0
HIGH_MIN_UPSTREAM_KM2 = 50.0
MEDIUM_HAND_M = 8.0
WINDOW_CELLS = 5
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
WORLDPOP_URL = ("https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/PAK/"
                "pak_ppp_2020_1km_Aggregated.tif")
POPULATED = {"ppl", "pplx", "pplq", "ppll", "village", "hamlet", "town", "city", "suburb",
             "neighbourhood", "locality", "ppla", "ppla2", "ppla3", "pplc"}


def band(hand_min_m: float, upstream_km2: float | None = None) -> str:
    """Exposure band from the lowest nearby HAND and the size of the nearest river."""

    big_river = upstream_km2 is None or upstream_km2 >= HIGH_MIN_UPSTREAM_KM2
    if hand_min_m < HIGH_HAND_M and big_river:
        return "high"
    if hand_min_m < MEDIUM_HAND_M:
        return "medium"
    return "low"


def cell_sizes_m(transform, height: int) -> tuple[np.ndarray, float]:
    """Width of a cell in metres for each row, and the (constant) height."""

    res_x, res_y = transform.a, -transform.e
    lats = transform.f - (np.arange(height) + 0.5) * res_y
    dy = res_y * 111_320.0
    dx = res_x * 111_320.0 * np.cos(np.radians(lats))
    return dx.astype("float32"), float(dy)


def condition_and_route(dem_path: Path):
    if not hasattr(np, "in1d"):  # pysheds 0.4 still calls np.in1d (removed in numpy 2.4)
        np.in1d = np.isin
    from pysheds.grid import Grid

    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    filled = grid.fill_depressions(grid.fill_pits(dem))
    inflated = grid.resolve_flats(filled)
    del filled
    gc.collect()
    fdir = grid.flowdir(inflated, dirmap=DIRMAP)
    del inflated
    gc.collect()
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    return grid, dem, fdir, acc


def compute_slope(dem: np.ndarray, dx: np.ndarray, dy: float) -> np.ndarray:
    z = dem.astype("float32")
    gy, gx = np.gradient(z)
    gx /= dx[:, None]
    gy /= dy
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")


def write_raster(path: Path, array: np.ndarray, profile: dict, nodata=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prof = profile | {"dtype": str(array.dtype), "count": 1, "compress": "deflate", "nodata": nodata}
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(array, 1)


def fetch_worldpop(path: Path) -> Path:
    if not path.is_file():
        import httpx

        path.parent.mkdir(parents=True, exist_ok=True)
        response = httpx.get(WORLDPOP_URL, timeout=300, follow_redirects=True)
        response.raise_for_status()
        path.write_bytes(response.content)
    return path


def population_density(worldpop: Path, profile: dict, shape_: tuple[int, int]) -> np.ndarray:
    """People per DEM cell: WorldPop 1 km counts spread evenly over the DEM cells inside."""

    from rasterio.warp import Resampling, reproject

    out = np.zeros(shape_, dtype="float32")
    with rasterio.open(worldpop) as src:
        counts = src.read(1).astype("float32")
        counts[counts < 0] = 0
        # Density per degree², resampled bilinearly, then times the DEM cell size in degrees².
        density = counts / (abs(src.transform.a) * abs(src.transform.e))
        reproject(density, out, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=profile["transform"], dst_crs=profile["crs"], resampling=Resampling.average)
    return out * abs(profile["transform"].a) * abs(profile["transform"].e)


def main(argv: list[str] | None = None) -> int:
    data = get_settings().data_dir
    parser = argparse.ArgumentParser()
    parser.add_argument("--dem", type=Path, default=data / "interim" / "terrain" / "dem_glo90.tif")
    parser.add_argument("--hand-stream-km2", type=float, default=10.0)
    parser.add_argument("--density-stream-km2", type=float, default=1.0)
    parser.add_argument("--tag", default="", help="write to interim/terrain/<tag>/ instead of the main outputs")
    args = parser.parse_args(argv)
    terrain_dir = data / "interim" / "terrain" / args.tag if args.tag else data / "interim" / "terrain"

    with rasterio.open(args.dem) as src:
        profile = src.profile.copy()
        transform, height, width = src.transform, src.height, src.width
    dx, dy = cell_sizes_m(transform, height)
    cell_km2 = (dx * dy / 1e6)[:, None]  # per row

    print("routing flow ...", flush=True)
    grid, dem, fdir, acc = condition_and_route(args.dem)
    upstream_km2 = (np.asarray(acc, dtype="float32") * cell_km2).astype("float32")
    hand_streams = upstream_km2 >= args.hand_stream_km2
    print("computing HAND ...", flush=True)
    hand_raster = grid.compute_hand(fdir, dem, _as_raster(grid, hand_streams, acc))
    hand = np.asarray(hand_raster, dtype="float32")
    del hand_raster, fdir, acc
    gc.collect()
    hand[~np.isfinite(hand)] = np.nan
    hand = np.clip(hand, 0, None)  # small negatives come from the unconditioned DEM
    from scipy.ndimage import minimum_filter

    # Same ground distance (about ±180 m) whatever the DEM resolution: 5 cells at 90 m, 15 at 30 m.
    window = max(3, int(round(WINDOW_CELLS * 92.8 / dy)) | 1)
    hand_min = minimum_filter(np.where(np.isfinite(hand), hand, 1e6).astype("float32"), size=window)
    hand_min[~np.isfinite(hand)] = np.nan
    dem_arr = np.asarray(dem, dtype="float32")
    slope = compute_slope(dem_arr, dx, dy)
    del dem, dem_arr
    gc.collect()

    write_raster(terrain_dir / "hand.tif", hand, profile, nodata=float("nan"))
    write_raster(terrain_dir / "hand_min5.tif", hand_min, profile, nodata=float("nan"))
    write_raster(terrain_dir / "slope.tif", slope, profile, nodata=float("nan"))
    write_raster(terrain_dir / "streams.tif", hand_streams.astype("uint8"), profile, nodata=0)
    # Upstream area of each stream cell (km², 0 elsewhere) for the riverbank danger check (M11).
    write_raster(terrain_dir / "stream_upstream_km2.tif",
                 np.where(hand_streams, upstream_km2, 0).astype("float32"), profile, nodata=0)

    # Distance to the nearest HAND stream (metres, anisotropic cells handled per row mean).
    from scipy.ndimage import distance_transform_edt

    mean_dx = float(dx.mean())
    dist, (iy, ix) = distance_transform_edt(~hand_streams, sampling=(dy, mean_dx), return_indices=True)
    dist = dist.astype("float32")

    # ---- tehsil statics -------------------------------------------------------------------
    tehsils = json.loads((data / "reference" / "tehsils.geojson").read_text(encoding="utf-8"))["features"]
    ids = [f["properties"]["tehsil_id"] for f in tehsils]
    zones = rasterize(((shape(f["geometry"]), i + 1) for i, f in enumerate(tehsils)),
                      out_shape=(height, width), transform=transform, fill=0, dtype="int32")
    density_streams = upstream_km2 >= args.density_stream_km2
    print("population ...", flush=True)
    pop = population_density(fetch_worldpop(data / "raw" / "worldpop" / "pak_ppp_2020_1km_Aggregated.tif"),
                             profile, (height, width))
    census = pd.read_csv(data / "reference" / "census2023_kp_tehsils.csv")
    census_by_id = _census_by_tehsil(census, data)

    area_grid = np.broadcast_to(cell_km2, (height, width))
    rows = []
    for i, tehsil_id in enumerate(ids):
        mask = zones == i + 1
        n = int(mask.sum())
        if n == 0:
            continue
        h = hand[mask]
        valid = np.isfinite(h)
        area = float(area_grid[mask].sum())
        low = valid & (h < HIGH_HAND_M)
        s = slope[mask]
        stream_len_km = float(density_streams[mask].sum()) * (mean_dx + dy) / 2 / 1000
        wp_total = float(pop[mask].sum())
        wp_low = float(pop[mask][low].sum())
        scale = census_by_id.get(tehsil_id, wp_total) / wp_total if wp_total > 0 else 1.0
        rows.append({
            "tehsil_id": tehsil_id,
            "mean_slope": round(float(np.nanmean(s)), 3),
            "p90_slope": round(float(np.nanpercentile(s, 90)), 3),
            "catchment_area_km2": round(float(upstream_km2[mask].max()), 1),
            "drainage_density": round(stream_len_km / area, 4),
            "share_low_hand": round(float(low.sum() / max(valid.sum(), 1)), 4),
            "population": round(wp_total * scale) if wp_total > 0 else None,
            "population_low_hand": round(wp_low * scale) if wp_total > 0 else None,
            "dem_coverage": round(float(valid.sum() / n), 4),
        })
    static = pd.DataFrame(rows)
    features = data / "features"
    features.mkdir(parents=True, exist_ok=True)
    static_path = terrain_dir / "tehsil_static.parquet" if args.tag else features / "tehsil_static.parquet"
    static.to_parquet(static_path, index=False)

    # ---- village exposure -----------------------------------------------------------------
    inv = ~transform
    out_rows = []
    with (data / "reference" / "gazetteer.csv").open(encoding="utf-8", newline="") as fh:
        for place in csv.DictReader(fh):
            if place["feature"] not in POPULATED or not place["tehsil_id"]:
                continue
            col, row = inv * (float(place["lon"]), float(place["lat"]))
            r, c = int(math.floor(row)), int(math.floor(col))
            if not (0 <= r < height and 0 <= c < width):
                continue
            h = float(hand[r, c])
            if not math.isfinite(h):
                continue
            sr, sc = int(iy[r, c]), int(ix[r, c])
            hmin = float(hand_min[r, c])
            up = float(upstream_km2[sr, sc])
            out_rows.append({
                "village_id": place["place_id"], "name": place["name"], "tehsil_id": place["tehsil_id"],
                "lat": place["lat"], "lon": place["lon"], "hand_m": round(h, 1),
                "hand_min_m": round(hmin, 1), "exposure_band": band(hmin, up),
                "dist_to_stream_m": round(float(dist[r, c])), "upstream_area_km2": round(up, 1),
            })
    exposure = pd.DataFrame(out_rows)
    exposure_path = terrain_dir / "village_exposure.csv" if args.tag else data / "reference" / "village_exposure.csv"
    exposure.to_csv(exposure_path, index=False)
    print(json.dumps({"tehsils": len(static), "villages": len(exposure),
                      "bands": exposure["exposure_band"].value_counts().to_dict()}, indent=2))
    return 0


def _as_raster(grid, mask: np.ndarray, like):
    from pysheds.view import Raster

    return Raster(mask, viewfinder=like.viewfinder)


def _census_by_tehsil(census: pd.DataFrame, data: Path) -> dict[str, float]:
    """2023 census population keyed by tehsil_id, matched by district and tehsil name."""

    from backend.app.geo.names import AdminNames

    names = AdminNames.from_dir(data / "reference")
    out: dict[str, float] = {}
    for _, r in census.iterrows():
        if pd.isna(r["pop_2023"]):
            continue
        district = names.resolve_district(str(r["district"]))
        matches = names.resolve_tehsil(str(r["tehsil"]), district)
        if district and matches:
            tehsil_id = matches[0].tehsil_id
            out[tehsil_id] = out.get(tehsil_id, 0.0) + float(r["pop_2023"])
    return out


if __name__ == "__main__":
    raise SystemExit(main())
