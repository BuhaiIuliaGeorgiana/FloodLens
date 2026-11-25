import os
import json
import pytest
from pathlib import Path
from typing import Dict, Any

from sentinel2 import process_sentinel2
from sentinel2.earth_engine import init_earth_engine


@pytest.fixture(scope="module")
def ee_initialized():
    """Ensures Earth Engine is initialized once for the test module."""
    init_earth_engine()


@pytest.fixture
def pechea_event_config() -> Dict[str, Any]:
    """Sample valid event configuration for Pechea, Galați flood testing."""
    return {
        "id": "test_pechea_s2_event",
        "name": "Pechea Sentinel-2 Validation Test",
        "geometry_type": "BBOX",
        "geometry": [27.74, 45.58, 27.86, 45.68],
        "before_start": "2024-08-15",
        "before_end": "2024-09-14",
        "during_start": "2024-09-14",
        "during_end": "2024-09-20",
        "crs": "EPSG:32635",
        "scale": 10,
        "max_cloud_cover": 80
    }


@pytest.fixture
def polygon_event_config() -> Dict[str, Any]:
    """Sample event configuration using GeoJSON Polygon coordinates."""
    return {
        "id": "test_polygon_s2_event",
        "geometry_type": "Polygon",
        "geometry": [
            [
                [27.74, 45.58],
                [27.86, 45.58],
                [27.86, 45.68],
                [27.74, 45.68],
                [27.74, 45.58]
            ]
        ],
        "before_start": "2024-08-15",
        "before_end": "2024-09-14",
        "during_start": "2024-09-14",
        "during_end": "2024-09-20",
        "crs": "EPSG:32635",
        "scale": 10
    }


# ==============================================================================
# 1. SUCCESSFUL PIPELINE EXECUTION TESTS
# ==============================================================================

def test_process_sentinel2_e2e_bbox(pechea_event_config, tmp_path, ee_initialized):
    """Tests complete end-to-end processing for a BBOX event."""
    output_dir = str(tmp_path / "s2_bbox_output")
    
    result = process_sentinel2(pechea_event_config, output_dir)
    
    # 1. Check Root Response Payload
    assert isinstance(result, dict)
    assert result["status"] in ["SUCCESS", "NO_DATA"]
    assert result["event_id"] == pechea_event_config["id"]
    
    summary_path = os.path.join(output_dir, "summary.json")
    assert os.path.exists(summary_path)

    if result["status"] == "SUCCESS":
        # 2. Check File Map Completeness
        files = result["files"]
        expected_keys = [
            "true_colour",
            "ndwi",
            "mndwi",
            "valid_mask",
            "flood_mask",
            "flood_extent_geojson"
        ]
        for key in expected_keys:
            assert key in files, f"Missing key '{key}' in result files payload"
            assert os.path.exists(files[key]), f"Output file does not exist: {files[key]}"

        # 3. Validate GeoJSON Structure
        geojson_path = files["flood_extent_geojson"]
        with open(geojson_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)
        assert geojson_data.get("type") == "FeatureCollection"
        assert "features" in geojson_data

        # 4. Validate Metadata Schema
        metadata = result["metadata"]
        assert metadata["event_id"] == pechea_event_config["id"]
        assert metadata["sensor"] == "Sentinel-2 L2A"
        assert "analyzable_area_pct" in metadata
        assert isinstance(metadata["analyzable_area_pct"], (int, float))
        assert 0.0 <= metadata["analyzable_area_pct"] <= 100.0

        # Validate Scenes Details
        scenes = metadata["scenes"]
        assert "before" in scenes and "during" in scenes
        for period in ["before", "during"]:
            assert "id" in scenes[period]
            assert "date_utc" in scenes[period]
            assert "cloud_cover_pct" in scenes[period]


def test_process_sentinel2_polygon_geometry(polygon_event_config, tmp_path, ee_initialized):
    """Tests execution using complex GeoJSON Polygon coordinate arrays."""
    output_dir = str(tmp_path / "s2_polygon_output")
    
    result = process_sentinel2(polygon_event_config, output_dir)
    
    assert result["status"] in ["SUCCESS", "NO_DATA"]
    assert result["event_id"] == polygon_event_config["id"]
    assert os.path.exists(os.path.join(output_dir, "summary.json"))


# ==============================================================================
# 2. NO DATA & CLOUD COVER FALLBACK TESTS
# ==============================================================================

def test_process_sentinel2_no_data_historical_range(tmp_path, ee_initialized):
    """
    Tests graceful fallback when querying date ranges prior to Sentinel-2 launch.
    Ensures clear output explaining lack of data rather than throwing an exception.
    """
    no_data_event = {
        "id": "no_data_test_1995",
        "geometry_type": "BBOX",
        "geometry": [27.74, 45.58, 27.86, 45.68],
        "before_start": "1995-01-01",
        "before_end": "1995-01-15",
        "during_start": "1995-01-16",
        "during_end": "1995-01-31",
        "crs": "EPSG:32635",
        "scale": 10
    }
    
    output_dir = str(tmp_path / "s2_nodata_output")
    result = process_sentinel2(no_data_event, output_dir)
    
    # Assert return contract
    assert result["status"] == "NO_DATA"
    assert "No usable Sentinel-2 cloud-free scenes" in result["message"]
    assert result["files"] == {}
    assert result["metadata"] is None
    
    # Verify summary.json is still generated explaining the failure
    summary_file = os.path.join(output_dir, "summary.json")
    assert os.path.exists(summary_file)
    with open(summary_file, "r", encoding="utf-8") as f:
        summary_content = json.load(f)
    assert summary_content["status"] == "NO_DATA"


def test_process_sentinel2_missing_during_scene(tmp_path, ee_initialized):
    """Tests handling when baseline scene exists but event window has no clear observations."""
    partial_data_event = {
        "id": "partial_missing_event",
        "geometry_type": "BBOX",
        "geometry": [27.74, 45.58, 27.86, 45.68],
        "before_start": "2024-08-15",  # Valid period
        "before_end": "2024-09-14",
        "during_start": "1999-01-01",  # Invalid period
        "during_end": "1999-01-05",
        "crs": "EPSG:32635",
        "scale": 10
    }
    
    output_dir = str(tmp_path / "s2_partial_nodata")
    result = process_sentinel2(partial_data_event, output_dir)
    
    assert result["status"] == "NO_DATA"
    assert "DURING" in result["message"]


# ==============================================================================
# 3. DIRECTORY & SUMMARY OUTPUT VALIDATION
# ==============================================================================

def test_summary_json_integrity(pechea_event_config, tmp_path, ee_initialized):
    """Validates that summary.json written on disk matches the returned payload."""
    output_dir = str(tmp_path / "s2_summary_test")
    
    result = process_sentinel2(pechea_event_config, output_dir)
    summary_path = os.path.join(output_dir, "summary.json")
    
    with open(summary_path, "r", encoding="utf-8") as f:
        file_summary = json.load(f)
        
    assert file_summary["status"] == result["status"]
    assert file_summary["event_id"] == result["event_id"]
    assert file_summary["message"] == result["message"]