from pipelines.reference.census2023 import parse_rows


def _row(name, area=None, pop=None, urban=None, pop2017=None):
    row = [None] * 12
    row[0], row[1], row[2], row[8], row[10] = name, area, pop, urban, pop2017
    return row


def test_parse_rows_units_and_districts():
    rows = [
        _row("KHYBER PAKHTUNKHWA", 101741, 40856097),
        _row("BUNER DISTRICT", 1865, 1016869),
        _row("RURAL", None, 1016869),
        _row("CHAGHARZAI TEHSIL", 218, 125949, 0, 109291),
        _row("RURAL", None, 125949),
        _row("SOUTH WAZIRISTAN \nDISTRICT", 6620, 888675),
        _row("WANA TEHSIL", 2315, 184645, 0, 153156),
        _row("LOWER DIR DISTRICT", 1583, 1650183),
        _row("TEMERGARA SUB-DIVISION", 576, 596173, 8.03, 520985),
        _row(float("nan")),
    ]
    out = parse_rows(rows)
    assert [(r["district"], r["tehsil"], r["unit_type"]) for r in out] == [
        ("Buner", "Chagharzai", "tehsil"),
        ("South Waziristan", "Wana", "tehsil"),
        ("Lower Dir", "Temergara", "sub_division"),
    ]
    assert out[0]["pop_2023"] == 125949 and out[0]["pop_2017"] == 109291
    assert out[2]["urban_share"] == 0.0803
