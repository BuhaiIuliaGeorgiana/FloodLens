from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, STORAGE_BUCKET
from pathlib import Path
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_event(event_id: str) -> dict | None:
    res = (
        supabase.table("flood_events")
        .select("id, slug, title, started_at, ended_at, aoi_geojson, visibility, created_by")
        .eq("id", event_id)
        .maybe_single()
        .execute()
    )
    return res.data


def create_pipeline_run(event_id: str) -> str:
    res = (
        supabase.table("pipeline_runs")
        .insert({"event_id": event_id, "status": "queued", "source_status": {}})
        .execute()
    )
    return res.data[0]["id"]


def update_pipeline_run(
    run_id: str,
    *,
    status: str | None = None,
    source_status: dict[str, str] | None = None,
    message: str | None = None,
) -> None:
    payload = {}
    if status is not None:
        payload["status"] = status
    if source_status is not None:
        payload["source_status"] = source_status
    if message is not None:
        payload["message"] = message
    if payload:
        supabase.table("pipeline_runs").update(payload).eq("id", run_id).execute()

def get_existing_layer_keys(event_id: str) -> set[tuple[str, str|None,str]]:
    res = (
        supabase.table("event_layers")
        .select("source, acquired_at, layer_type")
        .eq("event_id", event_id)
        .execute()
    )
    return {
        (row["source"], row.get("acquired_at"), row["layer_type"]) for row in (res.data or [])
    }

def upload_file(local_path: Path, storage_path: str, content_type: str = "application/octet-stream") -> str:
    with open(local_path, "rb") as f:
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=f,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    return storage_path

def insert_event_layer(layer_row: dict) -> None:
    supabase.table("event_layers").insert(layer_row).execute()

