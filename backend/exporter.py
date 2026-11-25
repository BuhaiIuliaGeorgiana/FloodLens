import mimetypes
from pathlib import Path
from .supabase_client import get_existing_layer_keys, upload_file, insert_event_layer


def _content_type(path: Path) -> str:
    if path.suffix.lower() == ".geojson":
        return "application/geo+json"
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def export_results(event_id: str, run_id: str, slug: str, result: dict) -> int:
    source = result.get("source", "unknown")
    existing = get_existing_layer_keys(event_id)
    saved_count = 0

    observations = result.get("observations") or []

    if not observations and result.get("status") in ("waiting_for_data", "failed"):
        key = (source, None, "status")
        if key not in existing:
            insert_event_layer({
                "event_id": event_id,
                "run_id": run_id,
                "source": source,
                "period": "post",
                "layer_type": "status",
                "kind": "metadata",
                "status": "unavailable",
                "reason": result.get("reason") or "No usable data available yet.",
                "storage_path": None,
                "acquired_at": None,
                "bounds": None,
            })
        return 0

    for obs in observations:
        acquired_at = obs.get("acquired_at")
        date_folder = (acquired_at or "unknown")[:10] 
        files = obs.get("layers") or obs.get("files") or []

        for item in files:
            layer_type = item.get("type") or item.get("layer_type") or "layer"
            local_path = Path(item["path"])
            key = (source, acquired_at, layer_type)

            if key in existing or not local_path.exists():
                continue

            storage_path = f"{slug}/{source}/{date_folder}/{local_path.name}"
            upload_file(local_path, storage_path, _content_type(local_path))

            insert_event_layer({
                "event_id": event_id,
                "run_id": run_id,
                "source": source,
                "period": "post",
                "layer_type": layer_type,
                "kind": item.get("kind") or local_path.suffix.lstrip("."),
                "status": "available",
                "reason": None,
                "storage_path": storage_path,
                "acquired_at": acquired_at,
                "bounds": item.get("bounds"),
            })
            existing.add(key)
            saved_count += 1

    return saved_count