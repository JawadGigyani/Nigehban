"""Observed rain from satellite (NASA IMERG) for the board's "rain already fallen" layer.

- This is a nowcast, not a forecast: it shows rain that has already fallen. It is NOT a model input
  (see reports/imerg_vs_era5.md: past satellite rain does not improve 1–3 day forecasts).
- Live: the latest finished UTC day, trying the Late run first (more accurate), then Early.
  Daily files appear a few hours to about a day after the day ends.
- Replay (as_of in the past): the day before as_of, from the Final run (falls back to Late/Early).
- Values per tehsil (area-weighted mean and wettest 0.1° cell) plus the wet cells themselves.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from dataclasses import dataclass, field

from backend.app.hydromet.imerg import LATS, LONS, ImergClient, ImergError, tehsil_values

LIVE_TTL_S = 30 * 60
MIN_CELL_MM = 1.0


@dataclass
class ObservedRain:
    date: dt.date | None
    run: str | None
    tehsils: dict[str, tuple[float, float]] = field(default_factory=dict)
    cells: list[tuple[float, float, float]] = field(default_factory=list)  # lon, lat, mm
    note: str = ""


class RainNowcast:
    def __init__(self, client: ImergClient, weights: dict[str, list[tuple[int, int, float]]],
                 clock=None) -> None:
        self.client = client
        self.weights = weights
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self._cells = sorted({(i, j) for cells in weights.values() for i, j, _ in cells})
        self._lock = threading.Lock()
        self._live: tuple[float, ObservedRain] | None = None

    def _build(self, grid, day: dt.date, run: str) -> ObservedRain:
        cells = []
        for i, j in self._cells:
            if i < grid.shape[0] and j < grid.shape[1]:
                v = float(grid[i, j])
                if v == v and v >= MIN_CELL_MM:
                    cells.append((float(LONS[i]), float(LATS[j]), round(v, 1)))
        return ObservedRain(day, run, tehsil_values(grid, self.weights), cells,
                            f"NASA GPM IMERG {run.title()} run, rain in the UTC day {day:%d %b %Y}.")

    def _first(self, candidates: list[tuple[dt.date, str]]) -> ObservedRain:
        for day, run in candidates:
            grid = self.client.day(day, run)
            if grid is not None:
                return self._build(grid, day, run)
        return ObservedRain(None, None, note="No satellite rain file is available yet for these days.")

    def observed(self, as_of: dt.datetime | None = None) -> ObservedRain:
        if not self.client.token:
            return ObservedRain(None, None, note="Satellite rain is off (no Earthdata token set).")
        now = self.clock()
        try:
            if as_of is not None and as_of.astimezone(dt.timezone.utc).date() < now.date() - dt.timedelta(days=3):
                day = as_of.astimezone(dt.timezone.utc).date() - dt.timedelta(days=1)
                return self._first([(day, "final"), (day, "late"), (day, "early")])
            with self._lock:
                if self._live and time.monotonic() - self._live[0] < LIVE_TTL_S:
                    return self._live[1]
                days = [now.date() - dt.timedelta(days=k) for k in (1, 2, 3)]
                result = self._first([(d, run) for d in days for run in ("late", "early")])
                self._live = (time.monotonic(), result)
                return result
        except ImergError as exc:
            return ObservedRain(None, None, note=f"Satellite rain unavailable: {exc}")
