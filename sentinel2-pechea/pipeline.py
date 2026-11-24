import os
import json
import ee
from typing import Dict, Any

from .earth_engine import init_earth_engine, search_s2_scenes, select_best_scene
from .core import mask_s2_clouds, calculate_water_indices, compute_rgb, detect_water_change
from .outputs import export_image_to_local_geotiff, export_mask_to_geojson

def process_sentinel2(event: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    Processes a generic flood event using Sentinel-2 multispectral imagery.

    :param event: Dictionary containing event metadata, geometry, and date windows:
                  {
                    "id": "event_id",
                    "project_id": "optional-gcp-project-id",
                    "geometry": [[[lon, lat], ...]], # GeoJSON Polygon coordinates or bbox
                    "before_start": "YYYY-MM-DD",
                    "before_end": "YYYY-MM-DD",
                    "during_start": "YYYY-MM-DD",
                    "during_end": "YYYY-MM-DD",
                    "crs": "EPSG:32635", # optional
                    "scale": 10
                  }
    :param output_dir: Local path where rasters, vectors, and summary.json will be saved.
    :return: Dictionary containing execution status, metadata, and local file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Initialize Earth Engine
    project_id = event.get("project_id", None)
    init_earth_engine(project_id)
    
    # Parse Geometry & Grid
    geom_type = event.get("geometry_type", "Polygon")
    coords = event["geometry"]
    if geom_type == "BBOX":
        aoi = ee.Geometry.Rectangle(coords)
    else:
        aoi = ee.Geometry.Polygon(coords)
        
    scale = event.get("scale", 10)
    crs = event.get("crs", "EPSG:4326")
    
    # 2. Search Scenes
    before_col = search_s2_scenes(aoi, event["before_start"], event["before_end"])
    during_col = search_s2_scenes(aoi, event["during_start"], event["during_end"])
    
    before_scene = select_best_scene(before_col, aoi)
    during_scene = select_best_scene(during_col, aoi)
    
    # Check for missing data
    if before_scene is None or during_scene is None:
        missing_period = []
        if before_scene is None: missing_period.append("BEFORE")
        if during_scene is None: missing_period.append("DURING")
        
        status_payload = {
            "status": "NO_DATA",
            "message": f"No usable Sentinel-2 cloud-free scenes found for period(s): {', '.join(missing_period)}. Note: Absence of clear observation does not imply absence of flood.",
            "event_id": event.get("id"),
            "files": {},
            "metadata": None
        }
        with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(status_payload, f, indent=2)
        return status_payload

    # Extract metadata details
    before_info = {
        "id": before_scene.get("system:index").getInfo(),
        "date_utc": before_scene.date().format("yyyy-MM-dd HH:mm:ss", "UTC").getInfo(),
        "cloud_cover_pct": before_scene.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    }
    during_info = {
        "id": during_scene.get("system:index").getInfo(),
        "date_utc": during_scene.date().format("yyyy-MM-dd HH:mm:ss", "UTC").getInfo(),
        "cloud_cover_pct": during_scene.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    }
    
    # 3. Processing & Masking
    before_masked = mask_s2_clouds(before_scene)
    during_masked = mask_s2_clouds(during_scene)
    
    # Valid observation mask (where pixels are NOT masked by clouds)
    valid_mask = during_masked.select("SCL").mask().rename("valid_mask")
    
    # Calculate coverage ratio of valid non-cloudy area over the AOI
    stats = valid_mask.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e8
    ).getInfo()
    analyzable_area_pct = round((stats.get("valid_mask", 0) or 0) * 100, 2)

    # Calculate Indices & RGB
    before_indices = calculate_water_indices(before_masked)
    during_indices = calculate_water_indices(during_masked)
    
    during_rgb = compute_rgb(during_masked)
    during_ndwi = during_indices.select("NDWI")
    during_mndwi = during_indices.select("MNDWI")
    
    # Detect Flooded Water
    flood_mask = detect_water_change(
        before_indices.select("MNDWI"),
        during_indices.select("MNDWI")
    )
    
    # 4. Save Outputs Locally
    rgb_path = os.path.join(output_dir, "true_colour.tif")
    ndwi_path = os.path.join(output_dir, "ndwi.tif")
    mndwi_path = os.path.join(output_dir, "mndwi.tif")
    valid_mask_path = os.path.join(output_dir, "valid_mask.tif")
    flood_mask_path = os.path.join(output_dir, "flood_mask.tif")
    geojson_path = os.path.join(output_dir, "flood_extent.geojson")
    summary_path = os.path.join(output_dir, "summary.json")

    export_image_to_local_geotiff(during_rgb.clip(aoi), aoi, rgb_path, scale=scale, crs=crs)
    export_image_to_local_geotiff(during_ndwi.clip(aoi), aoi, ndwi_path, scale=scale, crs=crs)
    export_image_to_local_geotiff(during_mndwi.clip(aoi), aoi, mndwi_path, scale=scale, crs=crs)
    export_image_to_local_geotiff(valid_mask.clip(aoi), aoi, valid_mask_path, scale=scale, crs=crs)
    export_image_to_local_geotiff(flood_mask.clip(aoi), aoi, flood_mask_path, scale=scale, crs=crs)
    export_mask_to_geojson(flood_mask.clip(aoi), aoi, geojson_path, scale=scale, crs=crs)

    metadata = {
        "event_id": event.get("id"),
        "sensor": "Sentinel-2 L2A",
        "analyzable_area_pct": analyzable_area_pct,
        "scenes": {
            "before": before_info,
            "during": during_info
        }
    }

    result_payload = {
        "status": "SUCCESS",
        "message": "Sentinel-2 flood analysis completed successfully.",
        "event_id": event.get("id"),
        "files": {
            "true_colour": rgb_path,
            "ndwi": ndwi_path,
            "mndwi": mndwi_path,
            "valid_mask": valid_mask_path,
            "flood_mask": flood_mask_path,
            "flood_extent_geojson": geojson_path
        },
        "metadata": metadata
    }

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    return result_payload