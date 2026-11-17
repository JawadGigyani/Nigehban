"""Build tehsil reference layers from OCHA COD-AB Pakistan (adm3).

Source: https://data.humdata.org/dataset/cod-ab-pak (pak_admin_boundaries.shp.zip),
licence CC BY-IGO, boundaries valid on 2022-09-09.

Writes:
- `data/reference/tehsils.geojson`: polygons for the candidate districts
  (in_scope = true) and the out-of-scope districts kept for geocoding, such as
  Chitral (in_scope = false). Geometry is lightly simplified (about 50 m).
- `data/reference/kp_admin.csv`: every KP district and tehsil name with
  P-codes, so district names anywhere in KP can be recognised.

Usage: python -m pipelines.reference.build_tehsils
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import geopandas as gpd

from backend.app.config import get_settings
from backend.app.config.region import (
    CANDIDATE_DISTRICTS,
    OUT_OF_SCOPE_DISTRICTS,
    make_tehsil_id,
    slugify,
)
from backend.app.contracts import TehsilRegion
from pipelines.reference.admin_names import canonical_district, district_slug

UTM_43N = "EPSG:32643"
SIMPLIFY_DEG = 0.0005  # about 50 m


def load_kp(shp: Path) -> gpd.GeoDataFrame:
    frame = gpd.read_file(shp)
    kp = frame[frame["adm1_name"].str.contains("Khyber", case=False)].copy()
    if kp.crs is None or kp.crs.to_epsg() != 4326:
        kp = kp.to_crs(4326)
    kp["district_name"] = kp["adm2_name"].map(canonical_district)
    kp["district_slug"] = kp["district_name"].map(district_slug)
    kp["tehsil_id"] = [
        make_tehsil_id(d, slugify(t)) for d, t in zip(kp["district_slug"], kp["adm3_name"])
    ]
    return kp


def build(shp: Path, out_dir: Path) -> dict:
    kp = load_kp(shp)
    if kp["tehsil_id"].duplicated().any():
        dupes = kp.loc[kp["tehsil_id"].duplicated(), "tehsil_id"].tolist()
        raise ValueError(f"Duplicate tehsil ids: {dupes}")

    in_scope = {d.slug: d for d in CANDIDATE_DISTRICTS}
    kept = {**in_scope, **{d.slug: d for d in OUT_OF_SCOPE_DISTRICTS}}
    missing = set(kept) - set(kp["district_slug"])
    if missing:
        raise ValueError(f"Districts not found in COD-AB: {sorted(missing)}")

    region = kp[kp["district_slug"].isin(kept)].copy()
    projected = region.to_crs(UTM_43N)
    centroids = projected.geometry.centroid.to_crs(4326)
    region["area_km2"] = (projected.geometry.area / 1e6).round(1)
    region["geometry"] = region.geometry.simplify(SIMPLIFY_DEG, preserve_topology=True)

    features = []
    for (_, row), centroid in zip(region.iterrows(), centroids):
        district = kept[row["district_slug"]]
        props = TehsilRegion(
            tehsil_id=row["tehsil_id"],
            district=district.name,
            tehsil=row["adm3_name"],
            centroid_lat=round(centroid.y, 5),
            centroid_lon=round(centroid.x, 5),
            is_ardc=district.is_ardc,
            pcode=row["adm3_pcode"],
            area_km2=float(row["area_km2"]),
            in_scope=district.slug in in_scope,
        )
        features.append({
            "type": "Feature",
            "properties": props.model_dump(mode="json"),
            "geometry": json.loads(gpd.GeoSeries([row.geometry]).to_json())["features"][0]["geometry"],
        })
    features.sort(key=lambda f: f["properties"]["tehsil_id"])

    out_dir.mkdir(parents=True, exist_ok=True)
    geojson = {
        "type": "FeatureCollection",
        "name": "tehsils",
        "source": "OCHA COD-AB Pakistan adm3 (valid 2022-09-09), CC BY-IGO",
        "features": features,
    }
    (out_dir / "tehsils.geojson").write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")

    with (out_dir / "kp_admin.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["district", "district_cod", "district_slug", "district_pcode",
                         "tehsil", "tehsil_id", "tehsil_pcode", "in_region"])
        for _, row in kp.sort_values(["district_slug", "adm3_name"]).iterrows():
            writer.writerow([row["district_name"], row["adm2_name"], row["district_slug"],
                             row["adm2_pcode"], row["adm3_name"], row["tehsil_id"],
                             row["adm3_pcode"], row["district_slug"] in kept])

    bounds = region.total_bounds  # minx, miny, maxx, maxy
    return {
        "kp_tehsils": len(kp),
        "region_tehsils": len(features),
        "in_scope_tehsils": sum(f["properties"]["in_scope"] for f in features),
        "bounds": {"south": bounds[1], "west": bounds[0], "north": bounds[3], "east": bounds[2]},
    }


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--shp", type=Path,
                        default=settings.data_dir / "raw" / "boundaries" / "cod" / "pak_admin3.shp")
    parser.add_argument("--out-dir", type=Path, default=settings.data_dir / "reference")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.shp, args.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
