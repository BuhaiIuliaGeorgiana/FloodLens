# Sentinel-2 Multispectral Flood Analysis Pipeline

A modular, generic Python pipeline for satellite-based flood monitoring and water surface detection using **Sentinel-2 L2A Multispectral Imagery** on **Google Earth Engine (GEE)**.

This module provides cloud/shadow masking, dual water index processing (**NDWI** and **MNDWI**), change detection, clear observation mask computation, and standardized outputs (GeoTIFFs, GeoJSON, and metadata JSON) ready for web integration.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Directory Structure](#-directory-structure)
- [Key Features](#-key-features)
- [Installation & Requirements](#-installation--requirements)
- [Authentication](#-authentication)
- [Pipeline Architecture & Workflow](#-pipeline-architecture--workflow)
- [Input Specification (`event`)](#-input-specification-event)
- [Output Files & Schema](#-output-files--schema)
- [Usage Examples](#-usage-examples)
  - [Python API](#1-python-api)
  - [Running with a JSON Event File](#2-running-with-a-json-event-file)
- [Error Handling & NO_DATA Fallbacks](#-error-handling--no_data-fallbacks)
- [Testing](#-testing)

---

## 🛰️ Overview

While Sentinel-1 Synthetic Aperture Radar (SAR) sees through clouds, **Sentinel-2 L2A (Bottom-Of-Atmosphere / Surface Reflectance)** optical imagery provides crucial complementary data:
1. **True Color RGB Visualization:** Provides immediate visual verification for frontend web maps.
2. **Spectral Water Indices:** 
   * **NDWI** (Normalized Difference Water Index): Uses native 10m Green ($B3$) and NIR ($B8$) bands.
   * **MNDWI** (Modified Normalized Difference Water Index): Uses Green ($B3$) and SWIR-1 ($B11$) resampled to 10m to suppress false-positive urban and building shadow noise.
3. **Cloud & Shadow Filtering:** Employs the 20m Scene Classification Layer (**SCL**) to filter out clouds, cirrus, and cloud shadows, calculating a clear **analyzable area percentage** over the Area of Interest (AOI).

---

## 📁 Directory Structure

```text
sentinel2/
├── __init__.py                # Module export for process_sentinel2
├── core.py                    # Spectral index math, cloud masking, and change detection
├── earth_engine.py            # Earth Engine authentication and collection search
├── outputs.py                 # Local GeoTIFF downloaders and GeoJSON vector reducers
├── pipeline.py                # Main orchestration pipeline process_sentinel2(event, output_dir)
├── requirements.txt           # Core Python dependencies
├── requirements-demo.txt      # Lightweight demo UI dependencies
├── requirements-tested.txt    # Fully tested, pinned dependency versions
├── README.md                  # Module documentation
├── examples/
│   └── pechea.json            # Example configuration for Pechea, Galați event
└── tests/
    └── test_pipeline.py       # Pytest unit and integration test suite
```

---

## ✨ Key Features

* **Generic Event Execution:** Operates on any user-defined GeoJSON `BBOX` or `Polygon` and timeframe without hardcoded coordinates.
* **Automated Cloud & Shadow Masking:** Uses `SCL` band filtering (excluding classes 3, 8, 9, 10) to ensure high-confidence pixel evaluation.
* **Dual Index Comparison:** Generates both NDWI and MNDWI rasters to support open-field and urban flood analysis.
* **Unified 10m CRS Grid:** Reprojects all rasters to a consistent metric coordinate system (e.g., `EPSG:32635` for UTM Zone 35N) at a 10m pixel size.
* **Analyzable Area Metric:** Reports the percentage of AOI pixels unmasked by clouds to quantify dataset reliability.
* **Graceful NO_DATA Contracts:** Handles missing or heavily clouded scenes by outputting a structured `NO_DATA` `summary.json` payload, ensuring absence of imagery is not confused with absence of flooding.

---

## 📦 Installation & Requirements

### Dependencies

Install core dependencies via `pip`:

```bash
pip install -r sentinel2/requirements.txt
```

#### `requirements.txt`
```text
earthengine-api>=0.1.350
requests>=2.28.0
pytest>=7.0.0
```

---

## 🔑 Authentication

Before running the pipeline, ensure your Google Earth Engine account is authenticated:

```bash
earthengine authenticate
```

Or pass your Google Cloud Platform project ID directly inside the `event` payload:
```python
event = {
    "project_id": "your-gcp-project-id",
    # ...
}
```

---

## 🔄 Pipeline Architecture & Workflow

```text
               +-----------------------------------+
               | Input Event Dict / pechea.json   |
               +-----------------------------------+
                                 |
                                 v
               +-----------------------------------+
               | 1. GEE Collection Query           |
               | (S2_SR_HARMONIZED + SCL Filter)   |
               +-----------------------------------+
                                 |
                +----------------+----------------+
                |                                 |
                v                                 v
      [ Baseline Scene ]                 [ Event Scene ]
                |                                 |
                +----------------+----------------+
                                 |
                                 v
               +-----------------------------------+
               | 2. Cloud Masking & Index Math     |
               |    - SCL Mask (3, 8, 9, 10)       |
               |    - NDWI  = (B3 - B8) / (B3 + B8)|
               |    - MNDWI = (B3 - B11)/(B3 + B11)|
               +-----------------------------------+
                                 |
                                 v
               +-----------------------------------+
               | 3. Change Detection & Masking     |
               |    - MNDWI_during > 0.1           |
               |    - (MNDWI_dur - MNDWI_bef) > 0.2|
               +-----------------------------------+
                                 |
                                 v
               +-----------------------------------+
               | 4. Local Export & Vectorization   |
               |    - GeoTIFF Rasters (10m)        |
               |    - GeoJSON Flood Extent         |
               |    - summary.json Metadata        |
               +-----------------------------------+
```

---

## 📝 Input Specification (`event`)

The `process_sentinel2(event, output_dir)` function accepts a dictionary with the following schema:

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | `str` | **Yes** | Unique identifier for the flood event. |
| `geometry_type` | `str` | **Yes** | Either `"BBOX"` `[west, south, east, north]` or `"Polygon"` `[[[lon, lat], ...]]`. |
| `geometry` | `list` | **Yes** | Bounding box coordinates or array of polygon vertices. |
| `before_start` | `str` | **Yes** | Start date for baseline search (`YYYY-MM-DD`). |
| `before_end` | `str` | **Yes** | End date for baseline search (`YYYY-MM-DD`). |
| `during_start` | `str` | **Yes** | Start date for event search (`YYYY-MM-DD`). |
| `during_end` | `str` | **Yes** | End date for event search (`YYYY-MM-DD`). |
| `crs` | `str` | No | Target EPSG projection code (default: `"EPSG:4326"`). |
| `scale` | `int` | No | Spatial resolution in meters (default: `10`). |
| `project_id` | `str` | No | Optional GCP project ID for Earth Engine initialization. |

---

## 📤 Output Files & Schema

Upon successful execution, the specified `output_dir` will contain the following files:

```text
output_dir/
├── true_colour.tif
├── ndwi.tif
├── mndwi.tif
├── valid_mask.tif
├── flood_mask.tif
├── flood_extent.geojson
└── summary.json
```

### File Details

1. **`true_colour.tif`**: 8-bit 3-band RGB GeoTIFF ($B4, B3, B2$) scaled to 0–255 for web display.
2. **`ndwi.tif`**: 32-bit floating point GeoTIFF containing native 10m NDWI values.
3. **`mndwi.tif`**: 32-bit floating point GeoTIFF containing resampled 10m MNDWI values.
4. **`valid_mask.tif`**: Binary raster (1 = clear observation, 0 = cloud/shadow/cirrus).
5. **`flood_mask.tif`**: Binary raster (1 = newly flooded candidate pixel, 0 = non-flooded).
6. **`flood_extent.geojson`**: GeoJSON FeatureCollection containing vectorized flood polygons.
7. **`summary.json`**: Execution summary and scene metadata payload.

### Example `summary.json` Output

```json
{
  "status": "SUCCESS",
  "message": "Sentinel-2 flood analysis completed successfully.",
  "event_id": "pechea_flood_2024_09",
  "files": {
    "true_colour": "output_pechea/true_colour.tif",
    "ndwi": "output_pechea/ndwi.tif",
    "mndwi": "output_pechea/mndwi.tif",
    "valid_mask": "output_pechea/valid_mask.tif",
    "flood_mask": "output_pechea/flood_mask.tif",
    "flood_extent_geojson": "output_pechea/flood_extent.geojson"
  },
  "metadata": {
    "event_id": "pechea_flood_2024_09",
    "sensor": "Sentinel-2 L2A",
    "analyzable_area_pct": 94.25,
    "scenes": {
      "before": {
        "id": "COPERNICUS/S2_SR_HARMONIZED/20240830T084551_20240830T085848_T35TML",
        "date_utc": "2024-08-30 08:45:51",
        "cloud_cover_pct": 2.14
      },
      "during": {
        "id": "COPERNICUS/S2_SR_HARMONIZED/20240914T084549_20240914T085844_T35TML",
        "date_utc": "2024-09-14 08:45:49",
        "cloud_cover_pct": 14.82
      }
    }
  }
}
```

---

## 💻 Usage Examples

### 1. Python API

```python
import json
from sentinel2 import process_sentinel2

# Define generic event payload
event = {
    "id": "pechea_2024",
    "geometry_type": "BBOX",
    "geometry": [27.74, 45.58, 27.86, 45.68],
    "before_start": "2024-08-15",
    "before_end": "2024-09-14",
    "during_start": "2024-09-14",
    "during_end": "2024-09-20",
    "crs": "EPSG:32635",
    "scale": 10
}

# Run processing
output_folder = "output_sentinel2_pechea"
result = process_sentinel2(event, output_folder)

print("Status:", result["status"])
print("Analyzable Area (%):", result["metadata"]["analyzable_area_pct"])
```

### 2. Running with a JSON Event File

```python
import json
from sentinel2 import process_sentinel2

# Load event configuration from disk
with open("sentinel2/examples/pechea.json", "r") as f:
    event_config = json.load(f)

# Execute pipeline
result = process_sentinel2(event_config, output_dir="./results_json_test")
```

---

## ⚠️ Error Handling & NO_DATA Fallbacks

If no cloud-free scene is available for either the `BEFORE` or `DURING` period, the pipeline catches the missing scene gracefully, writes a `summary.json` file explaining the missing data, and returns without raising an uncaught exception:

```json
{
  "status": "NO_DATA",
  "message": "No usable Sentinel-2 cloud-free scenes found for period(s): DURING. Note: Absence of clear observation does not imply absence of flood.",
  "event_id": "pechea_heavy_clouds",
  "files": {},
  "metadata": null
}
```

---

## 🧪 Testing

The unit test suite validates end-to-end execution, BBOX vs. Polygon parsing, GeoJSON vector generation, schema validity, and historical date range fallbacks.

To run all tests:

```bash
pytest sentinel2/tests/test_pipeline.py -v
```