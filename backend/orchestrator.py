from datetime import datetime, timedelta, timezone
from .supabase_client import update_pipeline_run, get_event
from .config import OUTPUT_DIR
from .stubs import process_sentinel2, fetch_osm
from sentinel1.pipeline import process_sentinel1
from .exporter import export_results


def _utm_crs_from_aoi(aoi: dict) -> str:
    #Pick the right UTM ESPG code from the first polygon point.
    coords = aoi["coordinates"][0][0]
    lon, lat = coords[0], coords[1]
    zone = int((lon + 180) / 6) + 1
    prefix = 326 if lat >= 0 else 327
    return f"EPSG:{prefix}{zone:02d}"

def build_pipeline_event(db_event: dict) ->dict:
    #translate flood_events DB row into the dict expexted by s1/s2/osm
    event_start = datetime.fromisoformat(db_event["started_at"].replace("Z", "+00:00"))
    baseline_start = event_start - timedelta(days=45)
    #ongoing event
    if db_event.get("ended_at"):
        search_end = datetime.fromisoformat(db_event["ended_at"].replace("Z", "+00:00"))
    else:
        search_end = datetime.now(timezone.utc)
    aoi = db_event["aoi_geojson"]
    return {
        "event_id": db_event["id"],
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

def _run_safely(name: str, fn, event:dict, output_dir: str, source_status: dict, run_id: str) -> dict:
    source_status[name] = "processing"
    update_pipeline_run(run_id, source_status=source_status)
    try: 
        res = fn(event, output_dir)
        source_status[name] = res.get("status", "failed")
        return res
    except Exception as e:
        source_status[name] = "failed"
        return {"event_id": event["event_id"], "source": name, "status": "failed", "reason": str(e), "observations": []}
    finally:
        update_pipeline_run(run_id, source_status=source_status)


def run_event_pipeline(event_id: str, run_id: str):
    update_pipeline_run(run_id, status="processing")
    try:
        db_event = get_event(event_id)
        if not db_event:
            update_pipeline_run(run_id, status="failed", message="Event not found")
            return
        event = build_pipeline_event(db_event)
        out_dir = str(OUTPUT_DIR / event["slug"])
        source_status: dict[str, str] = {}

        s1_result = _run_safely("sentinel1", process_sentinel1, event, out_dir, source_status, run_id)
        s2_result = _run_safely("sentinel2", process_sentinel2, event, out_dir, source_status, run_id)
        osm_result = _run_safely("osm", fetch_osm, event, out_dir, source_status, run_id)

        for res in (s1_result, s2_result, osm_result):
            export_results(event_id, run_id, event["slug"], res)

        final_status = _compute_overall_status(source_status)
        update_pipeline_run(run_id, status=final_status, source_status=source_status)
    except Exception as e:
        update_pipeline_run(run_id, status="failed", message=str(e))