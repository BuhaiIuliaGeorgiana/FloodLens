import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import (
    calculate_default_transform,
    reproject,
    Resampling,
    transform_bounds,
)
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image


# Find folders relative to this script, regardless of terminal location.
sentinel2_folder = Path(__file__).resolve().parents[1]
data_folder = sentinel2_folder / "data" / "pechea"
output_folder = sentinel2_folder / "export" / "pechea"
output_folder.mkdir(parents=True, exist_ok=True)

input_file = data_folder / "after_mndwi.tif"
output_file = output_folder / "s2_after_mndwi.png"

with rasterio.open(input_file) as source:
    # Read the first band. Each pixel contains an MNDWI value.
    values = source.read(1).astype("float32")

    # Missing pixels can be marked by a mask, NaN, or NoData.
    invalid = (source.read_masks(1) == 0) | ~np.isfinite(values)

    if source.nodata is not None:
        invalid |= values == source.nodata

    values[invalid] = np.nan

    # Leaflet's standard web map uses Web Mercator.
    target_crs = "EPSG:3857"

    transform, width, height = calculate_default_transform(
        source.crs,
        target_crs,
        source.width,
        source.height,
        *source.bounds,
    )

    projected = np.full((height, width), np.nan, dtype="float32")

    # Move the raster onto the web map's coordinate grid.
    reproject(
        source=values,
        destination=projected,
        src_transform=source.transform,
        src_crs=source.crs,
        src_nodata=np.nan,
        dst_transform=transform,
        dst_crs=target_crs,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )


# Convert the output image's bounds back to longitude/latitude.
projected_bounds = rasterio.transform.array_bounds(
    height, width, transform
)

bounds = list(
    transform_bounds(
        target_crs,
        "EPSG:4326",
        *projected_bounds,
    )
)

# Use this same colour scale for after/during/after previews.
minimum, maximum = -0.5, 0.5

colour_map = LinearSegmentedColormap.from_list(
    "water_index",
    ["brown", "yellow", "cyan", "blue"],
)

valid = np.isfinite(projected)

# Scale values to 0–1 for the colour map.
scaled = np.zeros_like(projected)
scaled[valid] = np.clip(
    (projected[valid] - minimum) / (maximum - minimum),
    0,
    1,
)

# RGBA means red, green, blue, and transparency.
rgba = colour_map(scaled, bytes=True)
rgba[~valid, 3] = 0

Image.fromarray(rgba).save(output_file)


# Read the real acquisition date from your colleague's metadata.
summary = json.loads(
    (data_folder / "summary.json").read_text(encoding="utf-8")
)

layer = {
    "id": "s2_after_mndwi",
    "source": "Sentinel-2",
    "period": "after",
    "type": "image",
    "url": "/data/pechea/s2_after_mndwi.png",
    "bounds": bounds,
    "acquired_at_utc": summary["scenes"]["after"]["acquired_at_utc"],
    "status": "available",
}

metadata_file = output_folder / "s2_after_mndwi.json"
metadata_file.write_text(
    json.dumps(layer, indent=2),
    encoding="utf-8",
)

print("Image saved:", output_file)
print("Metadata saved:", metadata_file)
print("Bounds [west, south, east, north]:", bounds)