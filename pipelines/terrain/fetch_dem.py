"""Download Copernicus DEM tiles (GLO-90 by default) and merge them into one GeoTIFF.

Source: Copernicus DEM on the AWS Open Data registry (public, no key).
Licence: © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018,
provided under COPERNICUS by the European Union and ESA; free use with attribution.

    python -m pipelines.terrain.fetch_dem                 # 90 m, in-scope tehsils
    python -m pipelines.terrain.fetch_dem --res 30 --bbox 72.0 34.6 72.9 35.9   # 30 m, Swat
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import httpx

from backend.app.config import get_settings

BUCKETS = {
    90: ("https://copernicus-dem-90m.s3.amazonaws.com", "Copernicus_DSM_COG_30"),
    30: ("https://copernicus-dem-30m.s3.amazonaws.com", "Copernicus_DSM_COG_10"),
}
DEFAULT_BBOX = (71.0, 34.0, 75.0, 36.0)  # lon_min, lat_min, lon_max, lat_max (in-scope tehsils + margin)


def tile_name(res: int, lat: int, lon: int) -> str:
    prefix = BUCKETS[res][1]
    ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
    ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
    return f"{prefix}_{ns}_00_{ew}_00_DEM"


def tiles_for_bbox(bbox: tuple[float, float, float, float]) -> list[tuple[int, int]]:
    lon0, lat0, lon1, lat1 = bbox
    return [(lat, lon) for lat in range(math.floor(lat0), math.ceil(lat1))
            for lon in range(math.floor(lon0), math.ceil(lon1))]


def download(res: int, bbox, out_dir: Path) -> list[Path]:
    base = BUCKETS[res][0]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        for lat, lon in tiles_for_bbox(bbox):
            name = tile_name(res, lat, lon)
            path = out_dir / f"{name}.tif"
            if not path.is_file():
                url = f"{base}/{name}/{name}.tif"
                response = client.get(url)
                if response.status_code == 404:
                    print(f"missing tile {name} (no land)")
                    continue
                response.raise_for_status()
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(response.content)
                tmp.replace(path)
                print(f"downloaded {name} ({len(response.content) / 1e6:.1f} MB)")
            paths.append(path)
    return paths


def merge(paths: list[Path], bbox, out_path: Path) -> Path:
    import rasterio
    from rasterio.merge import merge as rio_merge

    sources = [rasterio.open(p) for p in paths]
    try:
        mosaic, transform = rio_merge(sources, bounds=bbox)
        profile = sources[0].profile | {"height": mosaic.shape[1], "width": mosaic.shape[2],
                                        "transform": transform, "driver": "GTiff", "compress": "deflate",
                                        "tiled": True, "blockxsize": 512, "blockysize": 512}
        profile.pop("blocksize", None)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(mosaic)
    finally:
        for s in sources:
            s.close()
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--res", type=int, choices=[30, 90], default=90)
    parser.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX)
    args = parser.parse_args(argv)
    data = get_settings().data_dir
    tiles = download(args.res, tuple(args.bbox), data / "raw" / "dem" / f"glo{args.res}")
    out = merge(tiles, tuple(args.bbox), data / "interim" / "terrain" / f"dem_glo{args.res}.tif")
    print(f"merged {len(tiles)} tiles -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
