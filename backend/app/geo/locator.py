"""Find which tehsil a point falls in, using `data/reference/tehsils.geojson`."""

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from backend.app.contracts import TehsilRegion


class TehsilLocator:
    def __init__(self, features: list[tuple[TehsilRegion, object]]) -> None:
        self._regions = [region for region, _ in features]
        self._geoms = [geom for _, geom in features]
        self._tree = STRtree(self._geoms)
        self._by_id = {r.tehsil_id: r for r in self._regions}

    @classmethod
    def from_geojson(cls, path: Path) -> TehsilLocator:
        data = json.loads(path.read_text(encoding="utf-8"))
        features = [
            (TehsilRegion.model_validate(f["properties"]), shape(f["geometry"]))
            for f in data["features"]
        ]
        return cls(features)

    @property
    def regions(self) -> list[TehsilRegion]:
        return list(self._regions)

    def get(self, tehsil_id: str) -> TehsilRegion | None:
        return self._by_id.get(tehsil_id)

    def locate(self, lat: float, lon: float) -> TehsilRegion | None:
        point = Point(lon, lat)
        for index in self._tree.query(point, predicate="intersects"):
            return self._regions[int(index)]
        return None

    def nearest(self, lat: float, lon: float, max_km: float = 5.0) -> TehsilRegion | None:
        """Containing tehsil, or the nearest one within `max_km` (for points on a border)."""

        found = self.locate(lat, lon)
        if found is not None:
            return found
        point = Point(lon, lat)
        index = self._tree.nearest(point)
        if index is None:
            return None
        # Rough degrees-to-km at this latitude band (about 35 N); fine for a cutoff.
        distance_km = self._geoms[int(index)].distance(point) * 100.0
        return self._regions[int(index)] if distance_km <= max_km else None
