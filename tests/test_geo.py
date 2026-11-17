from shapely.geometry import box

from backend.app.contracts import TehsilRegion
from backend.app.geo import AdminNames, TehsilLocator, name_key


def test_name_key_spellings():
    assert name_key("Bala Kot") == name_key("Balakot") == name_key("BALAKOT Tehsil")
    assert name_key("Khwaza Khela") == name_key("Khwaza-Khela") == "khwazakhela"
    assert name_key("Lal Qila") == name_key("Lalqila")
    assert name_key("Dir (U)") == name_key("Dir Upper")
    assert name_key("Mingōra") == "mingora"
    assert name_key("District") == ""


def _names() -> AdminNames:
    districts = [("Upper Dir", "upper_dir"), ("Dir Upper", "upper_dir"), ("Swat", "swat"),
                 ("Battagram", "battagram"), ("Batagram", "battagram")]
    tehsils = [
        ("Matta Kharirai", "swat", "swat__matta_kharirai", "cod"),
        ("Matta Sebujni", "swat", "swat__matta_sebujni", "cod"),
        ("Matta", "swat", "swat__matta_kharirai", "census_hq_point"),
        ("Matta", "swat", "swat__matta_sebujni", "manual"),
        ("Khwaza Khela", "swat", "swat__khwaza_khela", "cod"),
        ("Dir", "upper_dir", "upper_dir__dir", "cod"),
        ("Unresolved", "swat", "", "census"),  # rows without a tehsil are ignored
    ]
    return AdminNames(districts, tehsils)


def test_resolve_district_exact_and_fuzzy():
    names = _names()
    assert names.resolve_district("UPPER DIR") == "upper_dir"
    assert names.resolve_district("Dir Upper") == "upper_dir"
    assert names.resolve_district("Batagram District") == "battagram"
    assert names.resolve_district("Swatt") == "swat"  # fuzzy
    assert names.resolve_district("Peshawar") is None
    assert names.resolve_district("") is None


def test_resolve_tehsil_exact_multi_and_fuzzy():
    names = _names()
    matta = names.resolve_tehsil("Matta", "swat")
    assert {m.tehsil_id for m in matta} == {"swat__matta_kharirai", "swat__matta_sebujni"}
    assert all(m.method == "exact" for m in matta)
    fuzzy = names.resolve_tehsil("Khawazakhela", "swat")
    assert fuzzy[0].tehsil_id == "swat__khwaza_khela" and fuzzy[0].method == "fuzzy"
    assert names.resolve_tehsil("Dir", "swat") == []  # wrong district
    assert names.resolve_tehsil("Unresolved") == []


def _region(tid: str) -> TehsilRegion:
    return TehsilRegion(tehsil_id=tid, district="D", tehsil=tid, centroid_lat=0.5, centroid_lon=0.5)


def test_locator_locate_and_nearest():
    locator = TehsilLocator([(_region("a__a"), box(0, 0, 1, 1)), (_region("b__b"), box(1, 0, 2, 1))])
    assert locator.locate(0.5, 0.5).tehsil_id == "a__a"
    assert locator.locate(0.5, 1.5).tehsil_id == "b__b"
    assert locator.locate(5, 5) is None
    assert locator.nearest(1.02, 0.5).tehsil_id == "a__a"  # about 2 km outside
    assert locator.nearest(2.0, 0.5) is None  # about 100 km away
    assert locator.get("b__b").tehsil == "b__b"
