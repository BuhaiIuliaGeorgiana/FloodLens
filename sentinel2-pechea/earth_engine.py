import ee
from typing import Optional

def init_earth_engine(project_id: Optional[str] = None) -> None:
    """
    Initializes Google Earth Engine.
    Passes project_id if provided, otherwise attempts default initialization.
    """
    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
    except Exception:
        # Prompt authentication if initialization fails
        ee.Authenticate()
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()

def search_s2_scenes(
    aoi: ee.Geometry, 
    start_date: str, 
    end_date: str, 
    max_cloud_cover: float = 80
) -> ee.ImageCollection:
    """
    Searches Sentinel-2 L2A HARMONIZED collection for a given spatial ROI and timeframe.
    Filters by max cloud percentage and selects key spectral bands + Scene Classification Layer (SCL).
    """
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover))
        .select(["B2", "B3", "B4", "B8", "B11", "SCL"])
        .sort("system:time_start")
    )

def select_best_scene(collection: ee.ImageCollection, aoi: ee.Geometry) -> Optional[ee.Image]:
    """
    Selects the image with the lowest cloud cover percentage covering the AOI.
    Returns None if no matching scene exists in the collection.
    """
    size = collection.size().getInfo()
    if size == 0:
        return None
    sorted_col = collection.sort("CLOUDY_PIXEL_PERCENTAGE")
    
    return ee.Image(sorted_col.first())

def get_scene_metadata(image: Optional[ee.Image]) -> Optional[dict]:
    """
    Extracts metadata from a Sentinel-2 image for the summary.json payload.
    """
    if image is None:
        return None
    return {
        "id": image.get("system:index").getInfo(),
        "date_utc": image.date().format("yyyy-MM-dd HH:mm:ss", "UTC").getInfo(),
        "cloud_cover_pct": image.get("CLOUDY_PIXEL_PERCENTAGE").getInfo(),
        "mgrs_tile": image.get("MGRS_TILE").getInfo()
    }