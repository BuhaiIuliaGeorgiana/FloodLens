import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from . import config
from .geo_utils import (OsmDataError, event_polygon, pick_metric_crs, polygons_only,
                        read_geojson, write_geojson, make_file)

OK_STATUS = ("ready", "partial")
# S1: flood_extent / valid_coverage. S2: flood_extent_geojson (no valid-area GeoJSON, only valid_mask.tif).
FLOOD_KEYWORDS = ("flood",)
VALID_KEYWORDS = ("valid",)


def _files_list(obs):
    """One list of {type, path} from any of the formats used by the team:
    - S1: layers = [{layer_type, local_path}, ...]
    - S2: files = {"flood_extent_geojson": "path", ...}
    - generic: files = [{type, path}, ...]"""
    items = []

    def add(t, p):
        if t and p:
            items.append({"type": str(t), "path": str(p)})

    files = obs.get("files")
    if isinstance(files, dict):
        for k, v in files.items():
            add(k, v if isinstance(v, str) else (v or {}).get("path") or (v or {}).get("local_path"))
    elif isinstance(files, list):
        for f in files:
            add(f.get("type") or f.get("layer_type"), f.get("path") or f.get("local_path"))
    for f in obs.get("layers") or []:
        add(f.get("layer_type") or f.get("type"), f.get("local_path") or f.get("path"))
    return items


def _date(obs):
    # CHECK: confirm the exact date key with the S1/S2 owners
    for k in ("acquisition_date", "date", "acquired_at", "datetime", "observation_date"):
        if obs.get(k):
            return str(obs[k])
    return None


def _normalise(obs):
    """Accept one observation or a whole S1/S2 result ({source, status, reason,
    observations: [...]}); return one flat dict with source, status, date, files."""
    obs = dict(obs)
    if obs.get("observations"):
        inner = max(obs["observations"], key=lambda o: _date(o) or "")
        top = {k: v for k, v in obs.items() if k != "observations"}
        obs = {**top, **inner}
    obs["files"] = _files_list(obs)
    obs["date"] = _date(obs)
    obs.setdefault("source", "unknown")
    obs.setdefault("status", "ready")
    return obs


def _find_path(obs, keywords):
    for f in obs.get("files", []):
        t = str(f.get("type", "")).lower()
        p = str(f.get("path", ""))
        if any(k in t for k in keywords) and p.lower().endswith((".geojson", ".json")):
            return p
    return None


def _lines_only(geom):
    if geom.is_empty:
        return None
    if geom.geom_type in ("LineString", "MultiLineString"):
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in geom.geoms if g.geom_type in ("LineString", "MultiLineString")]
        return unary_union(parts) if parts else None
    return None


def _union_metric(path, metric):
    gdf = read_geojson(path)
    if len(gdf) == 0:
        return Polygon()
    return polygons_only(unary_union(gdf.to_crs(metric).geometry))


def calculate_exposure(event, observation, osm_data, output_dir):
    """What is under the possibly flooded area? Run once per source (S1, S2)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    obs = _normalise(observation)
    source = obs["source"]
    event_id = event.get("event_id") or event.get("id")

    def skipped(reason):
        return {"status": "skipped", "reason": reason, "summary": None, "files": []}

    if obs["status"] not in OK_STATUS:
        return skipped(f"{source} result has status '{obs['status']}': {obs.get('reason') or 'no reason given'}")
    flood_path = _find_path(obs, FLOOD_KEYWORDS)
    if not flood_path or not Path(flood_path).exists():
        return skipped("no flood GeoJSON found in the observation")
    try:
        read_geojson(flood_path)  # fail early with a clear reason (e.g. unknown CRS)
    except OsmDataError as exc:
        return {"status": "failed", "reason": str(exc), "summary": None, "files": []}

    poly = event_polygon(event)
    metric = pick_metric_crs(poly)
    poly_m = polygons_only(gpd.GeoSeries([poly], crs=4326).to_crs(metric).iloc[0])

    buildings = read_geojson(osm_data["buildings"])
    roads = read_geojson(osm_data["roads"])
    b_m = buildings.to_crs(metric) if len(buildings) else buildings
    r_m = roads.to_crs(metric) if len(roads) else roads

    # flood area = flood polygons, only inside the valid area and the event polygon
    flood_m = _union_metric(flood_path, metric)
    valid_path = _find_path(obs, VALID_KEYWORDS)
    valid_ha = None
    if valid_path and Path(valid_path).exists():
        valid_m = _union_metric(valid_path, metric)
        valid_ha = valid_m.intersection(poly_m).area / 10_000
        flood_m = make_valid(flood_m).intersection(valid_m)
    flood_m = polygons_only(make_valid(flood_m).intersection(poly_m))

    flood_found = not flood_m.is_empty
    exp_b = b_m.iloc[0:0].assign(overlap_pct=[], mostly_flooded=[]) if len(b_m) else b_m
    exp_r = r_m.iloc[0:0].assign(flooded_m=[]) if len(r_m) else r_m
    if flood_found:
        if len(b_m):
            hit = b_m.iloc[b_m.sindex.query(flood_m, predicate="intersects")].copy()
            area = hit.geometry.area.replace(0, float("nan"))
            hit["overlap_pct"] = (hit.geometry.intersection(flood_m).area / area * 100).round(1)
            hit["mostly_flooded"] = hit["overlap_pct"] >= config.MOSTLY_FLOODED_PCT
            exp_b = hit
        if len(r_m):
            hit = r_m.iloc[r_m.sindex.query(flood_m, predicate="intersects")].copy()
            hit["geometry"] = hit.geometry.intersection(flood_m).apply(_lines_only)
            hit = hit[hit.geometry.notna()].copy()
            hit["flooded_m"] = hit.geometry.length.round(1)
            exp_r = hit

    suffix = source
    files_out = [
        ("exposed_buildings", write_geojson(exp_b, out / f"exposed_buildings_{suffix}.geojson"), exp_b),
        ("exposed_roads", write_geojson(exp_r, out / f"exposed_roads_{suffix}.geojson"), exp_r),
    ]

    real = exp_r[exp_r["is_real_road"]] if len(exp_r) else exp_r
    summary = {
        "event_id": event_id,
        "source": source,
        "observation_date": obs["date"],
        "flood_detected": flood_found,
        "buildings_exposed": int(len(exp_b)),  # touched by the flood (any overlap)
        "buildings_mostly_flooded": int(exp_b["mostly_flooded"].sum()) if len(exp_b) else 0,
        "mostly_flooded_threshold_pct": config.MOSTLY_FLOODED_PCT,
        "buildings_total": int(len(b_m)),
        "roads_exposed_km": round(float(exp_r.geometry.length.sum()) / 1000, 2) if len(exp_r) else 0.0,
        "roads_real_exposed_km": round(float(real.geometry.length.sum()) / 1000, 2) if len(real) else 0.0,
        "roads_total_km": round(float(r_m.geometry.length.sum()) / 1000, 2) if len(r_m) else 0.0,
        "flooded_area_ha": round(flood_m.area / 10_000, 2),
        "valid_area_ha": round(valid_ha, 2) if valid_ha is not None else None,
        "note": config.NOTE,
    }
    if not flood_found:
        summary["reason"] = "no flooded area inside the valid area of this observation"
    s_path = out / f"exposure_summary_{suffix}.json"
    s_path.write_text(json.dumps(summary, indent=2))

    files = [make_file(t, p, g, bounds=poly.bounds) for t, p, g in files_out]
    files.append(make_file("exposure_summary", s_path, bounds=poly.bounds))
    return {"status": "ready", "summary": summary, "files": files}
