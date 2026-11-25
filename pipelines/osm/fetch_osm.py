import json
from pathlib import Path

from . import config
from .geo_utils import event_polygon, polygon_hash, write_geojson, make_file
from .sources import read_osm_roads, read_ms_buildings


def fetch_osm(event, output_dir):
    """Buildings (Microsoft) + roads (OSM) for the event polygon.
    Writes buildings.geojson and roads.geojson in output_dir.
    Skips the work if the same polygon was already fetched."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    b_path, r_path, meta_path = out / "buildings.geojson", out / "roads.geojson", out / "osm_meta.json"

    poly = event_polygon(event)
    sig = polygon_hash(poly)
    bbox = poly.bounds

    # cache: same polygon + files still there -> nothing to download
    if meta_path.exists() and b_path.exists() and r_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("polygon_hash") == sig:
            return _result(b_path, r_path, meta, poly.bounds, cached=True)

    # roads: clip the lines to the polygon (cut at the edge)
    import geopandas as gpd
    roads = read_osm_roads(bbox)
    roads = gpd.clip(roads, poly, keep_geom_type=True) if len(roads) else roads
    if len(roads):
        roads = roads[roads.geom_type.isin(["LineString", "MultiLineString"])].copy()
        roads["is_real_road"] = roads["fclass"].isin(config.REAL_ROADS)

    # buildings: keep WHOLE footprints that touch the polygon (do not cut houses in half)
    buildings = read_ms_buildings(bbox)
    if len(buildings):
        buildings = buildings[buildings.intersects(poly)].copy().reset_index(drop=True)
        buildings["building_id"] = buildings.index

    write_geojson(buildings, b_path)
    write_geojson(roads, r_path)

    meta = {
        "polygon_hash": sig,
        "buildings": int(len(buildings)),
        "roads": int(len(roads)),
        "osm_snapshot_note": "OSM data is the Geofabrik snapshot on the server, not the flood date.",
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return _result(b_path, r_path, meta, bbox, cached=False, b=buildings, r=roads)


def _result(b_path, r_path, meta, bbox, cached, b=None, r=None):
    return {
        "status": "ready",
        "cached": cached,
        "buildings": str(b_path),
        "roads": str(r_path),
        "counts": {"buildings": meta["buildings"], "roads": meta["roads"]},
        "files": [
            make_file("osm_buildings", b_path, b, bounds=bbox),
            make_file("osm_roads", r_path, r, bounds=bbox),
        ],
    }
