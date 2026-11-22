"""Pipeline Sentinel-1 pentru un eveniment ales de utilizator."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import uuid
import numpy as np

from . import earth_engine as backend
from .core import validate, make_grid, group_observations, comparison_key, utc
from .comparison import load_context, analyze_band, compare_masks
from .outputs import write_json, read_shadow, export_observation, export_context_layers

VERSION = "0.3.0"
LIMITATIONS = [
    "Experimental open-water change detector; thresholds are not validated universally.",
    "Urban flooding and water beneath vegetation can be missed; bright double-bounce flooding is not detected.",
    "Wind, soil moisture, farming and speckle can cause false detections or missed flooding.",
    "10 m grid spacing is not 10 m effective radar resolution.",
    "Earth Engine GRD is calibrated terrain-corrected sigma0 in dB, not radiometrically terrain-flattened data.",
    "Processing coverage is not detection accuracy; urban and vegetated pixels remain difficult even when radar is valid.",
]


def process_sentinel1(event: dict, output_dir: str) -> dict:
    """Genereaza fisiere locale. Nu autentifica si nu incarca in Supabase."""
    result = {"event_id": event.get("event_id"), "source": "sentinel1", "status": "failed",
              "reason": None, "observations": [], "pipeline_version": VERSION,
              "processed_at": datetime.now(timezone.utc).isoformat(), "warnings": []}
    try:
        dates, options = validate(event)
        grid = make_grid(event, options["max_pixels"])
        # Alegem un an complet anterior evenimentului.
        options["water_reference_year"] = min(int(dates["event_start"][:4]) - 1, 2021)
        run = uuid.uuid4().hex
        event_key = hashlib.sha256(event["event_id"].encode()).hexdigest()[:16]
        root = Path(output_dir).resolve() / event_key / run
        root.mkdir(parents=True, exist_ok=False)
        result["manifest_path"] = str(root / "manifest.json")
        result["configuration"] = {"dates": dates, "aoi": event["aoi"], "grid": event["grid"],
                                   "sentinel1": options,
                                   "date_boundaries": "baseline=[baseline_start,event_start); observations=[event_start,search_end), UTC",
                                   "source_collection": backend.COLLECTION,
                                   "baseline_statistic": "median linear power converted to dB",
                                   "resampling": "nearest",
                                   "spatial_speckle_filter": {"method": options["speckle_filter"], "window_pixels": options["lee_window"], "enl": options["lee_enl"], "domain": "linear power, per acquisition before baseline median"},
                                   "minimum_patch_area_m2": options["min_patch_area_m2"],
                                   "output_mask_values": {"0": "no_detection", "1": "potential_flood", "255": "unknown_or_excluded"},
                                   "water_asset": backend.WATER_ASSET if options["use_permanent_water"] else None,
                                   "dem_asset": backend.DEM_ASSET if options["use_dem"] else None}
        result["analysis_grid"] = {"crs": grid["crs"], "transform": list(grid["transform"])[:6],
                                   "width": grid["width"], "height": grid["height"],
                                   "pixel_inclusion": "centre inside AOI"}
        records = backend.discover(event, dates)
        write_json(root / "candidates.json", records)
        baseline_groups = group_observations([r for r in records if r["acquired_at"] < dates["event_start"]])
        event_groups = group_observations([r for r in records if r["acquired_at"] >= dates["event_start"]])
        if not event_groups:
            result.update(status="waiting_for_data", reason="No suitable IW VV+VH event acquisitions in the requested time window.")
        context = None
        for obs in event_groups:
            key = comparison_key(obs["records"][0])
            baseline = [b for b in baseline_groups if comparison_key(b["records"][0]) == key]
            item = {"observation_id": obs["observation_id"], "acquired_at": obs["acquired_at"],
                    "scene_ids": [r["asset_id"] for r in obs["records"]],
                    "baseline_scene_ids": [r["asset_id"] for b in baseline for r in b["records"]],
                    "scene_acquisitions": [{"scene_id": r["asset_id"], "acquired_at": r["acquired_at"]} for r in obs["records"]],
                    "baseline_acquisitions": [{"observation_id": b["observation_id"], "acquired_at": b["acquired_at"]} for b in baseline],
                    "discarded_duplicate_scene_ids": obs["discarded_duplicate_scene_ids"] + [s for b in baseline for s in b["discarded_duplicate_scene_ids"]],
                    "comparison": {"mode": key[0], "relative_orbit": key[1], "direction": key[2],
                                   "polarizations": list(key[3]), "platform": key[4]},
                    "layers": [], "status": "waiting_for_data", "reason": None,
                    "quality": {"valid_coverage_pct": None, "warnings": list(LIMITATIONS)}}
            result["observations"].append(item)
            if len(baseline) < options["min_baseline_observations"]:
                item["reason"] = "Insufficient comparable baseline acquisitions; extend baseline_start or review the minimum baseline setting."
                continue
            try:
                if context is None:
                    context = load_context(event, dates, grid, options)
                    result["configuration"]["landcover"] = context["landcover_info"]
                shadow_path = options["shadow_masks"].get(obs["observation_id"])
                shadow = read_shadow(shadow_path, grid) if shadow_path else None
                primary = analyze_band(event, obs, baseline, grid, context, options, options["band"], shadow)
                stack, mask, valid, raw, flags, diagnostics = (
                    primary[k] for k in ("stack", "mask", "valid", "raw", "flags", "quality"))
                settings = primary["settings"]
                bands = {options["band"]: primary}
                band_error = None
                if options["compare_bands"]:
                    other = "VH" if options["band"] == "VV" else "VV"
                    try:
                        bands[other] = analyze_band(event, obs, baseline, grid, context, options, other, shadow)
                    except Exception as error:
                        band_error = f"{other} comparison processing failed: {type(error).__name__}: {error}"
                comparison = compare_masks(bands["VV"], bands["VH"], context["limitations"]) if len(bands) == 2 else None
                item["band_comparison"] = comparison[3] if comparison else {
                    "status": "failed" if band_error else "not_requested", "reason": band_error}
                item["band_results"] = {
                    band: {"quality": bundle["quality"], "effective_settings": {
                        **bundle["settings"], "water_db": bundle["quality"]["threshold"]["water_db"],
                        "threshold_method": bundle["quality"]["threshold"]["used_method"]},
                        "valid_pixel_count": int(bundle["valid"].sum()),
                        "potential_flood_pixel_count": int((bundle["mask"] == 1).sum())}
                    for band, bundle in bands.items()}
                item["quality"]["landcover"] = context["landcover_info"]
                water_valid = grid["inside"] & np.isfinite(stack[5]) & np.isin(stack[5], [1, 2, 3])
                water_available = bool(water_valid.any())
                water_missing = bool((grid["inside"] & ~water_valid).any())
                item["effective_settings"] = {**settings, "water_db": diagnostics["threshold"]["water_db"],
                                               "threshold_method": diagnostics["threshold"]["used_method"]}
                item["quality"].update(diagnostics)
                item["quality"]["filters"] = {
                    "permanent_water": {
                        "requested": options["use_permanent_water"],
                        "applied": options["use_permanent_water"] and water_available,
                        "fully_screened_aoi": options["use_permanent_water"] and not water_missing,
                        "reference_coverage_pct": float(100 * water_valid.sum() / grid["inside"].sum()) if options["use_permanent_water"] else None,
                        "policy": options["missing_water_policy"],
                    },
                    "slope": {"applied": options["use_dem"], "max_degrees": options["max_slope_degrees"]},
                    "shadow": {"applied": shadow is not None},
                    "speckle": {"method": options["speckle_filter"], "window": options["lee_window"], "enl": options["lee_enl"]},
                    "patch": {"min_area_m2": options["min_patch_area_m2"], "connectivity": 4},
                }
                coverage = float(100 * valid.sum() / grid["inside"].sum())
                issues = []
                if band_error:
                    issues.append(band_error)
                if comparison is not None and comparison[3]["status"] == "unavailable":
                    issues.append(comparison[3]["reason"])
                if options["use_landcover"] and context["landcover_info"]["status"] != "available":
                    issues.append(context["landcover_info"]["reason"])
                item["quality"]["warnings"].append("Urban/vegetation context flags are not flood labels or accuracy estimates; no detection there is inconclusive.")
                for band, bundle in bands.items():
                    if band != options["band"]:
                        if bundle["quality"]["threshold"]["fallback_reason"]:
                            issues.append(f"{band}: " + bundle["quality"]["threshold"]["fallback_reason"])
                        if bundle["quality"]["valid_coverage_pct"] < 99:
                            issues.append(f"{band} comparison has incomplete valid coverage; unknown pixels are excluded from agreement.")
                        if not bundle["quality"]["meets_min_coverage"]:
                            issues.append(f"{band} comparison is below the configured coverage threshold.")
                if shadow is None:
                    issues.append("No observation-specific radar shadow/layover mask supplied; slope masking does not replace it.")
                if options["use_permanent_water"] and water_missing:
                    if options["missing_water_policy"] == "partial":
                        issues.append("Water reference is incomplete; known water is excluded, but radar-valid pixels without a reference remain unscreened under partial policy. See quality_flags.tif.")
                    else:
                        issues.append("Water reference is incomplete; missing-reference pixels remain unknown under strict policy.")
                elif not options["use_permanent_water"]:
                    issues.append("Permanent-water exclusion disabled by configuration.")
                if options["use_permanent_water"]:
                    item["quality"]["warnings"].append("JRC yearly water is a historical 30 m reference; it can miss new water bodies and seasonal water.")
                if diagnostics["threshold"]["fallback_reason"]:
                    issues.append(diagnostics["threshold"]["fallback_reason"])
                if options["use_dem"]:
                    item["quality"]["warnings"].append("Copernicus DEM is a surface model including buildings and vegetation; slope exclusion may remove urban pixels.")
                if options["speckle_filter"] != "none" or options["min_patch_area_m2"] > 0:
                    item["quality"]["warnings"].append("Filtering can remove small or narrow flooded features; compare raw and cleaned masks. Filter settings require validation.")
                if not options["use_dem"]:
                    issues.append("Steep-terrain exclusion disabled.")
                if coverage < 99.0:
                    issues.append("Analysis does not cover the entire AOI; missing/excluded pixels must remain unknown.")
                if coverage < options["min_coverage_pct"]:
                    issues.append("Valid analysis coverage is below the configured usability threshold.")
                item["quality"].update(valid_coverage_pct=coverage,
                                       meets_min_coverage=coverage >= options["min_coverage_pct"],
                                       coverage_denominator="AOI grid cells, including excluded permanent water and terrain",
                                       valid_pixel_count=int(valid.sum()),
                                       potential_flood_pixel_count=int((mask == 1).sum()),
                                       shadow_mask_path=shadow_path)
                item["quality"]["warnings"].extend(issues)
                if not any(bundle["valid"].any() for bundle in bands.values()):
                    item.update(status="waiting_for_data", reason="No valid comparable analysis pixels; no flood conclusion can be drawn.")
                else:
                    item.update(status="partial" if issues else "ready", reason=" ".join(issues) or None)
                folder = root / obs["observation_id"]
                item["layers"] = export_observation(folder, stack, mask, valid, grid, obs, settings, raw=raw, quality_flags=flags)
                for layer in item["layers"]:
                    layer.update(band=options["band"], primary=True)
                for band, bundle in bands.items():
                    if band != options["band"]:
                        extra = export_observation(folder / band.lower(), bundle["stack"], bundle["mask"],
                            bundle["valid"], grid, obs, bundle["settings"], raw=bundle["raw"], quality_flags=bundle["flags"])
                        for layer in extra:
                            layer.update(band=band, primary=False)
                        item["layers"].extend(extra)
                item["layers"].extend(export_context_layers(folder, grid, obs, context["limitations"], context["landcover_info"], comparison))
                item["metadata_path"] = str(folder / "metadata.json")
                write_json(item["metadata_path"], {**item, "configuration": result["configuration"],
                                                   "analysis_grid": result["analysis_grid"], "pipeline_version": VERSION})
            except Exception as error:
                item.update(status="failed", reason=f"{type(error).__name__}: {error}", layers=[])
        if event_groups:
            states = [o["status"] for o in result["observations"]]
            usable = any(s in ("ready", "partial") for s in states)
            if all(s == "ready" for s in states):
                result.update(status="ready", reason=None)
            elif usable:
                result.update(status="partial", reason="Some observations have incomplete coverage, missing safeguards, or failed processing; inspect observation reasons.")
            elif "failed" in states:
                result.update(status="failed", reason="No usable observation was produced; inspect observation errors.")
            else:
                result.update(status="waiting_for_data", reason="No usable baseline/event comparison; inspect observation reasons.")
    except Exception as error:
        result.update(status="failed", reason=f"{type(error).__name__}: {error}")
    if result.get("manifest_path"):
        try:
            write_json(result["manifest_path"], result)
        except OSError as error:
            result.update(status="failed", reason=f"Cannot save manifest: {error}")
    return result
