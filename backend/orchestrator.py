import importlib
import os
from datetime import datetime, timedelta, timezone
from shapely.geometry import shape

from .config import OUTPUT_DIR
from .exporter import export_results
from .supabase_client import get_event, update_pipeline_run

from sentinel1.pipeline import process_sentinel1
from pipelines.osm.fetch_osm import fetch_osm
from pipelines.osm.exposure import calculate_exposure

_s2_module = importlib.import_module("sentinel2-pechea.pipeline")
process_sentinel2 = _s2_module.process_sentinel2


def _utm_crs_from_aoi(aoi: dict) -> str:
    coords = aoi["coordinates"][0][0]  # [lon, lat]
    lon, lat = coords[0], coords[1]
    zone = int((lon + 180) // 6) + 1
    prefix = 326 if lat >= 0 else 327
    return f"EPSG:{prefix}{zone:02d}"


def build_pipeline_event(db_event: dict) -> dict:
    event_start = datetime.fromisoformat(db_event["started_at"].replace("Z", "+00:00"))
    baseline_start = event_start - timedelta(days=45)

    if db_event.get("ended_at"):
        search_end = datetime.fromisoformat(db_event["ended_at"].replace("Z", "+00:00"))
    else:
        search_end = datetime.now(timezone.utc)

    aoi = db_event["aoi_geojson"]

    return {
        # Sentinel-1 & OSM keys
        "event_id": db_event["id"],
        "id": db_event["id"],
        "slug": db_event["slug"],
        "aoi": aoi,
        "baseline_start": baseline_start.isoformat().replace("+00:00", "Z"),
        "event_start": event_start.isoformat().replace("+00:00", "Z"),
        "search_end": search_end.isoformat().replace("+00:00", "Z"),
        "grid": {
            "crs": _utm_crs_from_aoi(aoi),
            "resolution": 10,
            "origin": [0, 0],
        },
        # Sentinel-2 keys
        "project_id": os.getenv("EE_PROJECT"),
        "before_start": baseline_start.strftime("%Y-%m-%d"),
        "before_end": event_start.strftime("%Y-%m-%d"),
        "during_start": event_start.strftime("%Y-%m-%d"),
        "during_end": search_end.strftime("%Y-%m-%d"),
    }


def _compute_overall_status(source_status: dict[str, str]) -> str:
    states = list(source_status.values())
    if not states:
        return "failed"
    if all(s == "ready" for s in states):
        return "ready"
    if any(s in ("ready", "partial") for s in states):
        return "partial"
    if any(s == "failed" for s in states):
        return "failed"
    return "waiting_for_data"


def _run_safely(name: str, fn, event: dict, output_dir: str, source_status: dict, run_id: str) -> dict:
    source_status[name] = "processing"
    update_pipeline_run(run_id, source_status=source_status)
    try:
        res = fn(event, output_dir)
        raw_status = res.get("status", "failed")
        status_map = {"SUCCESS": "ready", "NO_DATA": "waiting_for_data"}
        normalized = status_map.get(raw_status, raw_status)
        res["status"] = normalized
        res.setdefault("source", name)
        source_status[name] = normalized
        return res
    except Exception as error:
        print(f"[{name} FAILED] {error}")
        source_status[name] = "failed"
        return {
            "event_id": event["event_id"],
            "source": name,
            "status": "failed",
            "reason": str(error),
            "observations": [],
        }
    finally:
        update_pipeline_run(run_id, source_status=source_status)


def _run_exposure(event: dict, observations: list[dict], osm_result: dict, out_dir: str, source_status: dict, run_id: str) -> list[dict]:
    if osm_result.get("status") != "ready" or not observations:
        return []

    source_status["exposure"] = "processing"
    update_pipeline_run(run_id, source_status=source_status)
    exposure_results = []

    try:
        for obs in observations:
            exp = calculate_exposure(event, obs, osm_result, out_dir)
            if isinstance(exp, dict):
                exp.setdefault("source", "exposure")
                exposure_results.append(exp)
        source_status["exposure"] = "ready" if exposure_results else "waiting_for_data"
    except Exception as error:
        source_status["exposure"] = "failed"
        exposure_results.append({
            "event_id": event["event_id"],
            "source": "exposure",
            "status": "failed",
            "reason": str(error),
            "observations": [],
        })
    finally:
        update_pipeline_run(run_id, source_status=source_status)

    return exposure_results


def run_event_pipeline(event_id: str, run_id: str) -> None:
    update_pipeline_run(run_id, status="processing")

    try:
        db_event = get_event(event_id)
        if not db_event:
            update_pipeline_run(run_id, status="failed", message="Event not found.")
            return

        event = build_pipeline_event(db_event)
        aoi_bounds = list(shape(event["aoi"]).bounds)
        out_dir = str(OUTPUT_DIR / event["slug"])
        source_status: dict[str, str] = {}

        try:
            import ee
            ee.Initialize(project=os.getenv("EE_PROJECT"))
        except Exception as exc:
            print(f"[EE init skipped] {exc}")

        s2_event = {
            **event,
            "geometry_type": event["aoi"].get("type", "Polygon"),
            "geometry": event["aoi"].get("coordinates"),
        }
        
        s1_result = _run_safely("sentinel1", process_sentinel1, event, out_dir, source_status, run_id)
        s2_result = _run_safely("sentinel2", process_sentinel2, s2_event, out_dir, source_status, run_id)
        osm_result = _run_safely("osm", fetch_osm, event, out_dir, source_status, run_id)



        all_observations = (s1_result.get("observations") or []) + (s2_result.get("observations") or [])
        exposure_results = None
        exposure_results = _run_exposure(event, all_observations, osm_result, out_dir, source_status, run_id)
        for res in [s1_result, s2_result, osm_result, *exposure_results]:
            if res:
                export_results(
                    event_id,
                    run_id,
                    event["slug"],
                    res,
                    default_bounds=aoi_bounds,
                )
        for res in (s1_result, s2_result, osm_result, *exposure_results):
            if res:
                export_results(
                    event_id,
                    run_id,
                    event["slug"],
                    res,
                    default_bounds=aoi_bounds,
                )
        final_status = _compute_overall_status(source_status)
        update_pipeline_run(run_id, status=final_status, source_status=source_status)

    except Exception as error:
        update_pipeline_run(run_id, status="failed", message=str(error))