"""Tests for M1: report parsing, name redaction, task building, geocoding, de-duplication.

All report text here is made up; the names are invented placeholders.
"""

import datetime as dt
from pathlib import Path

import pytest

from backend.app.contracts import EventType, GeocodeLevel
from backend.app.geo import AdminNames
from pipelines.pdma.build_events import Draft, Geocoder, _parse_date, deduplicate, to_events
from pipelines.pdma.extract import ExtractionResult, Task, build_tasks, build_user_prompt, categorise
from pipelines.pdma.parse_dsr import SummaryRow, parse_report
from pipelines.pdma.redact import has_name_markers, redact_names, safe_redact

REF = Path(__file__).resolve().parents[1] / "data" / "reference"

NUMS = ["1", "0", "0", "1", "0", "0", "0", "0", "0", "2", "3", "5", "0", "0", "0", "0", "0", "0"]
HEADER = ("<tr><td>DISTRICT</td><td>NATURE OF INCIDENT</td><td>CAUSE OF INCIDENT</td>"
          "<td>HUMAN LOSSES/ INJURIES</td><td>CATTLE PERISHED</td><td>INFRASTRUCTURE DAMAGES</td></tr>"
          "<tr><td></td><td></td><td></td><td>DEATH</td><td>INJURED</td></tr>")


def _row(district, nature, cause, nums=NUMS):
    return "<tr>" + "".join(f"<td>{c}</td>" for c in [district, nature, cause, *nums]) + "</tr>"


REPORT_HTML = f"""<html><body>
<table><tr><td>PDMA</td></tr><tr><td>Date: 26/08/2022</td></tr></table>
<table>{HEADER}
{_row("Swat", "Heavy Rain", "Flash Flood")}
{_row("Karak", "Electrocution", "Electric Shock")}
{_row("Shangla", "Heavy Rain", "Roof Collapse")}
<tr><td>Total(s)</td><td></td><td></td>{"".join(f"<td>{n}</td>" for n in NUMS)}</tr>
</table>
<table><tr><td>DISTRICT</td><td>DETAIL OF INCIDENT</td><td>RESPONSE</td><td>SOURCE</td></tr>
<tr><td>Swat</td><td>On 25-08-2022 a flash flood hit Madyan. Resultantly, one Mr. Testname Alpha s/o Testname Beta r/o Madyan drowned in Swat river.</td><td></td><td>DC Swat</td></tr>
<tr><td>Karak</td><td>A child Testname Gamma s/o Testname Delta died of electric shock.</td><td></td><td>DC Karak</td></tr>
<tr><td>Shangla</td><td>Roof of a house collapsed in Alpuri due to rain.</td><td></td><td>DC Shangla</td></tr>
</table></body></html>"""


def test_parse_report_tables():
    report = parse_report(REPORT_HTML, dsrid=2601)
    assert report.report_date == dt.date(2022, 8, 26)
    assert [r.district_raw for r in report.summary] == ["Swat", "Karak", "Shangla"]
    swat = report.summary[0]
    assert (swat.cause, swat.deaths, swat.injured, swat.houses_damaged) == ("Flash Flood", 1, 0, 5)
    assert "Madyan" in report.details["Swat"][0]


@pytest.mark.parametrize("text", [
    "one Mr. Testname Alpha s/o Testname Beta r/o Madyan drowned",
    "a child Testname Gamma s/o Testname Delta r/o Kalam died",
    "two persons namely Testname Aqib (age 20 years) s/o Testname Bilal, Testname Zahid (age 22 years) s/o Testname Fazal drowned",
    "Mst. Testname Five w/o Testname Six aged 40 years drowned",
    "1. Daughter of Testname Seven age 12 years. 2. W/o Testname Eight age 40 years.",
    "the house of Testname Nine resident of Bahrain collapsed",
])
def test_redaction_removes_names(text):
    out = safe_redact(text)
    assert "Testname" not in out
    assert not has_name_markers(out)


def test_redaction_keeps_places():
    out = redact_names("Mr. Testname Alpha s/o Testname Beta r/o Madyan drowned in Swat river near Fizagat.")
    assert "resident of Madyan" in out and "Swat river" in out and "Fizagat" in out
    assert redact_names("A flash flood hit Madyan and Bahrain bazaar.") == "A flash flood hit Madyan and Bahrain bazaar."


def test_categorise_rows():
    row = lambda nature, cause: SummaryRow("Swat", nature, cause, 0, 0, 0)
    assert categorise(row("Heavy Rain", "Flash Flood"), []) == "flood_like"
    assert categorise(row("Drowning", "Drowning"), ["drowned in a stream"]) == "flood_like"
    assert categorise(row("Heavy Rain", "Land Sliding"), []) == "landslide"
    assert categorise(row("Heavy Rain", "Roof Collapse"), []) == "collapse"
    assert categorise(row("Electrocution", "Electric Shock"), []) == "unrelated"


def test_build_tasks_only_flood_rows_and_redacted():
    names = AdminNames.from_dir(REF)
    tasks, groups = build_tasks([parse_report(REPORT_HTML, 2601)], names)
    assert groups == {"flood_like": 1, "unrelated": 1, "collapse": 1}
    (task,) = tasks
    assert task.district_slug == "swat"
    assert "Testname" not in task.text and "Madyan" in task.text
    prompt = build_user_prompt(task)
    assert "Report date: 2022-08-26" in prompt and "Testname" not in prompt
    assert task.cache_name.startswith("02601_swat_")


def test_llm_form_has_no_name_fields():
    fields = set(ExtractionResult.model_fields) | set(
        ExtractionResult.model_fields["incidents"].annotation.__args__[0].model_fields)
    assert not {"name", "names", "person", "victim", "victims"} & fields


def test_parse_date_rules():
    report = dt.date(2022, 8, 26)
    assert _parse_date("2022-08-25", report) == (dt.date(2022, 8, 25), True)
    assert _parse_date("2021-08-25", report) == (report, False)  # too old
    assert _parse_date(None, report) == (report, False)
    assert _parse_date("bad", report) == (report, False)


@pytest.fixture(scope="module")
def geocoder():
    return Geocoder(REF)


def _draft(**kw):
    base = dict(date=dt.date(2022, 8, 25), report_date=dt.date(2022, 8, 26), district="Swat",
                district_slug="swat", event_type=EventType.FLASH_FLOOD, source_dsrid=1, confidence=0.9)
    base.update(kw)
    return Draft(**base)


def test_geocode_village_tehsil_and_district(geocoder):
    village = geocoder.geocode(_draft(), None, ["Mingora"])
    assert village.level is GeocodeLevel.VILLAGE and village.tehsil_id == "swat__babuzai"
    tehsil = geocoder.geocode(_draft(), "Tehsil Matta", ["Notaplace Xyz"])
    assert tehsil.level is GeocodeLevel.TEHSIL and tehsil.tehsil_id.startswith("swat__matta")
    as_tehsil = geocoder.geocode(_draft(), None, ["Kalam"])
    assert as_tehsil.tehsil_id == "swat__kalam"
    nothing = geocoder.geocode(_draft(), None, ["Notaplace Xyz"])
    assert nothing.level is GeocodeLevel.DISTRICT and nothing.tehsil_id is None
    outside = geocoder.geocode(_draft(district="Peshawar", district_slug="peshawar"), None, ["Mingora"])
    assert outside.level is GeocodeLevel.DISTRICT  # no gazetteer outside the region


def test_geocode_drops_village_conflicting_with_tehsil(geocoder):
    # Mingora is in Babuzai; if the report says Tehsil Kalam, keep the tehsil, drop the village.
    d = geocoder.geocode(_draft(), "Kalam", ["Mingora"])
    assert d.tehsil_id == "swat__kalam" and d.village is None


def test_deduplicate_merges_followups_and_folds_district_level():
    a = _draft(tehsil_id="swat__bahrain", level=GeocodeLevel.TEHSIL, deaths=2, dsrids={1})
    b = _draft(date=dt.date(2022, 8, 26), tehsil_id="swat__bahrain", level=GeocodeLevel.VILLAGE,
               village="Madyan", deaths=5, source_dsrid=2, dsrids={2})
    c = _draft(date=dt.date(2022, 8, 30), tehsil_id="swat__bahrain", level=GeocodeLevel.TEHSIL, dsrids={3})
    district_only = _draft(date=dt.date(2022, 8, 26), dsrids={4})
    collapse = _draft(event_type=EventType.ROOF_COLLAPSE, dsrids={5})
    out = deduplicate([a, b, c, district_only, collapse])
    positives = [d for d in out if d.event_type is not EventType.ROOF_COLLAPSE]
    assert len(positives) == 2  # a+b merged, c separate, district-level folded in
    merged = positives[0]
    assert merged.date == dt.date(2022, 8, 25) and merged.village == "Madyan"
    assert merged.deaths == 5 and merged.n_reports == 2
    assert any(d.event_type is EventType.ROOF_COLLAPSE for d in out)
    events = to_events(out)
    assert len({e.event_id for e in events}) == len(events)


def test_phrases_longest_first():
    assert Geocoder.phrases("Bhai Kalay Daggar") == [
        "Bhai Kalay Daggar", "Bhai Kalay", "Kalay Daggar", "Bhai", "Kalay", "Daggar"]


def test_village_inside_combined_string_and_generic_words(geocoder):
    # "<village> <tehsil>" in one string: the tehsil is used as a hint, the village found.
    d = geocoder.geocode(_draft(), None, ["Mingora Babuzai"])
    assert d.level is GeocodeLevel.VILLAGE and d.tehsil_id == "swat__babuzai"
    # A sub-phrase made only of generic words ("Banda") must not match a place.
    assert geocoder._village("malakand", "Notaplace Banda", None) is None


def test_tehsil_spelling_variants_within_district(geocoder):
    assert geocoder._tehsil("shangla", "Besham") == "shangla__bisham"
    assert geocoder._tehsil("bajaur", "Wara Mamund") == "bajaur__mamund"
    assert geocoder._tehsil("buner", "Khadu Khel") == "buner__khado_khel"


@pytest.mark.parametrize("text", [
    "Houses Damaged 1. Abdul Testaziz resident of Garam Chashma 2. Syed Testshah resident of Garam Chashma",
    "Crops Damaged 1. Muhammad Testnabi 2. Testnazir Khan 3. Fazal Testuddin",
    "the other Testijaz Khan (Age 13 years) drowned in the drain",
    "On 15-08-2024, due to heavy rain, Testmanzoor Khan was flooded away.",
    "Injured 3. Testmuddasir Ahmad s/0 Testmuhtiyar Ahmad 4. Testfour",
    "15. Atta Ullahs/o Akram Testkhan (Hair dresser shop)",
    "Two rooms of Mr.Abdus Testsatar Slo Mubarak Testshah Rio Batara collapsed.",
    "Boundary wall of a house owned by Testhashim Ali in Paharpur",
    "standing crops of [person] and Sher Testnazim were damaged",
    "died sons of Sher Testbadshah, while 03 women got injured",
    "40. Testaisha Bi Bi Widow of Muhammad Testqadir (Two Rooms)",
    "Testhastam resident of Dorma Kore Loe Shilman (Boundary wall)",
])
def test_redaction_removes_other_name_forms(text):
    out = safe_redact(text)
    assert "Test" not in out, out
    assert not has_name_markers(out)


def test_redaction_keeps_known_and_likely_places():
    from pipelines.pdma.extract import load_place_keys
    from pipelines.pdma.redact import place_checker
    from backend.app.geo import name_key

    is_place = place_checker(load_place_keys(REF)["swat"], name_key)
    text = "flash floods in: 1. Saidu Sharif 2. Faiz Abad; resident of Umar Khel Kacha near Kernal Sher Khan Kili"
    out = safe_redact(text, is_place)
    for place in ("Saidu Sharif", "Faiz Abad", "Umar Khel", "Kernal Sher Khan Kili"):
        assert place in out
    assert safe_redact("In Mir Khan Arang Tehsil Uthmankhel during rain") == \
        "In Mir Khan Arang Tehsil Uthmankhel during rain"


def test_apply_corrections(tmp_path):
    from collections import Counter

    from backend.app.contracts import FloodEvent
    from pipelines.pdma.build_events import apply_corrections

    event = FloodEvent(event_id="evt_x", date="2025-06-28", report_date="2025-06-28",
                       district="Charsadda", geocode_level="district", event_type="flood",
                       source_dsrid=1, extract_confidence=0.9)
    path = tmp_path / "c.csv"
    path.write_text("event_id,field,value,reason\n"
                    "evt_x,event_type,other,not a flood\n"
                    "evt_x,date,2025-06-27,body found next day\n"
                    "evt_missing,district,Swat,unknown id\n", encoding="utf-8")
    stats = Counter()
    (fixed,) = apply_corrections([event], path, stats)
    assert not fixed.is_positive and str(fixed.date) == "2025-06-27"
    assert stats["corrected_events"] == 1
