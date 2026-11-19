"""GloFAS river levels by rarity for the main river points (M6).

1. Main channel: GloFAS (via the Open-Meteo Flood API) snaps to a 0.05° cell,
   often beside the river. For each point, scan the 5 x 5 cells around it over
   the 2022 monsoon and keep the cell with the highest mean discharge.
2. History: daily discharge for Apr–Oct 1997–2025 at that cell (the yearly
   peak falls in these months: snowmelt and monsoon).
3. Return levels: fit a Gumbel distribution to the yearly peaks; q2, q5, q10, q20
   are the flows exceeded on average once in 2, 5, 10, 20 years.

Output: data/reference/river_points_thresholds.json (RiverThresholds contract),
plus each point's chosen cell. Data credit: Copernicus GloFAS via Open-Meteo (CC BY 4.0).

    python -m pipelines.rivers.build_thresholds
"""

from __future__ import annotations

import datetime as dt
import json
import logging

import numpy as np
import pandas as pd
from scipy import stats

from backend.app.config import get_settings
from backend.app.contracts import RiverPointThresholds, RiverThresholds
from backend.app.hydromet.client import OpenMeteoClient, RatePacer

log = logging.getLogger("rivers")
STEP = 0.05
SCAN = (dt.date(2022, 6, 1), dt.date(2022, 9, 30))
YEARS = range(1997, 2026)
RETURN_PERIODS = (2, 5, 10, 20)


def scan_cells(lat: float, lon: float, radius: int = 2) -> list[tuple[float, float]]:
    return [(round(lat + i * STEP, 3), round(lon + j * STEP, 3))
            for i in range(-radius, radius + 1) for j in range(-radius, radius + 1)]


def pick_main_channel(client: OpenMeteoClient, lat: float, lon: float) -> tuple[float, float, float]:
    cells = scan_cells(lat, lon)
    data = client.flood([c[0] for c in cells], [c[1] for c in cells], *SCAN)
    best = None
    for (cell_lat, cell_lon), item in zip(cells, data, strict=True):
        values = np.array([v for v in item["daily"]["river_discharge"] if v is not None], dtype=float)
        mean = float(values.mean()) if values.size else 0.0
        if best is None or mean > best[2]:
            best = (cell_lat, cell_lon, mean)
    return best


def yearly_peaks(client: OpenMeteoClient, lat: float, lon: float) -> pd.Series:
    peaks = {}
    for year in YEARS:
        item = client.flood([lat], [lon], dt.date(year, 4, 1), dt.date(year, 10, 31))[0]
        values = [v for v in item["daily"]["river_discharge"] if v is not None]
        if values:
            peaks[year] = max(values)
    return pd.Series(peaks, name="peak")


def return_levels(peaks: pd.Series) -> dict[int, float]:
    loc, scale = stats.gumbel_r.fit(peaks.to_numpy())
    return {t: float(stats.gumbel_r.ppf(1 - 1 / t, loc, scale)) for t in RETURN_PERIODS}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    data = get_settings().data_dir
    points = pd.read_csv(data / "reference" / "river_points.csv")
    cache = data / "cache" / "openmeteo"
    client = OpenMeteoClient(cache, pacer=RatePacer(state_path=cache / "_pacer.json"))
    out, cells, peak_table = [], {}, {}
    for p in points.itertuples(index=False):
        cell_lat, cell_lon, mean = pick_main_channel(client, p.lat, p.lon)
        peaks = yearly_peaks(client, cell_lat, cell_lon)
        levels = return_levels(peaks)
        cells[p.point_id] = {"lat": cell_lat, "lon": cell_lon, "mean_jjas_2022": round(mean, 1),
                             "offset_km": round(float(np.hypot((cell_lat - p.lat) * 111,
                                                               (cell_lon - p.lon) * 92)), 1)}
        peak_table[p.point_id] = peaks
        out.append(RiverPointThresholds(point_id=p.point_id, name=p.name, lat=cell_lat, lon=cell_lon,
                                        q2=round(levels[2], 1), q5=round(levels[5], 1),
                                        q10=round(levels[10], 1), q20=round(levels[20], 1),
                                        years_used=len(peaks)))
        log.info("%s: cell %.3f,%.3f (mean %.0f m3/s); q2 %.0f q5 %.0f q20 %.0f; peak 2022 %.0f",
                 p.point_id, cell_lat, cell_lon, mean, levels[2], levels[5], levels[20], peaks.get(2022, np.nan))
    result = RiverThresholds(method="Gumbel fit to Apr-Oct yearly peaks 1997-2025 at the main-channel "
                             "GloFAS cell (highest mean discharge within 0.1 degrees)", points=tuple(out))
    (data / "reference" / "river_points_thresholds.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8")
    peaks = pd.DataFrame(peak_table)
    peaks.index.name = "year"
    peaks.to_csv(data / "reference" / "river_yearly_peaks.csv")
    (data / "reference" / "river_points_cells.json").write_text(json.dumps(cells, indent=2), encoding="utf-8")
    print(json.dumps(cells, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
