"""M3 terrain and M4b facilities: pure helpers (no DEM download needed)."""

from __future__ import annotations

import numpy as np
import pytest
from rasterio.transform import from_origin

from backend.app.contracts import VillageExposure
from pipelines.reference.build_facilities import classify
from pipelines.terrain.build_terrain import band, cell_sizes_m, compute_slope
from pipelines.terrain.fetch_dem import tile_name, tiles_for_bbox


def test_bands_use_nearby_low_ground_and_river_size():
    assert band(1.0, 500) == "high" and band(4.9, 50) == "high"
    assert band(1.0, 20) == "medium"  # small stream: medium at most
    assert band(6.0, 500) == "medium"
    assert band(8.0, 500) == "low" and band(30, 500) == "low"


def test_cell_sizes_shrink_with_latitude():
    transform = from_origin(72.0, 36.0, 1 / 1200, 1 / 1200)  # 3 arc-seconds
    dx, dy = cell_sizes_m(transform, 2400)
    assert dy == pytest.approx(92.8, abs=0.5)
    assert 74 < dx[0] < dx[-1] < 77  # row 0 is the north edge (36° N), where cells are narrower


def test_slope_of_a_ramp():
    dem = np.tile(np.arange(10, dtype="float32") * 10, (5, 1))  # rises 10 m per 10 m cell eastward
    slope = compute_slope(dem, np.full(5, 10.0, dtype="float32"), 10.0)
    assert slope[2, 5] == pytest.approx(45.0, abs=0.01)


def test_dem_tiles():
    assert tile_name(90, 34, 72) == "Copernicus_DSM_COG_30_N34_00_E072_00_DEM"
    assert tile_name(30, 35, 71) == "Copernicus_DSM_COG_10_N35_00_E071_00_DEM"
    assert len(tiles_for_bbox((71.0, 34.0, 75.0, 36.0))) == 8


@pytest.mark.parametrize("tags,kind", [
    ({"amenity": "school", "name": "Govt High School"}, "shelter"),
    ({"office": "government"}, "shelter"),
    ({"amenity": "hospital"}, "health"),
    ({"amenity": "fire_station", "name": "Rescue 1122 Mingora"}, "rescue_1122"),
    ({"emergency": "ambulance_station"}, "rescue_1122"),
    ({"amenity": "police"}, "police"),
    ({"amenity": "restaurant"}, None),
])
def test_facility_classification(tags, kind):
    assert classify(tags) == kind


def test_village_exposure_contract():
    VillageExposure(village_id="gn:1", hand_m=1.2, exposure_band="high", dist_to_stream_m=80,
                    upstream_area_km2=520.0, tehsil_id="swat__babuzai")
