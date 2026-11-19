"""River flag from GloFAS discharge at the main river points (M6).

Each river point has a main-channel cell and return levels (q2, q5, q10, q20)
from `data/reference/river_points_thresholds.json`, and the tehsils it serves
(`river_points.csv`). A tehsil gets `glofas_flag` on a day when any of its
points is forecast at or above the flag level (default: the 5-year flow).

The flag is a second signal next to the rain model: it catches river floods
from rain far upstream, which the tehsil's own rain does not show. It never
changes the model's risk level; the alert rules use "high or above, or flag".
Archived GloFAS forecasts are not available through Open-Meteo, so replays and
the backtest use the GloFAS reanalysis (what the river actually did).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.app.hydromet.client import OpenMeteoClient

RETURN_PERIODS = (2, 5, 10, 20)


@dataclass(frozen=True)
class RiverPoint:
    point_id: str
    name: str
    lat: float
    lon: float
    q: dict[int, float]
    tehsils: tuple[str, ...]


@dataclass(frozen=True)
class RiverReading:
    point_id: str
    name: str
    date: dt.date
    discharge: float
    return_period: int  # largest return period reached (0 = below the 2-year flow)


def return_period_reached(discharge: float, q: dict[int, float]) -> int:
    reached = 0
    for t in RETURN_PERIODS:
        if discharge >= q[t]:
            reached = t
    return reached


class RiverMonitor:
    def __init__(self, points: list[RiverPoint], client: OpenMeteoClient, flag_return_period: int = 5) -> None:
        self.points = points
        self.client = client
        self.flag_return_period = flag_return_period

    @classmethod
    def from_data_dir(cls, data_dir: Path, client: OpenMeteoClient | None = None,
                      flag_return_period: int = 5) -> RiverMonitor | None:
        ref = data_dir / "reference"
        thresholds = ref / "river_points_thresholds.json"
        if not thresholds.is_file():
            return None
        tehsils = pd.read_csv(ref / "river_points.csv").set_index("point_id")["tehsils"].to_dict()
        points = []
        for p in json.loads(thresholds.read_text(encoding="utf-8"))["points"]:
            points.append(RiverPoint(p["point_id"], p["name"], p["lat"], p["lon"],
                                     {2: p["q2"], 5: p["q5"], 10: p["q10"], 20: p["q20"]},
                                     tuple(str(tehsils.get(p["point_id"], "")).split(";"))))
        return cls(points, client or OpenMeteoClient(data_dir / "cache" / "openmeteo"), flag_return_period)

    def _readings(self, payloads: list[dict]) -> list[RiverReading]:
        out = []
        for point, item in zip(self.points, payloads, strict=True):
            for day, value in zip(item["daily"]["time"], item["daily"]["river_discharge"], strict=True):
                if value is not None:
                    out.append(RiverReading(point.point_id, point.name, dt.date.fromisoformat(day), float(value),
                                            return_period_reached(float(value), point.q)))
        return out

    def forecast(self, forecast_days: int = 4, past_days: int = 1) -> list[RiverReading]:
        payloads = self.client.flood([p.lat for p in self.points], [p.lon for p in self.points],
                                     forecast_days=forecast_days, past_days=past_days)
        return self._readings(payloads)

    def history(self, start: dt.date, end: dt.date) -> list[RiverReading]:
        payloads = self.client.flood([p.lat for p in self.points], [p.lon for p in self.points], start, end)
        return self._readings(payloads)

    def tehsil_flags(self, readings: list[RiverReading]) -> dict[tuple[str, dt.date], RiverReading]:
        """(tehsil_id, date) -> the highest reading at or above the flag level."""

        by_point = {p.point_id: p for p in self.points}
        flags: dict[tuple[str, dt.date], RiverReading] = {}
        for r in readings:
            if r.return_period < self.flag_return_period:
                continue
            for tehsil_id in by_point[r.point_id].tehsils:
                key = (tehsil_id, r.date)
                if key not in flags or r.return_period > flags[key].return_period:
                    flags[key] = r
        return flags
