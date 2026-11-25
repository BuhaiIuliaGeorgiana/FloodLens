"""Local test with a fake event. Run from the repo root:
    python -m pipelines.osm.dev_run
Needs the Geofabrik folder (data/raw/romania) and internet for Microsoft tiles."""
import json
from pathlib import Path

from shapely.geometry import box, mapping

from pipelines.osm import fetch_osm, calculate_exposure
from pipelines.osm import config

OUT = config.ROOT / "outputs" / "dev_run"
OUT.mkdir(parents=True, exist_ok=True)

event = {
    "event_id": "dev-pechea",
    "polygon": mapping(box(27.74, 45.58, 27.86, 45.68)),
    "start_date": "2024-09-14",
}

osm = fetch_osm(event, OUT / "osm")
print("OSM:", osm["counts"], "cached" if osm["cached"] else "downloaded")

# fake flood polygon, in place of the real S1 output
flood_file = OUT / "fake_flood.geojson"
flood_file.write_text(json.dumps(
    {"type": "FeatureCollection",
     "features": [{"type": "Feature", "properties": {}, "geometry": mapping(box(27.76, 45.60, 27.80, 45.64))}]}))
observation = {"source": "sentinel1", "status": "ready", "date": "2024-09-15",
               "files": [{"type": "flood_geojson", "path": str(flood_file), "bounds": None}]}

res = calculate_exposure(event, observation, osm, OUT / "exposure")
print(json.dumps(res["summary"], indent=2))
