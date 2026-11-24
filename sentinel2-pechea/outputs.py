import os
import json
import ee

def export_image_to_local_geotiff(image: ee.Image, aoi: ee.Geometry, filepath: str, scale: int = 10, crs: str = "EPSG:4326"):
    """Downloads an Earth Engine image directly to a local GeoTIFF file via download URL."""
    url = image.getDownloadURL({
        'region': aoi,
        'scale': scale,
        'crs': crs,
        'format': 'GEO_TIFF'
    })
    import requests
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                f.write(chunk)
    else:
        raise RuntimeError(f"Failed to download image from Earth Engine: {response.text}")

def export_mask_to_geojson(mask: ee.Image, aoi: ee.Geometry, filepath: str, scale: int = 10, crs: str = "EPSG:4326"):
    """Converts a binary mask (1 = water) to GeoJSON polygons and saves locally."""
    vectors = mask.selfMask().reduceToVectors(
        geometry=aoi,
        crs=crs,
        scale=scale,
        geometryType="polygon",
        eightConnected=False,
        labelProperty="flooded",
        maxPixels=1e8
    )
    geojson_dict = vectors.getInfo()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(geojson_dict, f, indent=2)