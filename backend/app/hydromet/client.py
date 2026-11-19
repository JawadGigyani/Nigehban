"""Open-Meteo client: forecast, previous runs, ERA5 archive and flood (GloFAS).

- No API key. Free tier for non-commercial use: 600 calls a minute, 5,000 an
  hour, 10,000 a day. A request for more than 10 variables or more than 14 days
  per location counts as several calls, so the pacer charges each request
  `locations * max(1, variables / 10) * max(1, days / 14)` (conservative).
- Responses are cached on disk (gzip JSON, keyed by URL and parameters).
  Historical data never expires; live forecasts expire after `ttl_s`.
- Several locations go in one request (comma-separated coordinates).
- Data credit: Open-Meteo (CC BY 4.0), ECMWF ERA5 / IFS, NOAA GFS, DWD ICON,
  Copernicus GloFAS.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import logging
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from backend.app.hydromet.grid import Cell

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"

TIMEZONE = "Asia/Karachi"  # PDMA report dates are local days

# Open-Meteo model names for the forecast models used by Nigehban.
FORECAST_MODELS = {"ecmwf": "ecmwf_ifs025", "gfs": "gfs_seamless", "icon": "icon_seamless"}


class OpenMeteoError(RuntimeError):
    pass


class DailyLimitReached(OpenMeteoError):
    """The free daily quota is used up; resume later (the cache keeps progress)."""


@dataclass
class RatePacer:
    """Keeps the charged weight under per-minute, per-hour and per-day budgets."""

    per_minute: float = 500.0
    per_hour: float = 4500.0
    per_day: float = 9000.0
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    state_path: Path | None = None  # remembers usage across restarts
    _log: deque = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.state_path is not None and self.state_path.is_file():
            try:
                entries = json.loads(self.state_path.read_text())
                now = self.clock()
                self._log.extend((t, w) for t, w in entries if now - t < 86400)
            except (ValueError, TypeError):
                pass

    def _save(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(self._log)))
        tmp.replace(self.state_path)

    def _used(self, window: float, now: float) -> float:
        return sum(w for t, w in self._log if now - t < window)

    def acquire(self, weight: float) -> None:
        while True:
            now = self.clock()
            while self._log and now - self._log[0][0] >= 86400:
                self._log.popleft()
            if self._used(86400, now) + weight > self.per_day:
                raise DailyLimitReached("Local daily budget used up; resume tomorrow.")
            wait = 0.0
            for window, budget in ((60, self.per_minute), (3600, self.per_hour)):
                if self._used(window, now) + weight > budget:
                    oldest = next((t for t, _ in self._log if now - t < window), now)
                    wait = max(wait, window - (now - oldest) + 0.5)
            if wait <= 0:
                self._log.append((now, weight))
                self._save()
                return
            log.info("rate pacer: waiting %.0f s", wait)
            self.sleep(min(wait, 60.0))


def request_weight(n_locations: int, n_variables: int, n_days: int) -> float:
    return n_locations * max(1.0, n_variables / 10) * max(1.0, n_days / 14)


class ResponseCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @staticmethod
    def key(url: str, params: dict) -> str:
        blob = json.dumps({"url": url, "params": params}, sort_keys=True)
        return hashlib.sha1(blob.encode()).hexdigest()

    def path(self, key: str) -> Path:
        return self.directory / key[:2] / f"{key}.json.gz"

    def get(self, key: str, ttl_s: float | None) -> object | None:
        path = self.path(key)
        if not path.is_file():
            return None
        if ttl_s is not None and time.time() - path.stat().st_mtime > ttl_s:
            return None
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None  # partial write; fetch again

    def put(self, key: str, value: object) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(value, fh)
        tmp.replace(path)


class OpenMeteoClient:
    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        pacer: RatePacer | None = None,
        http: httpx.Client | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 4,
        user_agent: str = "nigehban-research/0.1",
    ) -> None:
        self.cache = ResponseCache(cache_dir) if cache_dir else None
        self.pacer = pacer or RatePacer()
        self.http = http or httpx.Client(timeout=timeout_s, headers={"User-Agent": user_agent})
        self.max_retries = max_retries
        self.calls = 0  # network requests made (not cache hits)

    # ---- low level ---------------------------------------------------------------------

    def get(self, url: str, params: dict, *, weight: float, ttl_s: float | None = None) -> list[dict]:
        """GET with cache, pacing and retries. Always returns a list (one item per location)."""

        key = ResponseCache.key(url, params)
        if self.cache is not None:
            cached = self.cache.get(key, ttl_s)
            if cached is not None:
                return cached
        delay = 5.0
        for attempt in range(self.max_retries + 1):
            self.pacer.acquire(weight)
            try:
                response = self.http.get(url, params=params)
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise OpenMeteoError(f"network error: {exc}") from exc
                time.sleep(delay)
                delay *= 2
                continue
            self.calls += 1
            if response.status_code == 200:
                data = response.json()
                data = data if isinstance(data, list) else [data]
                if self.cache is not None:
                    self.cache.put(key, data)
                return data
            reason = _reason(response)
            if response.status_code == 429:
                if "daily" in reason.lower():
                    raise DailyLimitReached(reason)
                wait = 65.0 if "minut" in reason.lower() else delay * 6
                log.warning("Open-Meteo 429 (%s); waiting %.0f s", reason, wait)
                time.sleep(wait)
                continue
            if response.status_code >= 500 and attempt < self.max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise OpenMeteoError(f"HTTP {response.status_code}: {reason}")
        raise OpenMeteoError("retries exhausted")

    # ---- endpoints -----------------------------------------------------------------------

    @staticmethod
    def _coords(cells: Sequence[Cell]) -> dict:
        return {
            "latitude": ",".join(f"{c.lat:.2f}" for c in cells),
            "longitude": ",".join(f"{c.lon:.2f}" for c in cells),
        }

    def archive(self, cells: Sequence[Cell], start: dt.date, end: dt.date,
                hourly: Sequence[str], model: str = "era5") -> list[dict]:
        """ERA5 reanalysis (about 5 days behind real time)."""

        params = {**self._coords(cells), "start_date": start.isoformat(), "end_date": end.isoformat(),
                  "hourly": ",".join(hourly), "models": model, "timezone": TIMEZONE}
        days = (end - start).days + 1
        return self.get(ARCHIVE_URL, params, weight=request_weight(len(cells), len(hourly), days))

    def forecast(self, cells: Sequence[Cell], hourly: Sequence[str], models: Sequence[str],
                 forecast_days: int = 4, past_days: int = 7, ttl_s: float = 3600.0) -> list[dict]:
        params = {**self._coords(cells), "hourly": ",".join(hourly), "models": ",".join(models),
                  "forecast_days": forecast_days, "past_days": past_days, "timezone": TIMEZONE}
        weight = request_weight(len(cells), len(hourly) * len(models), forecast_days + past_days)
        return self.get(FORECAST_URL, params, weight=weight, ttl_s=ttl_s)

    def previous_runs(self, cells: Sequence[Cell], start: dt.date, end: dt.date,
                      hourly: Sequence[str], models: Sequence[str]) -> list[dict]:
        """Archived forecasts at fixed lead days (`precipitation_previous_day1` etc.); from about 2024."""

        params = {**self._coords(cells), "start_date": start.isoformat(), "end_date": end.isoformat(),
                  "hourly": ",".join(hourly), "models": ",".join(models), "timezone": TIMEZONE}
        days = (end - start).days + 1
        weight = request_weight(len(cells), len(hourly) * len(models), days)
        return self.get(PREVIOUS_RUNS_URL, params, weight=weight)

    def flood(self, lats: Sequence[float], lons: Sequence[float], start: dt.date | None = None,
              end: dt.date | None = None, forecast_days: int = 7, past_days: int = 0,
              ttl_s: float | None = 3600.0) -> list[dict]:
        """GloFAS daily river discharge (m³/s). Snaps to the nearest 0.05° cell."""

        params: dict = {"latitude": ",".join(f"{v:.3f}" for v in lats),
                        "longitude": ",".join(f"{v:.3f}" for v in lons),
                        "daily": "river_discharge"}
        if start and end:
            params |= {"start_date": start.isoformat(), "end_date": end.isoformat()}
            days = (end - start).days + 1
            ttl = None if end < dt.date.today() - dt.timedelta(days=7) else ttl_s
        else:
            params |= {"forecast_days": forecast_days, "past_days": past_days}
            days = forecast_days + past_days
            ttl = ttl_s
        return self.get(FLOOD_URL, params, weight=request_weight(len(lats), 1, days), ttl_s=ttl)


def _reason(response: httpx.Response) -> str:
    try:
        return str(response.json().get("reason", response.text[:200]))
    except ValueError:
        return response.text[:200]
