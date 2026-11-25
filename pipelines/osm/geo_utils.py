"""Small helpers shared by fetch_osm and calculate_exposure."""
import hashlib
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape, MultiPolygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from . import config


class OsmDataError(Exception):
    """Raised when OSM/Microsoft data cannot be read. The coordinator
    catches it and marks this part of the run as 'failed' with this message."""


# ---------- event polygon ----------

def polygons_only(geom):
    """make_valid can return a GeometryCollection; keep only the polygon parts."""
    geom = make_valid(geom)
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    parts = []
    for g in getattr(geom, "geoms", []):
        if g.geom_type == "Polygon":
            parts.append(g)
        elif g.geom_type == "MultiPolygon":
            parts.extend(g.geoms)
    return MultiPolygon(parts) if parts else geom.__class__()


def event_polygon(event):
    """Return the event area as a shapely polygon in EPSG:4326.
    Accepts a Geometry, Feature or FeatureCollection, as dict or JSON string.
    Key names differ per team: polygon/geometry (OSM, S2), aoi (S1), aoi_geojson (DB)."""
    raw = (event.get("polygon") or event.get("geometry") or event.get("geojson")
           or event.get("aoi_geojson") or event.get("aoi"))  # aoi_geojson = DB/frontend, aoi = Sentinel-1
    if raw is None:
        raise OsmDataError("event has no polygon")
    if isinstance(raw, str):
        raw = json.loads(raw)
    kind = raw.get("type")
    if kind == "FeatureCollection":
        geom = unary_union([shape(f["geometry"]) for f in raw["features"]])
    elif kind == "Feature":
        geom = shape(raw["geometry"])
    else:
        geom = shape(raw)
    geom = polygons_only(geom)
    if geom.is_empty:
        raise OsmDataError("event polygon is empty or invalid")
    return geom


def polygon_hash(poly):
    """Short fingerprint of the polygon, used to know if the cache is still valid."""
    return hashlib.sha1(poly.wkb).hexdigest()[:16]


def pick_metric_crs(poly_4326):
    """EPSG:3844 inside Romania, otherwise the local UTM zone."""
    c = poly_4326.centroid
    if 20 <= c.x <= 30 and 43.5 <= c.y <= 48.5:
        return config.MEASURE_CRS
    return gpd.GeoSeries([poly_4326], crs=4326).estimate_utm_crs()


# ---------- GeoDataFrames ----------

def clean(gdf):
    """Drop empty/null geometries and repair invalid ones."""
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    gdf["geometry"] = gdf.geometry.apply(make_valid)
    return gdf[~gdf.geometry.is_empty]


def read_geojson(path):
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        # no CRS in the file: only accept it if the numbers look like lon/lat
        if len(gdf) and (abs(gdf.total_bounds) > 180).any():
            raise OsmDataError(f"{path} has no CRS and its coordinates are not lon/lat")
        gdf = gdf.set_crs(4326)
    return clean(gdf) if len(gdf) else gdf


def write_geojson(gdf, path):
    """Always writes a valid file, even when gdf is empty."""
    path = Path(path)
    if gdf is None or len(gdf) == 0:
        path.write_text('{"type": "FeatureCollection", "features": []}')
    else:
        gdf.to_crs(4326).to_file(path, driver="GeoJSON")
    return str(path)


# ---------- file records ----------

def make_file(type_, path, gdf=None, bounds=None):
    """The record every pipeline step returns for each output file:
    {"type": ..., "path": ..., "bounds": [west, south, east, north] or None}"""
    if gdf is not None and len(gdf) > 0:
        bounds = [round(float(x), 6) for x in gdf.to_crs(4326).total_bounds]
    elif bounds is not None:
        bounds = [round(float(x), 6) for x in bounds]
    # "type" is what the pipelines use, "layer_type" is the DB column name
    return {"type": type_, "layer_type": type_, "path": str(path), "bounds": bounds}
