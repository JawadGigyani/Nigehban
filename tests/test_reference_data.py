"""Checks on the committed reference files in data/reference/ (built in M4a)."""

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from backend.app.config.region import (
    CANDIDATE_BBOX,
    CANDIDATE_DISTRICTS,
    OUT_OF_SCOPE_DISTRICTS,
    REGION_BBOX,
)
from backend.app.contracts import TehsilRegion
from backend.app.geo import AdminNames, TehsilLocator

REF = Path(__file__).resolve().parents[1] / "data" / "reference"


def _csv(name):
    with (REF / name).open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def locator():
    return TehsilLocator.from_geojson(REF / "tehsils.geojson")


@pytest.fixture(scope="module")
def names():
    return AdminNames.from_dir(REF)


def test_tehsils_valid_unique_and_cover_every_district(locator):
    regions = locator.regions
    ids = [r.tehsil_id for r in regions]
    assert len(ids) == len(set(ids))
    per_district = Counter(r.tehsil_id.split("__")[0] for r in regions)
    for district in CANDIDATE_DISTRICTS + OUT_OF_SCOPE_DISTRICTS:
        assert per_district[district.slug] >= 1, district.slug
    in_scope = {r.tehsil_id.split("__")[0] for r in regions if r.in_scope}
    assert in_scope == {d.slug for d in CANDIDATE_DISTRICTS}
    assert all(r.is_ardc == r.tehsil_id.startswith("bajaur__") for r in regions)


def test_centroids_inside_region_boxes(locator):
    for r in locator.regions:
        box = CANDIDATE_BBOX if r.in_scope else REGION_BBOX
        assert box.contains(r.centroid_lat, r.centroid_lon), r.tehsil_id


@pytest.mark.parametrize("town,lat,lon,expected", [
    ("Mingora", 34.7717, 72.3602, "swat__babuzai"),
    ("Kalam", 35.4902, 72.5796, "swat__kalam"),
    ("Batkhela", 34.6178, 71.9708, "malakand__bat_khela"),
    ("Khar", 34.7350, 71.5250, "bajaur__khar"),
    ("Timergara", 34.8296, 71.8434, "lower_dir__timergara"),
    ("Daggar", 34.5110, 72.4700, "buner__daggar"),
    ("Alpuri", 34.9050, 72.6460, "shangla__alpuri"),
    ("Balakot", 34.5480, 73.3510, "mansehra__bala_kot"),
    ("Chitral", 35.8510, 71.7860, "lower_chitral__chitral"),
    ("Peshawar", 34.0151, 71.5249, None),
])
def test_known_towns_locate(locator, town, lat, lon, expected):
    found = locator.locate(lat, lon)
    assert (found.tehsil_id if found else None) == expected


def test_gazetteer_covers_every_tehsil_and_is_consistent(locator):
    rows = _csv("gazetteer.csv")
    ids = {r.tehsil_id for r in locator.regions}
    counts = Counter(r["tehsil_id"] for r in rows)
    assert set(counts) == ids
    assert min(counts.values()) >= 1
    assert len({r["place_id"] for r in rows}) == len(rows)
    for r in rows[:: max(1, len(rows) // 200)]:  # spot-check a sample
        assert locator.locate(float(r["lat"]), float(r["lon"])).tehsil_id == r["tehsil_id"]


# District spellings seen in the PDMA report tables (sample of 400 reports).
PDMA_DISTRICTS = [
    "Buner", "Upper Dir", "Shangla", "Swat", "Dera Ismail Khan", "Bajaur", "Upper Chitral",
    "Abbottabad", "South Waziristan Lower", "Mardan", "Lower Dir", "Malakand", "Mansehra",
    "Lower Kohistan", "Khyber", "Lower Chitral", "Upper Kohistan", "Nowshera", "Swabi",
    "Charsadda", "Mohmand", "Karak", "North Waziristan", "Hangu", "Peshawar", "Battagram",
    "Kurram", "Tank", "Haripur", "Kohistan Kolai Pallas", "Kohat", "Orakzai", "Lakki Marwat",
    "Torghar", "Bannu",
]


def test_every_pdma_district_spelling_resolves(names):
    for name in PDMA_DISTRICTS:
        assert names.resolve_district(name) is not None, name
    assert names.resolve_district("Batagram") == "battagram"
    assert names.resolve_district("Chitral Upper") == "upper_chitral"


def test_aliases_point_to_real_tehsils(locator):
    ids = {r.tehsil_id for r in locator.regions}
    for file in ("tehsil_aliases.csv", "manual_aliases.csv"):
        for row in _csv(file):
            assert row["tehsil_id"] in ids, (file, row)


def test_census_names_resolve_except_known_open(names):
    known_open = {("buner", "Chagharzai"), ("buner", "Gadezai")}
    open_now = {(u["district_slug"], u["census_name"])
                for u in json.loads((REF / "_alias_unresolved.json").read_text(encoding="utf-8"))}
    assert open_now <= known_open
    assert {m.tehsil_id for m in names.resolve_tehsil("Matta", "swat")} == {
        "swat__matta_kharirai", "swat__matta_sebujni"}
    assert {m.tehsil_id for m in names.resolve_tehsil("Behrain", "swat")} == {
        "swat__bahrain", "swat__kalam"}
    assert names.resolve_tehsil("Swat Rani Zai", "malakand")[0].tehsil_id == "malakand__bat_khela"


def test_geojson_properties_match_contract():
    data = json.loads((REF / "tehsils.geojson").read_text(encoding="utf-8"))
    for feature in data["features"]:
        TehsilRegion.model_validate(feature["properties"])
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
