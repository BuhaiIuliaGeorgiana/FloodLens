# Reusable Sentinel-1 event pipeline

`from sentinel1 import process_sentinel1`

```python
result = process_sentinel1(event: dict, output_dir: str)
```

This first implementation detects **potential open-water flooding** using backscatter changes. It is not a validated damage or insurance-loss model. It generates local files and metadata only. No scheduler, Supabase upload, database write or frontend change is included.

## What changed from the existing code

Inspected repository main at `81e291e`. The existing `sentinel1_pechea (2).py` is a Colab export: it has fixed dates/coordinates/project ID, authenticates on execution, discovers unrelated orbits together and saves previews. It does not calculate flood extent. That demo is preserved.

The new files form an importable Python package:

| File | Responsibility |
| --- | --- |
| `core.py` | Validate input, construct the shared grid, group acquisitions, classify pixels |
| `earth_engine.py` | Discover scenes, build comparable baseline/event images, download aligned tiles |
| `outputs.py` | Write GeoTIFF, geographic GeoJSON, web PNG and JSON |
| `pipeline.py` | Coordinate the steps and return the shared result |
| `run.py` | Example command-line caller; handles authentication outside the function |
| `tests/test_pipeline.py` | Synthetic local and offline Earth Engine tests |

## Water-reference fallback (version 0.1.1)

`event["sentinel1"]["missing_water_policy"]` defaults to `"partial"`. When water exclusion is requested but the downloaded reference has no usable AOI pixels (classes 1, 2 or 3), processing continues without that exclusion and explicitly returns partial with a warning. Use `"strict"` to retain unknown analysis in that situation. Partial reference gaps remain unknown when any usable reference coverage exists. Missing radar and baseline data always remain unknown. Authentication/network/export errors are not converted to a missing-reference fallback.

The manifest keeps requested configuration. Each observation records `effective_settings` plus `quality.filters` with the requested/applied water filter, reference coverage and policy. A disabled filter does not label missing reference data as dry land.

## 1. Install and authenticate

Run from the repository root in PowerShell, using your existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\sentinel1\requirements.txt
.\.venv\Scripts\python.exe -m pytest .\sentinel1\tests -q
```

Python 3.10+ is required; local verification used Python 3.12. Dependencies include Earth Engine, NumPy, Rasterio, Shapely, PyProj, Pillow, Requests and Pytest. Dependencies of these packages are installed by pip. `requirements-tested.txt` records the direct versions tested here; it is not a full transitive lock file.

Use a Google Cloud project registered for Earth Engine, with the Earth Engine API enabled and your account granted access. Do not use the literal placeholder project ID. Authentication belongs to the caller:

```python
import ee

ee.Authenticate()  # Autentificare interactiva, la prima configurare.
ee.Initialize(project="YOUR_ACTUAL_PROJECT_ID")
```

A future worker should initialize with its own authorized credentials outside the function. Never embed keys in React or commit credential files.

## 2. Supply the event

```python
import json
from pathlib import Path
from sentinel1 import process_sentinel1

# Exemplu istoric pentru verificare, nu coordonate fixe in pipeline.
event = json.loads(Path("sentinel1/examples/pechea.json").read_text())
result = process_sentinel1(event, "outputs/sentinel1")
print(result["status"], result["reason"])
```

Or run the complete caller:

```powershell
.\.venv\Scripts\python.exe -m sentinel1.run --event .\sentinel1\examples\pechea.json --output .\outputs\sentinel1 --project YOUR_ACTUAL_PROJECT_ID --authenticate
```

After the first login, omit `--authenticate`. To use another event, supply another JSON file. `event_id` is an opaque string; the pipeline does not assume it is the old Pechea UUID.

Required input:

- `aoi`: a valid GeoJSON Polygon geometry, EPSG:4326, `[longitude, latitude]`. Holes are allowed; Features and MultiPolygons are not accepted in this version.
- `baseline_start`, `event_start`, `search_end`: ISO timestamps with timezone, normalized to UTC. A plain `YYYY-MM-DD` means midnight UTC. Naive date-time strings are rejected.
- `grid`: `{"crs": "EPSG:32635", "resolution": 10, "origin": [0, 0]}` in this example. The team must choose a suitable projected CRS with metre units for each event; EPSG:32635 is only the example's CRS. Origin is an alignment anchor, not necessarily the AOI's upper-left corner. All pipelines must use the same CRS, origin and resolution.

Date intervals are **[baseline_start, event_start)** and **[event_start, search_end)**. The lower boundary is inclusive and the upper boundary exclusive. For all of September 18, use `search_end` September 19 at midnight. The baseline never includes the event start instant.

For an ongoing event, update only `search_end` as appropriate, for example:

```python
from datetime import datetime, timezone

event["search_end"] = datetime.now(timezone.utc).isoformat()
result = process_sentinel1(event, "outputs/sentinel1")
```

There is no required after-flood image. This searches the catalogue as it exists at run time; acquisition and publication delays mean an ongoing event may return `waiting_for_data`.

## 3. Understand the processing

1. `validate` checks the event and settings before satellite calls.
2. `make_grid` projects the AOI and snaps its outer rectangle to the supplied 10 m grid. Pixel centres determine AOI membership; holes/outside pixels stay unknown. The GeoTIFF transform is recorded.
3. `discover` uses the existing Earth Engine source, `COPERNICUS/S1_GRD`. This implementation deliberately supports IW, 10 m spacing, VV+VH products. Other products return no suitable scenes, rather than being silently mixed.
4. `group_observations` combines slices only within the same platform, absolute orbit and datatake. It preserves individual scene times. Overlapping duplicate products with the same start time and slice use the lexically last asset ID; discarded IDs are recorded. This tie-break is deterministic, not a claim that this product is scientifically better.
5. Each event acquisition uses only baseline acquisitions with equal mode, relative orbit, direction, polarization set **and platform**. Same-platform matching is an extra conservative restriction; cross-platform calibration is outside this first version. Each pixel also needs the minimum number of baseline acquisitions and an acceptable incidence-angle difference.
6. Source images are aligned by nearest-neighbour sampling to the shared grid. A baseline median is computed in **linear power**, then converted back to dB. Each event acquisition is processed separately. Matching slices are mosaicked; different dates are never merged into one event image.
7. Classification uses the selected band. A valid pixel is potential flood when both `event_db <= water_db` and `baseline_db - event_db >= drop_db`. Example: baseline -10 dB, event -20 dB gives a 10 dB drop. Do not divide negative dB values. A 3 dB drop corresponds to approximately halving linear backscatter power.
8. Permanent water and steep terrain are excluded, and an optional observation-specific shadow/layover raster is applied. Missing auxiliary pixels remain unknown when that auxiliary filter is enabled.
9. Each observation produces separate outputs and provenance. Each run has a unique directory, so an interrupted rerun cannot overwrite a previous successful product. Only the returned manifest is authoritative; do not scan old output folders for the latest result.

Earth Engine S1 GRD already has orbit correction, noise handling, radiometric calibration and geometric terrain correction and is in dB. Do not calibrate it again or apply `10*log10` directly to its dB values. It is not radiometrically terrain-flattened data. We use `10 ** (dB / 10)` only for the baseline statistic, then return to dB. No additional spatial speckle filter is applied: the first version stays inspectable, but isolated noisy detections are a known limitation.

**10 m pixel spacing is not 10 m effective radar resolution.** Resampling or output grid size cannot recover finer physical detail. The 30 m auxiliaries also do not become 10 m observations when resampled.

## 4. Settings and auxiliary masks

Optional settings go in `event["sentinel1"]`; unknown setting names are rejected.

| Setting | Default | Meaning |
| --- | --- | --- |
| `band` | `VV` | Detection and preview band, `VV` or `VH` |
| `water_db` | -17 | Maximum event backscatter for a candidate |
| `drop_db` | 3 | Minimum decrease from baseline in dB |
| `min_baseline_observations` | 2 | Minimum distinct baseline acquisitions per pixel |
| `max_angle_difference` | 2 | Maximum absolute difference in incidence angle, degrees |
| `max_slope_degrees` | 5 | Exclude steeper pixels |
| `min_coverage_pct` | 20 | Flag observations below this usability threshold |
| `use_permanent_water` | true | Apply historical JRC water exclusion |
| `exclude_seasonal_water` | false | Also exclude JRC seasonal water if requested |
| `use_dem` | true | Apply Copernicus DEM slope exclusion |
| `shadow_masks` | `{}` | Map observation IDs to aligned local shadow/layover TIFFs |
| `max_pixels` | 5,000,000 | Memory guard for the AOI's bounding grid |

Thresholds are initial development values, not calibrated recommendations. Changing band to VH requires reconsidering thresholds; the VV defaults should not be assumed suitable. All effective settings are saved in the manifest and each successful observation's metadata.

Permanent water uses `JRC/GSW1_4/YearlyHistory`, taking `min(event year - 1, 2021)`. Class 3 is excluded; class 0/no data stays unknown. This avoids using an incomplete event year or water observations from the future. The old reference may miss new reservoirs, drainage changes and seasonal water. The chosen year is recorded as `water_reference_year`.

Slope uses `COPERNICUS/DEM/GLO30_2024_1` at 30 m in the processing CRS before sampling onto the shared grid. It is a static surface model (including structures/vegetation), not a contemporaneous ground survey. A slope cutoff is **not** geometric radar shadow/layover modelling.

To apply a shadow mask, supply a single-band GeoTIFF on exactly the generated grid: `0=clear`, `1=shadow or layover`, nodata=unknown. It must correspond to that observation's viewing geometry and should cover invalid geometry for both event and baseline. Get the stable observation IDs from a first run or from candidate orbit/datatake metadata, then rerun with:

```python
event["sentinel1"]["shadow_masks"] = {
    "s1_A_ABSOLUTEORBIT_DATATAKE": "path/to/observation_shadow.tif"
}
```

The pipeline does not generate a physical shadow mask from a DEM. Without one, it returns `partial` with a specific warning. Disabling either other auxiliary filter also produces `partial`. If an enabled auxiliary asset fails to download, that observation fails rather than silently dropping the filter. Urban and vegetated flooding, bright flood returns, rough water, agricultural change and residual speckle remain limitations even with all masks.

## 5. Files and result contract

The agreed top-level fields remain `event_id`, `source="sentinel1"`, `status`, `reason`, and `observations`. Additional fields provide provenance and integration detail.

Per successfully exported observation:

| File | Layer type | Notes |
| --- | --- | --- |
| `radar_vv.png` or `radar_vh.png` | `satellite_image` | Transparent outside valid radar coverage; Web Mercator raster with geographic bounding box |
| `flood_mask.tif` | `flood_mask` | Shared grid, uint8: 0=no detection, 1=potential flood, 255=unknown/excluded; nodata=255 |
| `flood_extent.geojson` | `flood_extent` | EPSG:4326 FeatureCollection of potential flood pixels |
| `valid_coverage.geojson` | `valid_coverage` | EPSG:4326 FeatureCollection of analysed pixels |
| `metadata.json` | separate `metadata_path` | Acquisition times, exact scene IDs, baseline IDs, configuration, grid, quality warnings |

The manifest also contains candidates and reasons for observations that could not be analysed. Those have no analytical outputs. A downloaded observation with zero valid coverage exports an all-nodata mask, empty coverage/flood collections and its radar preview, but its status is `waiting_for_data`, **not** a zero-flood result.

All layer `bounds` arrays use geographic `[west, south, east, north]`, including GeoTIFF bounds. Layer `crs` describes the actual raster/geometry CRS. PNGs use EPSG:3857; only their bounds are EPSG:4326. Leaflet converts them to `[[south,west],[north,east]]`. Preview coverage can exceed analysis coverage because a radar image may exist where baseline comparison is unavailable.

`valid_coverage_pct` = valid analysed AOI grid cells / all AOI grid cells × 100. The denominator includes permanent water and terrain exclusions. This is coverage, not accuracy or confidence. A valid zero-detection area remains in `valid_coverage.geojson`; missing areas do not.

| Status | Interpretation |
| --- | --- |
| `ready` | All returned observations usable, >=99% AOI analysis coverage, enabled safeguards applied and shadow masks supplied. Does not mean scientific validation. |
| `partial` | At least one usable observation, but missing safeguards, coverage exclusions, failed or unmatched observations exist. Inspect reasons. |
| `waiting_for_data` | No suitable event scenes, insufficient matching baseline, or zero analysable pixels. Extending search_end alone will not repair a missing baseline; review baseline_start. |
| `failed` | Invalid input, access/processing/export error with no usable result. With other successful observations, top-level status is partial. |

## 6. Short guide for the integrating teammate

- Initialize Earth Engine once in the Python worker; call this synchronous function outside the web request/UI thread.
- Supply the complete event and agreed grid; schedule repeated calls with updated `search_end` for an ongoing event.
- Read the manifest, not a folder glob. Upload files referenced by its observations and preserve their metadata. Keep paths relative to your chosen storage prefix in the database; `local_path` is a worker filesystem path, not a web URL.
- Upsert by `(event_id, source, observation_id, layer_type, band when present)`. Observation IDs stay stable across runs; run directories are unique. Preserve the old published run until a new run has uploaded successfully. Configuration/baseline changes can change historical results, so retain version provenance.
- Existing `event_layers` fields cannot store this whole contract: source currently uses `Sentinel-1`, image kind uses `image`, and the status constraint only has `available/unavailable`. Map source casing explicitly, use `image` for PNG and `geojson` for GeoJSON. Do not put processing status `partial` directly into that old constraint. Preserve processing status/reason/quality in a separate processing record or extend the schema deliberately.
- The current frontend only draws EMS GeoJSON plus satellite PNGs. It needs explicit support for Sentinel-1 `flood_extent` and `valid_coverage`; this function does not make those UI changes. GeoTIFF is an analysis/download product, not a Leaflet ImageOverlay URL. New layer types such as `valid_coverage` may require a database constraint update.
- Use actual `acquired_at` to show evolution. No `after` period is inferred. If the existing UI needs periods, all observations in this search window may be labelled `during`, with precise dates retained.
- Never show an empty flood collection as “no flood” without checking coverage and observation status. Label partial outputs, show coverage boundaries, and distinguish no detection from unavailable data.

## 7. Tests and remaining verification

Run `python -m pytest sentinel1/tests -q`. Tests cover input/date boundaries, grid alignment, orbit/polarization/platform separation, deduplication, configurable classification, unknown pixels, dry valid pixels, shadow checks, status transitions, independent observation failures, repeat runs, actual GeoTIFF/PNG/GeoJSON export, tiled download alignment, and offline Earth Engine graph serialization.

These use synthetic arrays or mocked remote responses. They do **not** prove real satellite access, live asset metadata availability, catalogue completeness, server execution, visual alignment on real scenes, or flood-detection accuracy. Credentials are not available in this environment, so no live satellite run was performed.

First live check: run the example on your account, inspect `candidates.json`, confirm matched baseline/event orbit metadata, verify TIFF CRS/transform/nodata in QGIS, overlay the PNG and both GeoJSON layers, and compare date-matched potential flood results against an independent reference. Assess commission and omission inside common valid coverage; do not tune and report accuracy on the same reference pixels.

Downloads are tiled into 512x512 requests to stay below EE's direct-download size limit. The local seven-band stack is held in memory; a 5-million-pixel bounding grid uses about 140 MB just for that stack, plus other arrays and geometry. Very large AOIs require partitioning or a future streaming/batch export implementation. Antimeridian-crossing, polar (outside +/-85 degrees), and invalid projected AOIs are rejected. Fine noisy masks can produce large GeoJSON files. This is a bounded first implementation, not an unrestricted global service.

## Official references and attribution

- [Earth Engine Sentinel-1 preprocessing and comparable subsets](https://developers.google.com/earth-engine/guides/sentinel1)
- [S1 GRD collection](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD)
- [Direct-download limits and transform parameters](https://developers.google.com/earth-engine/apidocs/ee-image-getdownloadurl)
- [Authentication and project setup](https://developers.google.com/earth-engine/guides/auth)
- [JRC yearly water classifications](https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_YearlyHistory)
- [Copernicus DEM 2024_1](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30_2024_1)

Satellite attribution: Copernicus Sentinel data. Water attribution: Source: EC JRC/Google; Pekel et al., Nature 540, 418–422 (2016), doi:10.1038/nature20584. DEM derivative attribution: produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30. Preserve the dataset notices when publishing derived layers.
