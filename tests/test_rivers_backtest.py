"""M6 river flag and M7 backtest helpers."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.app.contracts import RiverThresholds
from backend.app.hydromet.rivers import RiverMonitor, RiverPoint, RiverReading, return_period_reached
from pipelines.backtest.run import caught_lead
from pipelines.rivers.build_thresholds import return_levels, scan_cells

ROOT = Path(__file__).resolve().parents[1]
Q = {2: 100.0, 5: 200.0, 10: 300.0, 20: 400.0}


def test_return_period_reached():
    assert return_period_reached(50, Q) == 0
    assert return_period_reached(100, Q) == 2
    assert return_period_reached(250, Q) == 5
    assert return_period_reached(1000, Q) == 20


def test_tehsil_flags_use_flag_level_and_keep_the_highest():
    points = [RiverPoint("a", "A", 34.7, 72.3, Q, ("swat__babuzai", "swat__kabal")),
              RiverPoint("b", "B", 34.6, 72.0, Q, ("swat__kabal",))]
    monitor = RiverMonitor(points, client=None, flag_return_period=5)
    d = dt.date(2025, 8, 15)
    readings = [RiverReading("a", "A", d, 150, 2), RiverReading("b", "B", d, 350, 10),
                RiverReading("a", "A", d + dt.timedelta(days=1), 250, 5)]
    flags = monitor.tehsil_flags(readings)
    assert ("swat__babuzai", d) not in flags  # 2-year flow is below the flag level
    assert flags[("swat__kabal", d)].point_id == "b"
    assert flags[("swat__babuzai", d + dt.timedelta(days=1))].return_period == 5


def test_scan_cells_and_gumbel_levels():
    cells = scan_cells(34.765, 72.375)
    assert len(cells) == 25 and (34.765, 72.375) in cells
    rng = np.random.default_rng(1)
    peaks = pd.Series(rng.gumbel(500, 120, 29))
    levels = return_levels(peaks)
    assert levels[2] < levels[5] < levels[10] < levels[20]
    assert 450 < levels[2] < 600


def test_caught_lead_takes_the_longest_lead():
    d = dt.date(2025, 7, 10)
    events = pd.DataFrame({"tehsil_id": ["t1", "t2"], "date": [d, d]})
    alerts = {1: {("t1", d)}, 2: {("t1", d - dt.timedelta(days=1))}, 3: set()}
    assert caught_lead(events, alerts) == [2, 0]


def test_committed_river_thresholds_are_valid():
    path = ROOT / "data" / "reference" / "river_points_thresholds.json"
    if not path.is_file():
        pytest.skip("river thresholds not built yet")
    result = RiverThresholds.model_validate(json.loads(path.read_text(encoding="utf-8")))
    points = pd.read_csv(ROOT / "data" / "reference" / "river_points.csv")
    assert {p.point_id for p in result.points} == set(points["point_id"])
    for p in result.points:
        assert p.q2 < p.q5 < p.q10 < p.q20 and p.years_used >= 25
