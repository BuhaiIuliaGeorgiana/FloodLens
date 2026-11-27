import mimetypes
from pathlib import Path
from .supabase_client import get_existing_layer_keys, upload_file, insert_event_layer


def _content_type(path: Path) -> str:
    if path.suffix.lower() == ".geojson":
        return "application/geo+json"
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"

def _infer_kind(path: Path | None = None, source: str = "") -> str:
    if path is not None:
        if path.suffix.lower() in (".geojson", ".json"):
            return "geojson"
        return "image"
    return "image" if source in ("sentinel1", "sentinel2") else "geojson"

def _default_layer_type(source: str) -> str:
    if source in ("sentinel1", "sentinel2"):
        return "satellite_image"
    if source == "osm":
        return "buildings"
    return "flood_extent"

ALLOWED_LAYER_TYPES = {
    "satellite_image",
    "flood_extent",
    "buildings",
    "roads",
    "ems_reference",
}


def _normalize_layer_type(raw_type: str | None, source: str, kind: str) -> str:
    raw = (raw_type or "").lower()
    if raw in ALLOWED_LAYER_TYPES:
        return raw
    if "building" in raw:
        return "buildings"
    if "road" in raw:
        return "roads"
    if "ems" in raw:
        return "ems_reference"
    if any(word in raw for word in ("flood", "mask", "water", "change", "evolution")):
        return "flood_extent"
    if source in ("sentinel1", "sentinel2") and kind == "image":
        return "satellite_image"
    return _default_layer_type(source)
def export_results(
    event_id: str,
    run_id: str,
    slug: str,
    result: dict,
    default_bounds: list[float] | None = None,
) -> int:
    source = result.get("source", "unknown")
    existing = get_existing_layer_keys(event_id)
    saved_count = 0

    observations = _extract_observations(result)

    if not observations and result.get("status") in ("waiting_for_data", "failed"):
        default_type = _default_layer_type(source)
        key = (source, None, default_type)
        if key not in existing:
            insert_event_layer({
                "event_id": event_id,
                "run_id": run_id,
                "source": source,
                "period": None,
                "layer_type": default_type,
                "kind": _infer_kind(source=source),
                "status": "unavailable",
                "reason": result.get("reason") or "No usable data available yet.",
                "storage_path": None,
                "acquired_at": None,
                "bounds": None,
            })
        return 0

    for obs in observations:
        acquired_at = obs.get("acquired_at")
        date_folder = str(acquired_at)[:10] if acquired_at else "unknown"
        files = obs.get("files") or []

        for item in files:
            file_path = item.get("path") or item.get("local_path")
            if not file_path:
                continue
            local_path = Path(file_path)
            if not local_path.exists():
                continue

            kind = (
                item.get("kind")
                if item.get("kind") in ("image", "geojson")
                else _infer_kind(local_path, source)
            )
            raw_layer_type = item.get("layer_type") or item.get("type") or local_path.stem
            layer_type = _normalize_layer_type(raw_layer_type, source, kind)
            key = (source, acquired_at, layer_type)

            if key in existing:
                continue

            bounds = item.get("bounds")
            if kind == "image" and not bounds:
                bounds = default_bounds

            storage_path = f"{slug}/{source}/{date_folder}/{local_path.name}"
            upload_file(local_path, storage_path, _content_type(local_path))

            insert_event_layer({
                "event_id": event_id,
                "run_id": run_id,
                "source": source,
                "period": item.get("period") if item.get("period") in ("before", "during", "after") else "during",
                "layer_type": layer_type,
                "kind": kind,
                "status": "available",
                "reason": None,
                "storage_path": storage_path,
                "acquired_at": acquired_at,
                "bounds": bounds,
            })
            existing.add(key)
            saved_count += 1

    return saved_count

def _extract_observations(result: dict) -> list[dict]:
    """Normalize S1 (observations/layers), S2 (files dict), and OSM (files list)."""
    if result.get("observations"):
        normalized = []
        for obs in result["observations"]:
            files = obs.get("files") or obs.get("layers") or []
            normalized.append({
                "acquired_at": obs.get("acquired_at"),
                "files": files,
            })
        return normalized

    top_files = result.get("files")
    if isinstance(top_files, dict) and top_files:
        files = [{"layer_type": k, "path": v} for k, v in top_files.items() if isinstance(v, str)]
        return [{"acquired_at": None, "files": files}]
    if isinstance(top_files, list) and top_files:
        return [{"acquired_at": None, "files": top_files}]

    return []