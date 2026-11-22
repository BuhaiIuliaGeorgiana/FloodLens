"""Prag adaptiv, curatarea mastii si explicarea pixelilor."""
import math
import numpy as np
from scipy import ndimage
from .core import classify

# Un pixel poate avea mai multe probleme in acelasi timp.
QUALITY_BITS = {
    "outside_aoi": 1, "missing_radar": 2, "insufficient_baseline": 4,
    "angle_mismatch": 8, "water_reference_missing": 16,
    "water_excluded": 32, "slope_excluded_or_missing": 64,
    "shadow_excluded_or_missing": 128, "shadow_not_screened": 256,
    "water_not_requested": 512, "small_patch_removed": 1024,
    "urban_limitation": 2048, "vegetation_limitation": 4096, "landcover_unknown": 8192,
}


def otsu_candidate(values, options):
    """Acceptam doar histograme cu doua grupuri suficient de separate."""
    values = values[np.isfinite(values)]
    if values.size < options["min_tile_pixels"] or np.ptp(values) < 1e-6:
        return None
    hist, edges = np.histogram(values, bins=128)
    centres = (edges[:-1] + edges[1:]) / 2
    p = hist.astype(float) / hist.sum()
    weight = np.cumsum(p)
    mean = np.cumsum(p * centres)
    total = mean[-1]
    between = np.zeros_like(weight)
    good = (weight > 0) & (weight < 1)
    between[good] = (total * weight[good] - mean[good]) ** 2 / (weight[good] * (1 - weight[good]))
    index = int(np.median(np.flatnonzero(np.isclose(between, between.max(), rtol=1e-10, atol=1e-15))))
    variance = float(np.sum(p * (centres - total) ** 2))
    if variance <= 0 or not good[index]:
        return None
    fraction = float(min(weight[index], 1 - weight[index]))
    separation = float((total - mean[index]) / (1 - weight[index]) - mean[index] / weight[index])
    score = float(between[index] / variance)
    threshold = float(edges[index + 1])
    if (score < options["otsu_min_separability"]
            or fraction < options["otsu_min_class_fraction"]
            or separation < options["otsu_min_separation_db"]
            or not options["adaptive_min_db"] <= threshold <= options["adaptive_max_db"]):
        return None
    return {"water_db": threshold, "separability": score,
            "minority_fraction": fraction, "mean_separation_db": separation}


def choose_threshold(current, valid, options):
    report = {"requested_method": options["threshold_method"], "used_method": "fixed",
              "water_db": float(options["water_db"]), "drop_db": float(options["drop_db"]),
              "accepted_tiles": [], "fallback_reason": None,
              "estimation_domain": "valid pixels inside requested AOI; no spatial buffer"}
    if options["threshold_method"] == "fixed":
        return report
    size = options["tile_size"]
    for row in range(0, current.shape[0], size):
        for col in range(0, current.shape[1], size):
            tile = current[row:row + size, col:col + size]
            available = valid[row:row + size, col:col + size]
            candidate = otsu_candidate(tile[available], options)
            if candidate is not None:
                report["accepted_tiles"].append({"row": row, "col": col, **candidate})
    if len(report["accepted_tiles"]) < options["min_threshold_tiles"]:
        report["fallback_reason"] = "Too few separable water/land tiles; used configured fixed threshold."
    else:
        report["water_db"] = float(np.median([t["water_db"] for t in report["accepted_tiles"]]))
        report["used_method"] = "tile_otsu"
    return report


def analyze(stack, inside, options, shadow=None, threshold=None):
    """Pastram necunoscutul si salvam motivul fiecarei excluderi."""
    baseline, current, count, old_angle, angle, water, slope = stack
    _, valid = classify(stack, inside, options, shadow)
    threshold = choose_threshold(current, valid, options) if threshold is None else threshold
    settings = {**options, "water_db": threshold["water_db"]}
    raw, valid = classify(stack, inside, settings, shadow)
    cleaned = raw.copy()
    minimum = int(math.ceil(options["min_patch_area_m2"] / 100))
    removed = np.zeros_like(inside)
    if minimum > 1:
        # Conectivitate 4, la fel ca la vectorizare; nu unim peste nodata.
        labels, _ = ndimage.label(raw == 1, structure=ndimage.generate_binary_structure(2, 1))
        sizes = np.bincount(labels.ravel())
        removed = (labels > 0) & (sizes[labels] < minimum)
        cleaned[removed] = 0

    known_water = np.isfinite(water) & np.isin(water, [1, 2, 3])
    radar = np.isfinite(stack[:5]).all(axis=0)
    checks = {
        "missing_radar": ~radar,
        "insufficient_baseline": np.isfinite(count) & (count < options["min_baseline_observations"]),
        "angle_mismatch": np.isfinite(angle) & np.isfinite(old_angle) & (np.abs(angle - old_angle) > options["max_angle_difference"]),
        "water_reference_missing": ~known_water if options["use_permanent_water"] else np.zeros_like(inside),
        "water_excluded": ((water == 3) | ((water == 2) & options["exclude_seasonal_water"])) if options["use_permanent_water"] else np.zeros_like(inside),
        "slope_excluded_or_missing": (~np.isfinite(slope) | (slope > options["max_slope_degrees"])) if options["use_dem"] else np.zeros_like(inside),
        "shadow_excluded_or_missing": (~np.isfinite(shadow) | (shadow != 0)) if shadow is not None else np.zeros_like(inside),
        "shadow_not_screened": np.full_like(inside, shadow is None),
        "water_not_requested": np.full_like(inside, not options["use_permanent_water"]),
        "small_patch_removed": removed,
    }
    flags = np.zeros(inside.shape, dtype="uint16")
    flags[~inside] = QUALITY_BITS["outside_aoi"]
    for name, condition in checks.items():
        flags[inside & condition] |= QUALITY_BITS[name]
    remaining = inside.copy()
    stages = {"aoi": int(inside.sum())}
    for name in ("missing_radar", "insufficient_baseline", "angle_mismatch", "water_reference_missing", "water_excluded", "slope_excluded_or_missing", "shadow_excluded_or_missing"):
        if name != "water_reference_missing" or options["missing_water_policy"] == "strict":
            remaining &= ~checks[name]
        stages[name] = int(remaining.sum())
    screened = valid & known_water if options["use_permanent_water"] else np.zeros_like(inside)
    report = {
        "threshold": threshold,
        "exclusion_counts": {name: int((inside & checks[name]).sum()) for name in checks},
        "counts_note": "Independent counts overlap; warning bits do not necessarily exclude a pixel.",
        "remaining_pixels_after_checks": stages,
        "water_class_counts_on_grid": {str(value): int((inside & (water == value)).sum()) for value in (0, 1, 2, 3)},
        "water_nonfinite_pixels_on_grid": int((inside & ~np.isfinite(water)).sum()),
        "water_screened_valid_pixel_count": int(screened.sum()),
        "water_unscreened_valid_pixel_count": int((valid & ~screened).sum()),
        "raw_potential_flood_pixel_count": int((raw == 1).sum()),
        "removed_small_patch_pixel_count": int(removed.sum()),
        "potential_flood_area_ha": float((cleaned == 1).sum() / 100),
        "quality_bits": QUALITY_BITS,
    }
    return cleaned, valid, raw, flags, report
