"""Validare, grila comuna si clasificare locala."""
from datetime import datetime, timezone
from math import floor, ceil

import numpy as np
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.features import geometry_mask
from shapely.geometry import shape, mapping
from shapely import transform

DEFAULTS = {
    "band": "VV", "drop_db": 3.0, "water_db": -17.0,
    "min_baseline_observations": 2, "max_angle_difference": 2.0,
    "max_slope_degrees": 5.0, "exclude_seasonal_water": False,
    "min_coverage_pct": 20.0, "max_pixels": 5_000_000,
    "use_permanent_water": True, "use_dem": True,
    "shadow_masks": {}, "missing_water_policy": "partial",
}


def utc(value):
    """Datele simple inseamna miezul noptii UTC."""
    if not isinstance(value, str):
        raise ValueError("Dates must be ISO strings")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        if len(value) != 10:
            raise ValueError("Timestamps must include a timezone")
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate(event):
    for key in ("event_id", "aoi", "baseline_start", "event_start", "search_end", "grid"):
        if key not in event:
            raise ValueError(f"Missing event.{key}")
    if not isinstance(event["event_id"], str) or not event["event_id"].strip():
        raise ValueError("event_id must be a non-empty string")
    dates = {k: utc(event[k]) for k in ("baseline_start", "event_start", "search_end")}
    if not dates["baseline_start"] < dates["event_start"] < dates["search_end"]:
        raise ValueError("Require baseline_start < event_start < search_end")
    geom = shape(event["aoi"])
    if geom.geom_type != "Polygon" or geom.is_empty or not geom.is_valid:
        raise ValueError("aoi must be a valid non-empty GeoJSON Polygon")
    west, south, east, north = geom.bounds
    if not (-180 <= west < east <= 180 and -85 < south < north < 85):
        raise ValueError("AOI outside supported longitude/latitude range")
    if east - west > 180:
        raise ValueError("Split an antimeridian-crossing AOI before processing")
    options = dict(DEFAULTS)
    supplied = event.get("sentinel1", {})
    if set(supplied) - set(options):
        raise ValueError(f"Unknown Sentinel-1 settings: {set(supplied) - set(options)}")
    options.update(supplied)
    if options["band"] not in ("VV", "VH"):
        raise ValueError("band must be VV or VH")
    for key in ("drop_db", "water_db", "max_angle_difference", "max_slope_degrees", "min_coverage_pct"):
        if not isinstance(options[key], (int, float)) or not np.isfinite(options[key]):
            raise ValueError(f"Invalid {key}")
    if options["drop_db"] <= 0 or options["max_angle_difference"] < 0:
        raise ValueError("drop_db must be positive; angle tolerance nonnegative")
    if not 0 <= options["max_slope_degrees"] < 90 or not 0 < options["min_coverage_pct"] <= 100:
        raise ValueError("Invalid slope or coverage threshold")
    for key in ("min_baseline_observations", "max_pixels"):
        if type(options[key]) is not int or options[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("use_permanent_water", "use_dem", "exclude_seasonal_water"):
        if type(options[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    if not isinstance(options["shadow_masks"], dict):
        raise ValueError("shadow_masks must map observation IDs to local TIFF paths")
    if options["missing_water_policy"] not in ("partial", "strict"):
        raise ValueError("missing_water_policy must be partial or strict")
    return dates, options


def make_grid(event, max_pixels):
    """Aliniem marginile la originea primita de la echipa."""
    spec = event["grid"]
    crs = CRS.from_user_input(spec["crs"])
    if not crs.is_projected or any(a.unit_conversion_factor != 1 for a in crs.axis_info[:2]):
        raise ValueError("grid.crs must be projected, with metre units")
    if spec["resolution"] != 10:
        raise ValueError("Shared grid resolution must be 10 metres")
    ox, oy = spec["origin"]
    if not np.isfinite([ox, oy]).all():
        raise ValueError("Grid origin must be finite")
    # Indesim conturul inainte de schimbarea proiectiei.
    polygon = shape(event["aoi"]).segmentize(0.01)
    project = Transformer.from_crs(4326, crs, always_xy=True).transform
    projected = transform(polygon, project, interleaved=False)
    x0, y0, x1, y1 = projected.bounds
    if not np.isfinite([x0, y0, x1, y1]).all():
        raise ValueError("AOI cannot be projected into this grid")
    left = ox + floor((x0 - ox) / 10) * 10
    top = oy + ceil((y1 - oy) / 10) * 10
    width = ceil((x1 - left) / 10)
    height = ceil((top - y0) / 10)
    if width * height > max_pixels or width < 1 or height < 1:
        raise ValueError("AOI exceeds max_pixels; split the AOI or raise the documented memory limit")
    affine = Affine(10, 0, left, 0, -10, top)
    inside = geometry_mask([mapping(projected)], (height, width), affine, invert=True)
    if not inside.any():
        raise ValueError("AOI contains no pixel centres at this grid resolution")
    return {"crs": crs.to_string(), "transform": affine,
            "width": width, "height": height, "inside": inside}


def comparison_key(record):
    # Aceeasi platforma este o restrictie suplimentara pentru prima versiune.
    return (record["mode"], record["relative_orbit"], record["direction"],
            tuple(sorted(record["polarizations"])), record["platform"])


def group_observations(records):
    """Unim doar feliile aceleiasi treceri, nu date diferite."""
    groups = {}
    for record in records:
        key = (comparison_key(record), record["absolute_orbit"], record["datatake"])
        groups.setdefault(key, []).append(record)
    result = []
    for group in groups.values():
        unique = {}
        discarded = []
        for record in sorted(group, key=lambda r: r["asset_id"]):
            key = (record["acquired_at"], record["slice"])
            if key in unique:
                discarded.append(unique[key]["asset_id"])
            unique[key] = record
        selected = sorted(unique.values(), key=lambda r: r["acquired_at"])
        first = selected[0]
        result.append({"observation_id": f"s1_{first['platform']}_{first['absolute_orbit']}_{first['datatake']}",
                       "acquired_at": first["acquired_at"], "records": selected,
                       "discarded_duplicate_scene_ids": discarded})
    return sorted(result, key=lambda item: item["acquired_at"])


def classify(stack, inside, options, shadow=None):
    """0 = fara detectie, 1 = inundatie posibila, 255 = exclus/necunoscut."""
    baseline, current, count, old_angle, angle, water, slope = stack
    valid = inside & np.isfinite(stack[:5]).all(axis=0)
    valid &= count >= options["min_baseline_observations"]
    valid &= np.abs(angle - old_angle) <= options["max_angle_difference"]
    if options["use_permanent_water"]:
        valid &= np.isfinite(water) & np.isin(water, [1, 2])
        if options["exclude_seasonal_water"]:
            valid &= water != 2
    if options["use_dem"]:
        valid &= np.isfinite(slope) & (slope <= options["max_slope_degrees"])
    if shadow is not None:
        valid &= np.isfinite(shadow) & (shadow == 0)
    mask = np.full(inside.shape, 255, dtype="uint8")
    mask[valid] = 0
    candidate = (current <= options["water_db"]) & ((baseline - current) >= options["drop_db"])
    mask[valid & candidate] = 1
    return mask, valid
