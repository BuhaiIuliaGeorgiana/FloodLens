def process_sentinel2(event: dict, output_dir: str) -> dict:
    """Temporary placeholder until Task 3 (Sentinel-2) is merged."""
    return {
        "event_id": event["event_id"],
        "source": "sentinel2",
        "status": "waiting_for_data",
        "reason": "Sentinel-2 pipeline not connected yet (stub).",
        "observations": [],
    }


def fetch_osm(event: dict, output_dir: str) -> dict:
    """Temporary placeholder until Task 4 (OSM) is merged."""
    return {
        "event_id": event["event_id"],
        "source": "osm",
        "status": "waiting_for_data",
        "reason": "OSM pipeline not connected yet (stub).",
        "files": [],
    }


def calculate_exposure(event: dict, observation: dict, osm_data: dict, output_dir: str) -> dict:
    """Temporary placeholder until Task 4 (exposure) is merged."""
    return {"status": "waiting_for_data", "files": []}