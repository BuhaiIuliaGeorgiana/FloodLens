"""Pipeline Sentinel-1 pentru un eveniment ales de utilizator."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import uuid
import numpy as np

from . import earth_engine as backend
from .core import validate, make_grid, group_observations, comparison_key, classify, utc
from .outputs import write_json, read_shadow, export_observation

VERSION = "0.1.1"
LIMITATIONS = [
    "Experimental open-water change detector; thresholds are not validated universally.",
    "Urban flooding and water beneath vegetation can be missed; bright double-bounce flooding is not detected.",
    "Wind, soil moisture, farming and speckle can cause false detections or missed flooding.",
    "10 m grid spacing is not 10 m effective radar resolution.",
    "Earth Engine GRD is calibrated terrain-corrected sigma0 in dB, not radiometrically terrain-flattened data.",
    "No spatial speckle filter or minimum patch filter is applied in this first version.",
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
                                   "spatial_speckle_filter": None,
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
                stack = backend.download_stack(backend.build_stack(event, obs, baseline, grid, options), grid)
                shadow_path = options["shadow_masks"].get(obs["observation_id"])
                shadow = read_shadow(shadow_path, grid) if shadow_path else None
                # Optiunile efective apartin doar acestei observatii.
                effective = dict(options)
                water_valid = grid["inside"] & np.isfinite(stack[5]) & np.isin(stack[5], [1, 2, 3])
                water_available = bool(water_valid.any())
                skipped_missing_water = (
                    options["use_permanent_water"] and not water_available
                    and options["missing_water_policy"] == "partial"
                )
                if skipped_missing_water:
                    effective["use_permanent_water"] = False
                item["effective_settings"] = effective
                item["quality"]["filters"] = {
                    "permanent_water": {
                        "requested": options["use_permanent_water"],
                        "applied": effective["use_permanent_water"] and water_available,
                        "reference_coverage_pct": (
                            float(100 * water_valid.sum() / grid["inside"].sum())
                            if options["use_permanent_water"] else None
                        ),
                        "policy": options["missing_water_policy"],
                    },
                    "slope": {"applied": options["use_dem"]},
                    "shadow": {"applied": shadow is not None},
                }
                mask, valid = classify(stack, grid["inside"], effective, shadow)
                coverage = float(100 * valid.sum() / grid["inside"].sum())
                issues = []
                if shadow is None:
                    issues.append("No observation-specific radar shadow/layover mask supplied; slope masking does not replace it.")
                if skipped_missing_water:
                    issues.append("Permanent-water reference has no usable AOI pixels; exclusion skipped under partial policy. Existing water may be included.")
                elif options["use_permanent_water"] and not water_available:
                    issues.append("Permanent-water reference has no usable AOI pixels; strict policy retains unknown analysis pixels.")
                elif not options["use_permanent_water"]:
                    issues.append("Permanent-water exclusion disabled by configuration.")
                else:
                    item["quality"]["warnings"].append("JRC yearly water is a historical 30 m reference; it can miss new water bodies and seasonal water.")
                if not options["use_dem"]:
                    issues.append("Steep-terrain exclusion disabled.")
                if coverage < 99.0:
                    issues.append("Analysis does not cover the entire AOI; missing/excluded pixels must remain unknown.")
                if coverage < options["min_coverage_pct"]:
                    issues.append("Valid analysis coverage is below the configured usability threshold.")
                item["quality"].update(valid_coverage_pct=coverage,
                                       coverage_denominator="AOI grid cells, including excluded permanent water and terrain",
                                       valid_pixel_count=int(valid.sum()),
                                       potential_flood_pixel_count=int((mask == 1).sum()),
                                       shadow_mask_path=shadow_path)
                item["quality"]["warnings"].extend(issues)
                if not valid.any():
                    item.update(status="waiting_for_data", reason="No valid comparable analysis pixels; no flood conclusion can be drawn.")
                else:
                    item.update(status="partial" if issues else "ready", reason=" ".join(issues) or None)
                folder = root / obs["observation_id"]
                item["layers"] = export_observation(folder, stack, mask, valid, grid, obs, options)
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
