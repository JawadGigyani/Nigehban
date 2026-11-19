"""M2 hydromet: grid weights, pacing, cache, daily and tehsil features (offline)."""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import httpx
import pandas as pd
import pytest
from shapely.geometry import box

from backend.app.contracts import HydrometDaily
from backend.app.hydromet.client import (
    DailyLimitReached,
    OpenMeteoClient,
    RatePacer,
    request_weight,
)
from backend.app.hydromet.features import (
    add_rolling,
    build_climatology,
    cells_to_tehsils,
    finalise,
    forecast_rolling,
    hourly_to_daily,
)
from backend.app.hydromet.grid import Cell, CellWeight, build_grid, cells_for_geometry, check_weights
from backend.app.hydromet.service import live_tehsil_features

ROOT = Path(__file__).resolve().parents[1]
D = dt.date


def test_cells_cover_polygon_and_weights_sum_to_one():
    cells = cells_for_geometry(box(72.1, 34.6, 72.6, 34.9))
    assert abs(sum(w for _, w in cells) - 1) < 1e-9
    assert {c.key for c, _ in cells} >= {"34.75,72.25", "34.75,72.50"}
    tiny = cells_for_geometry(box(72.20, 34.70, 72.22, 34.72))
    assert [(c.key, round(w, 6)) for c, w in tiny] == [("34.75,72.25", 1.0)]


def test_reference_grid_covers_every_tehsil():
    rows = build_grid(ROOT / "data" / "reference" / "tehsils.geojson")
    check_weights(rows)
    assert len({r.tehsil_id for r in rows}) == 53
    committed = (ROOT / "data" / "reference" / "tehsil_grid.csv").read_text(encoding="utf-8")
    assert committed.count("\n") == len(rows) + 1


def test_request_weight():
    assert request_weight(1, 4, 14) == 1
    assert request_weight(20, 15, 28) == pytest.approx(20 * 1.5 * 2)


def test_pacer_waits_when_minute_budget_is_used():
    now = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    pacer = RatePacer(per_minute=10, per_hour=100, per_day=1000, clock=lambda: now[0], sleep=sleep)
    pacer.acquire(6)
    pacer.acquire(6)  # over the minute budget: must wait about 60 s
    assert slept and sum(slept) >= 59
    with pytest.raises(DailyLimitReached):
        RatePacer(per_day=5).acquire(6)


def _payload(days: int, rain_per_hour: float, start="2025-08-14", suffix=""):
    times = pd.date_range(start, periods=24 * days, freq="h").strftime("%Y-%m-%dT%H:%M").tolist()
    return {"hourly": {"time": times,
                       f"precipitation{suffix}": [rain_per_hour] * len(times),
                       f"temperature_2m{suffix}": list(range(len(times))),
                       f"soil_moisture_0_to_7cm{suffix}": [0.3] * len(times)}}


def test_hourly_to_daily_sums_local_days_and_handles_model_suffix():
    daily = hourly_to_daily(_payload(2, 0.5, suffix="_ecmwf_ifs025"), "34.75,72.50", suffix="ecmwf_ifs025")
    assert list(daily["precip_sum"]) == [12.0, 12.0]
    assert list(daily["precip_max_1h"]) == [0.5, 0.5]
    assert list(daily["t2m_max"]) == [23, 47]
    assert daily["soil_moisture_0_7"].iloc[0] == pytest.approx(0.3)


def test_cells_to_tehsils_weighted_mean_and_cell_max():
    grid = [CellWeight("t1", Cell(34.75, 72.25), 0.25), CellWeight("t1", Cell(34.75, 72.5), 0.75)]
    cell_daily = pd.DataFrame({"cell": ["34.75,72.25", "34.75,72.50"], "date": [D(2025, 8, 15)] * 2,
                               "precip_sum": [40.0, 0.0], "precip_max_1h": [9.0, 0.0]})
    out = cells_to_tehsils(cell_daily, grid)
    row = out.iloc[0]
    assert row["precip_sum"] == pytest.approx(10.0)
    assert row["precip_cell_max"] == 40.0 and row["precip_max_1h"] == 9.0


def test_add_rolling_windows():
    frame = pd.DataFrame({"tehsil_id": "t1", "date": [D(2025, 8, 1) + dt.timedelta(days=i) for i in range(10)],
                          "precip_sum": [float(i) for i in range(10)]})
    out = add_rolling(frame).set_index("date")
    assert out.loc[D(2025, 8, 3), "precip_3d"] == 0 + 1 + 2
    assert pd.isna(out.loc[D(2025, 8, 7), "precip_7d_antecedent"])
    assert out.loc[D(2025, 8, 8), "precip_7d_antecedent"] == sum(range(7))


def test_forecast_rolling_uses_only_information_known_at_issue():
    analysis = pd.DataFrame({"tehsil_id": "t1", "date": [D(2025, 8, d) for d in range(1, 16)],
                             "precip_sum": 1.0})
    # Issued on 14 Aug: lead 0 = 14th (5 mm), lead 1 = 15th (20 mm).
    forecast = pd.DataFrame({"tehsil_id": "t1", "model": "ecmwf",
                             "date": [D(2025, 8, 14), D(2025, 8, 15)], "lead_days": [0, 1],
                             "precip_sum": [5.0, 20.0]})
    out = forecast_rolling(analysis, forecast).set_index("lead_days")
    assert out.loc[1, "precip_3d"] == 20 + 5 + 1  # 15th fc, 14th fc (same issue), 13th analysis
    assert out.loc[1, "precip_7d_antecedent"] == 5 + 6 * 1


def test_climatology_and_finalise_match_contract():
    dates = [D(y, 8, 1) + dt.timedelta(days=i) for y in (2023, 2024) for i in range(40)]
    era5 = pd.DataFrame({"tehsil_id": "t1", "date": dates, "precip_sum": 2.0, "t2m_max": 30.0})
    clim = build_climatology(era5)
    assert (clim["t2m_clim"] == 30.0).all()
    era5["model"], era5["lead_days"] = "era5", 0
    out = finalise(add_rolling(era5))
    HydrometDaily.model_validate(json.loads(out.iloc[10].to_json(date_format="iso"))
                                 | {"date": str(out.iloc[10]["date"])})


def test_client_caches_and_stops_on_daily_limit(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        if "daily_limit" in str(request.url):
            return httpx.Response(429, json={"error": True, "reason": "Daily API request limit exceeded."})
        return httpx.Response(200, json={"hourly": {"time": []}})

    client = OpenMeteoClient(tmp_path, http=httpx.Client(transport=httpx.MockTransport(handler)))
    params = {"latitude": "34.75", "longitude": "72.50"}
    assert client.get("https://x.test/a", params, weight=1) == [{"hourly": {"time": []}}]
    client.get("https://x.test/a", params, weight=1)
    assert len(calls) == 1  # second call came from the cache
    with pytest.raises(DailyLimitReached):
        client.get("https://x.test/daily_limit", params, weight=1)


def test_live_features_rows_for_each_model_and_lead():
    grid = [CellWeight("t1", Cell(34.75, 72.5), 1.0)]
    issue = D(2026, 7, 10)
    rows = []
    for model in ("ecmwf", "gfs", "icon"):
        for k in range(-7, 4):
            rows.append({"cell": "34.75,72.50", "date": issue + dt.timedelta(days=k), "model": model,
                         "precip_sum": 2.0, "precip_max_1h": 1.0, "t2m_max": 30.0,
                         "soil_moisture_0_7": 0.3 if model == "ecmwf" else None,
                         "soil_moisture_7_28": 0.32 if model == "ecmwf" else None})
    out = live_tehsil_features(pd.DataFrame(rows), grid, issue)
    assert len(out) == 12 and set(out["lead_days"]) == {0, 1, 2, 3}
    assert out["precip_7d_antecedent"].eq(14.0).all()
    assert out["soil_moisture_0_7"].eq(0.3).all()  # GFS/ICON borrow ECMWF soil moisture


@pytest.mark.live
def test_live_call_under_30_seconds(tmp_path):
    from backend.app.hydromet import HydrometService, load_grid

    grid = load_grid(ROOT / "data" / "reference" / "tehsil_grid.csv")
    service = HydrometService(OpenMeteoClient(tmp_path), grid)
    started = time.time()
    out = service.live_features()
    assert time.time() - started < 30
    assert out["tehsil_id"].nunique() == 53 and len(out) == 53 * 12


def test_pacer_remembers_usage_across_restarts(tmp_path):
    state = tmp_path / "pacer.json"
    RatePacer(per_day=10, state_path=state).acquire(6)
    with pytest.raises(DailyLimitReached):
        RatePacer(per_day=10, state_path=state).acquire(6)
