"""Cut roads and paths for the in-scope area out of the Geofabrik Pakistan extract.

Writes 0.1° tiles in the routing cache format (data/cache/osm_roads/roads_<ty>_<tx>.json.gz),
so the router never depends on the public Overpass servers (often overloaded).
Source: OpenStreetMap contributors (ODbL), extract by Geofabrik.

    curl -L -o data/raw/osm/pakistan-latest.osm.pbf https://download.geofabrik.de/asia/pakistan/pakistan-latest.osm.pbf
    python -m pipelines.reference.extract_roads
"""

from __future__ import annotations

import gzip
import json
import math
from collections import defaultdict

import osmium

from backend.app.config import get_settings
from backend.app.geo.routing import HIGHWAYS, TILE

BBOX = (34.0, 71.0, 36.1, 74.6)  # south, west, north, east (in-scope tehsils + margin)
KEEP = set(HIGHWAYS.split("|"))


class RoadHandler(osmium.SimpleHandler):
    def __init__(self) -> None:
        super().__init__()
        self.tiles: dict[tuple[int, int], list[dict]] = defaultdict(list)
        self.ways = 0

    def way(self, w) -> None:
        hw = w.tags.get("highway")
        if hw not in KEEP:
            return
        pts = []
        for n in w.nodes:
            if n.location.valid():
                pts.append([round(n.location.lon, 6), round(n.location.lat, 6)])
        if len(pts) < 2:
            return
        south, west, north, east = BBOX
        tiles = {(math.floor(lat / TILE), math.floor(lon / TILE)) for lon, lat in pts
                 if south <= lat <= north and west <= lon <= east}
        if not tiles:
            return
        record = {"hw": hw, "pts": pts}
        for t in tiles:
            self.tiles[t].append(record)
        self.ways += 1


def main() -> int:
    data = get_settings().data_dir
    pbf = data / "raw" / "osm" / "pakistan-latest.osm.pbf"
    index = data / "raw" / "osm" / "node_locations.idx"
    handler = RoadHandler()
    handler.apply_file(str(pbf), locations=True, idx=f"sparse_file_array,{index}")
    out = data / "cache" / "osm_roads"
    out.mkdir(parents=True, exist_ok=True)
    tiles_written = list(handler.tiles)
    for (ty, tx), ways in handler.tiles.items():
        with gzip.open(out / f"roads_{ty}_{tx}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(ways, fh)
    # Empty tiles inside the box: write them too, so the router does not ask Overpass.
    south, west, north, east = BBOX
    empty = 0
    for ty in range(math.floor(south / TILE), math.floor(north / TILE) + 1):
        for tx in range(math.floor(west / TILE), math.floor(east / TILE) + 1):
            path = out / f"roads_{ty}_{tx}.json.gz"
            if not path.exists():
                with gzip.open(path, "wt", encoding="utf-8") as fh:
                    json.dump([], fh)
                empty += 1
    ways = handler.ways
    del handler  # releases the node index file (Windows keeps it locked while open)
    try:
        index.unlink(missing_ok=True)
    except PermissionError:
        print(f"note: delete {index} by hand")
    print(f"{ways} ways in {len(tiles_written)} tiles ({empty} empty tiles written) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
