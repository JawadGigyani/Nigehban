"""Weather grid cells for each tehsil.

Each tehsil is covered by the 0.25° cells of the ERA5 / ECMWF grid that overlap
its polygon. A cell's weight is its share of the tehsil's area, so a tehsil
mean is `sum(weight * value)`. Small tehsils that fall inside one cell get that
cell with weight 1. The same cell centres are used for every weather source,
so one request covers all tehsils without repeating points.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import box, shape

CELL_DEG = 0.25
# Cells covering less than this share of a tehsil are dropped (and the rest
# re-weighted), so the tehsil max is not driven by a sliver at the border.
MIN_WEIGHT = 0.02


@dataclass(frozen=True)
class Cell:
    lat: float
    lon: float

    @property
    def key(self) -> str:
        return f"{self.lat:.2f},{self.lon:.2f}"


@dataclass(frozen=True)
class CellWeight:
    tehsil_id: str
    cell: Cell
    weight: float


def _snap(value: float) -> float:
    return round(round(value / CELL_DEG) * CELL_DEG, 2)


def cells_for_geometry(geom, cell_deg: float = CELL_DEG) -> list[tuple[Cell, float]]:
    """Cells (centred on the grid) overlapping `geom`, with area-share weights."""

    minx, miny, maxx, maxy = geom.bounds
    half = cell_deg / 2
    lat0, lat1 = _snap(miny), _snap(maxy)
    lon0, lon1 = _snap(minx), _snap(maxx)
    out: list[tuple[Cell, float]] = []
    total = geom.area
    n_lat = int(round((lat1 - lat0) / cell_deg)) + 1
    n_lon = int(round((lon1 - lon0) / cell_deg)) + 1
    for i in range(n_lat):
        lat = round(lat0 + i * cell_deg, 2)
        for j in range(n_lon):
            lon = round(lon0 + j * cell_deg, 2)
            overlap = geom.intersection(box(lon - half, lat - half, lon + half, lat + half)).area
            if overlap > 0:
                out.append((Cell(lat, lon), overlap / total))
    kept = [(c, w) for c, w in out if w >= MIN_WEIGHT] or [max(out, key=lambda cw: cw[1])]
    norm = sum(w for _, w in kept)
    return [(c, w / norm) for c, w in kept]


def build_grid(tehsils_geojson: Path, only_in_scope: bool = False) -> list[CellWeight]:
    data = json.loads(tehsils_geojson.read_text(encoding="utf-8"))
    rows: list[CellWeight] = []
    for feature in data["features"]:
        props = feature["properties"]
        if only_in_scope and not props.get("in_scope", True):
            continue
        for cell, weight in cells_for_geometry(shape(feature["geometry"])):
            rows.append(CellWeight(props["tehsil_id"], cell, round(weight, 5)))
    return rows


def write_grid(rows: list[CellWeight], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["tehsil_id", "lat", "lon", "weight"])
        for r in rows:
            writer.writerow([r.tehsil_id, f"{r.cell.lat:.2f}", f"{r.cell.lon:.2f}", r.weight])


def load_grid(path: Path) -> list[CellWeight]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [
            CellWeight(r["tehsil_id"], Cell(float(r["lat"]), float(r["lon"])), float(r["weight"]))
            for r in csv.DictReader(fh)
        ]


def unique_cells(rows: list[CellWeight]) -> list[Cell]:
    return sorted({r.cell for r in rows}, key=lambda c: (c.lat, c.lon))


def check_weights(rows: list[CellWeight]) -> None:
    sums: dict[str, float] = {}
    for r in rows:
        sums[r.tehsil_id] = sums.get(r.tehsil_id, 0.0) + r.weight
    bad = {t: s for t, s in sums.items() if not math.isclose(s, 1.0, abs_tol=1e-3)}
    if bad:
        raise ValueError(f"Weights do not sum to 1 for {sorted(bad)[:5]}")
