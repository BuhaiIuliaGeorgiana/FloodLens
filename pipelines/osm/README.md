# OSM + exposure (`pipelines/osm/`)

> Everything here is **potential exposure at 10 m resolution, not confirmed damage.**


## How it fits in the pipeline

```
event (id, polygon, start date)  ->  run_event_pipeline
   |- process_sentinel1  -> flood GeoJSON
   |- process_sentinel2  -> flood GeoJSON
   |- fetch_osm          -> buildings.geojson, roads.geojson        (this module, once per event)
   |- calculate_exposure -> exposed_*.geojson, exposure_summary     (this module, once per source)
```

This module only takes inputs and writes files. It does not touch Supabase, Storage, or the processing button; the coordinator calls it.

## Folder

```
pipelines/osm/
  __init__.py        exports fetch_osm, calculate_exposure, OsmDataError, make_file
  config.py          settings only (paths, Microsoft index URL, road classes, thresholds)
  geo_utils.py       OsmDataError, make_file, event polygon parsing, GeoJSON read/write
  sources.py         reads Geofabrik roads and Microsoft building tiles
  fetch_osm.py       fetch_osm(event, output_dir)
  exposure.py        calculate_exposure(event, observation, osm_data, output_dir)
  dev_run.py         local test: Pechea + a fake flood
  dev_run_ems.py     local test: Pechea + a real flood file (e.g. the EMS flood extent)
  requirements.txt
  tests/test_exposure.py
```

## Data sources

| Data | Source | Notes |
|---|---|---|
| Roads | OpenStreetMap, from the **Geofabrik Romania extract** (`gis_osm_roads_free_1.shp`) | Not the Overpass API: it failed repeatedly (502). It is the same OSM data. |
| Buildings | **Microsoft Global ML Building Footprints** | OSM has almost no buildings around Pechea. A footprint is a roofed structure (house, barn, shed), **not a household**. |



### Setup

1. Python environment (from the repo root):
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   pip install -r pipelines/osm/requirements.txt
   ```
2. Download the Romania extract (`.shp.zip`) from <https://download.geofabrik.de> (Europe > Romania), unzip it to `data/raw/romania/`.
   On a server, put it anywhere persistent (about 2 GB) and set `OSM_GEOFABRIK_DIR`.
3. Nothing to do for buildings: the Microsoft tiles are downloaded at the first run and cached in `data/raw/cache/`.

**Do not commit** `data/raw/` (Geofabrik, cache) or test outputs. They are in `.gitignore`.

### Settings (`config.py`)

| Setting | Default | Meaning |
|---|---|---|
| `OSM_GEOFABRIK_DIR` (env) | `data/raw/romania` | Folder with the unzipped Geofabrik files |
| `OSM_CACHE_DIR` (env) | `data/raw/cache` | Cache for Microsoft tiles and index |
| `MS_BUILDINGS_INDEX_URL` (env) | see file | Microsoft `dataset-links.csv`. **The URL moves over time.** Check the README of `microsoft/GlobalMLBuildingFootprints` if the download fails. |
| `REAL_ROADS` | motorway ... service | Road classes with `is_real_road = True`. Tracks, paths and footways are `False`. |
| `MOSTLY_FLOODED_PCT` | 50 | A building is "mostly flooded" at this % of its footprint under water |
| `MEASURE_CRS` | 3844 | Lengths and areas are measured in Romania Stereo 70 (metres). Outside Romania, local UTM is used. Files are stored in EPSG:4326. |

## Usage

```python
from pipelines.osm import fetch_osm, calculate_exposure

osm = fetch_osm(event, output_dir / "osm")                       # once per event
exp = calculate_exposure(event, s1_result, osm,
                         output_dir / "exposure" / "sentinel1")  # once per source
```

Use a **separate output folder per run and per source**, e.g. `outputs/<event_id>/<run_id>/<source>/`. Files are named by source but not by run, so the same folder is overwritten.

### `fetch_osm(event, output_dir)`

- **Input:** `event` with the polygon (GeoJSON, EPSG:4326) under one of `polygon`, `geometry`, `geojson`, `aoi_geojson`, `aoi`. Geometry, Feature and FeatureCollection are accepted, as dict or JSON string.
- **What it does:** reads only the event area from the Geofabrik file; clips roads to the polygon (cut at the edge); keeps **whole** building footprints that touch the polygon; adds `is_real_road` to roads.
- **Cache:** if the same polygon was already fetched (`osm_meta.json`), it returns the saved files without downloading.
- **Output files:** `buildings.geojson`, `roads.geojson`, `osm_meta.json` (an empty layer is still a valid, empty FeatureCollection).
- **Returns:** `{"status": "ready", "cached": bool, "buildings": path, "roads": path, "counts": {...}, "files": [...]}`
- **Errors:** raises `OsmDataError` (missing Geofabrik file, download failure, no polygon). The coordinator should mark OSM as `failed` with the message.

### `calculate_exposure(event, observation, osm_data, output_dir)`

- **Input:**
  - `observation`: one result from S1 or S2. Accepted as returned: S1 `observations[*].layers` (`layer_type`, `local_path`), S2 `files` dict (`flood_extent_geojson`), or a generic `files: [{type, path}]`. With several observations, the **latest** is used.
  - `osm_data`: the dict returned by `fetch_osm`.
- **Flood file:** the file whose type contains `flood` and ends in `.geojson`. A valid-area file (type containing `valid`, e.g. S1 `valid_coverage`) is used if present. S2 has none, so `valid_area_ha` is `null` there.
- **What it does:** cuts the flood to the valid area and the event polygon, reprojects to metres, then:
  1. **Buildings:** counts those touched by the flood and those at least 50% under water; adds `overlap_pct` and `mostly_flooded`.
  2. **Roads:** cuts the lines to the flood, sums the length in km, real roads separately.
  3. **Area:** flooded area in hectares.
- **Output files** (the source is in the name, so S1 and S2 stay separate):
  `exposed_buildings_<source>.geojson`, `exposed_roads_<source>.geojson`, `exposure_summary_<source>.json`
- **Returns:** `{"status", "summary", "files"}` where `status` is:

  | status | When |
  |---|---|
  | `ready` | Calculated. No flooded area gives zeros with `flood_detected: false`. |
  | `skipped` | Observation status is not `ready` or `partial`, or no flood GeoJSON is in it. `reason` explains. |
  | `failed` | The flood file has no CRS and non-lon/lat coordinates. `reason` explains. |

### Summary example (`exposure_summary_<source>.json`)

```json
{
  "event_id": "…",
  "source": "sentinel1",
  "observation_date": "2024-09-15",
  "flood_detected": true,
  "buildings_exposed": 1200,
  "buildings_mostly_flooded": 950,
  "mostly_flooded_threshold_pct": 50,
  "buildings_total": 11780,
  "roads_exposed_km": 12.3,
  "roads_real_exposed_km": 11.8,
  "roads_total_km": 154.5,
  "flooded_area_ha": 850.0,
  "valid_area_ha": null,
  "note": "Potential exposure at 10 m resolution, not confirmed damage."
}
```

(Illustrative values.) `buildings_exposed` = any overlap with the flood; `buildings_mostly_flooded` = at least `MOSTLY_FLOODED_PCT` of the footprint.

### File records

Every returned file has the same shape, so the export step can upload all of them the same way:

```json
{"type": "exposed_buildings", "layer_type": "exposed_buildings", "path": "...", "bounds": [west, south, east, north]}
```

Types: `osm_buildings`, `osm_roads`, `exposed_buildings`, `exposed_roads`, `exposure_summary` (JSON, not a spatial layer). `type` is the pipeline name; `layer_type` is the same value for the database column.

## Testing

```
python -m pytest pipelines/osm/tests                                    # made-up data, no downloads
python -m pipelines.osm.dev_run                                         # Pechea + a fake flood rectangle
```

`dev_run*.py` contain a hardcoded Pechea box on purpose: they are only test scripts. The pipeline functions never contain coordinates.
QGIS: exposed buildings must lie only under the flood.

## Limits

- 10 m flood maps show flooded or not, not the level of damage.
- Footprints are estimated from imagery and include sheds and outbuildings, so counts are structures, not households or homes.
- A building touching the flood edge counts as exposed; use `overlap_pct` / `buildings_mostly_flooded` for a stricter count.
- OSM is a snapshot from the Geofabrik file date, not from the flood date.
- Only Romania is covered (Geofabrik extract and `MS_COUNTRY = "Romania"`); a polygon outside returns empty layers.
- S1 and S2 flood maps may come from different days; each source is calculated separately.