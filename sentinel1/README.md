# Reusable Sentinel-1 event pipeline

`from sentinel1 import process_sentinel1`

```python
result = process_sentinel1(event, output_dir)
```

Version 0.3.0 detects **potential open-water flooding** using backscatter changes. It is not a validated damage or insurance-loss model. It generates local files and metadata only. Primary outputs still follow `band`; comparison products are additional outputs. No scheduler, Supabase upload, database write or frontend change is included.

## What changed from the existing code

Inspected repository main at `81e291e`. The existing `sentinel1_pechea (2).py` is a Colab export: it has fixed dates/coordinates/project ID, authenticates on execution, discovers unrelated orbits together and saves previews. It does not calculate flood extent. That demo is preserved.

The new files form an importable Python package:

| File | Responsibility |
| --- | --- |
| `core.py` | Validate input, construct the shared grid, group acquisitions, classify pixels |
| `earth_engine.py` | Discover scenes, build comparable baseline/event images, download aligned tiles |
| `comparison.py` | Buffered sampling, separate VV/VH analysis, agreement and land-cover context |
| `analysis.py` | Optional tile Otsu, patch removal, quality flags and coverage diagnostics |
| `diagnose_water.py` | Optional live native/grid water-reference diagnostic |
| `outputs.py` | Write GeoTIFF, geographic GeoJSON, web PNG and JSON |
| `pipeline.py` | Coordinate the steps and return the shared result |
| `run.py` | Example command-line caller; handles authentication outside the function |
| `tests/test_pipeline.py` | Synthetic local and offline Earth Engine tests |

## Research-based changes (versions 0.2.0–0.3.0)

The callable interface is unchanged. The implementation adds:

- **Pixel-wise water-reference policy.** Under `partial`, known permanent water is still excluded, but otherwise valid radar pixels with missing reference data remain analysable and explicitly unscreened. Under `strict`, those pixels remain unknown. Missing reference values are never relabelled as known dry land. This fixes the former fallback that only worked at exactly zero reference coverage.
- **Simplified Lee filtering in linear power**, separately on each aligned acquisition before the temporal baseline median. The original radar mask is preserved; filtering never creates observations inside nodata holes. Default: a 5×5 window and assumed ENL 4.4. This is a conventional local Lee formulation, not Refined Lee, and the assumed noise parameter needs validation.
- **Optional tile Otsu.** The fixed threshold remains the default for reproducibility. Adaptive mode selects sufficiently separable tiles in a configurable metric buffer around the AOI and uses the median accepted threshold; the change threshold remains configured. This is inspired by tile-based thresholding, not a reproduction of the hierarchical split-based paper or operational DLR algorithm. The buffer shares the AOI CRS and grid alignment; only the original AOI is exported. There is no hierarchical subdivision in this release. Insufficient or uniform buffered samples may correctly fall back to the configured fixed threshold.
- **Minimum connected patch area**, default 300 m² (three 10 m pixels), with four-neighbour connectivity. Smaller candidates become no detection in the cleaned product, while the raw mask and quality flag preserve what was removed. This can remove genuine narrow flooding.
- **VV/VH comparison.** Enabled by default. Separate band thresholds, masks, previews and context-stratified counts. A four-class comparison and conservative intersection product preserve disagreements and missing observations; agreement is not accuracy.
- **Urban/vegetation limitation layers.** Historical ESA WorldCover provides spatial context in TIFF and GeoJSON. It does not force urban or vegetation pixels to dry/flooded or validate radar results.
- **Quality raster and diagnostics.** Independent exclusion counts, sequential remaining counts, water-screened and unscreened coverage, selected threshold/fallback, raw/cleaned counts, actual processing settings.

These changes are implemented and locally tested, not proven accuracy improvements. No EMS data are required. They do not solve urban double-bounce flooding, vegetation, missed flood peaks or radar shadow. The JRC source-coverage problem must still be diagnosed with live access; the partial policy prevents it from silently destroying usable radar coverage.

## 1. Install and authenticate

Run from the repository root in PowerShell, using your existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\sentinel1\requirements.txt
.\.venv\Scripts\python.exe -m pytest .\sentinel1\tests -q
```

Python 3.10+ is required; local verification used Python 3.12. Dependencies include Earth Engine, NumPy, Rasterio, Shapely, PyProj, Pillow, Requests, SciPy and Pytest. Dependencies of these packages are installed by pip. `requirements-tested.txt` records the direct versions tested here; it is not a full transitive lock file.

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
6. Source images are aligned by nearest-neighbour sampling to the shared grid and optionally Lee-filtered individually in linear power. A baseline median is computed in **linear power**, then converted back to dB. Each event acquisition is processed separately. Matching slices are mosaicked; different dates are never merged into one event image.
7. Classification uses the selected band and either the configured ceiling or a recorded tile-Otsu ceiling. A valid pixel is potential flood when both `event_db <= water_db` and `baseline_db - event_db >= drop_db`. Example: baseline -10 dB, event -20 dB gives a 10 dB drop. Do not divide negative dB values. A 3 dB drop corresponds to approximately halving linear backscatter power.
8. Permanent water and steep terrain are excluded, and an optional observation-specific shadow/layover raster is applied. Missing DEM/shadow pixels remain unknown. Missing water-reference pixels follow the configured strict/partial policy.
9. Each observation produces separate outputs and provenance. Each run has a unique directory, so an interrupted rerun cannot overwrite a previous successful product. Only the returned manifest is authoritative; do not scan old output folders for the latest result.

Earth Engine S1 GRD already has orbit correction, noise handling, radiometric calibration and geometric terrain correction and is in dB. Do not calibrate it again or apply `10*log10` directly to its dB values. It is not radiometrically terrain-flattened data. Linear-power conversion is used for speckle filtering and the baseline statistic; classification uses dB. Filtering is performed on the complete EE image before tiled download, so download boundaries do not become filter seams. The PNG shows the processed event radar band; the raw flood mask means before patch removal, not before speckle filtering.

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
| `missing_water_policy` | `partial` | Keep unscreened radar analysis where water reference is missing; `strict` excludes it |
| `speckle_filter` | `lee` | `lee` or `none` |
| `lee_window` | 5 | Odd window size: 3, 5 or 7 pixels |
| `lee_enl` | 4.4 | Assumed equivalent number of looks; experimental noise parameter |
| `min_patch_area_m2` | 300 | Remove smaller 4-connected patches; 0 disables removal |
| `threshold_method` | `fixed` | `fixed` or experimental `tile_otsu` |
| `tile_size` | 128 | Non-overlapping tile width/height in grid pixels |
| `min_tile_pixels` | 256 | Minimum valid samples per threshold-estimation tile |
| `min_threshold_tiles` | 3 | Minimum accepted tiles; otherwise fixed fallback |
| `otsu_min_separability` | 0.65 | Minimum between-class / total variance |
| `otsu_min_class_fraction` | 0.05 | Each inferred class needs at least this fraction |
| `otsu_min_separation_db` | 3 | Minimum separation of inferred class means |
| `adaptive_min_db` / `adaptive_max_db` | -25 / -10 | Accepted threshold range; review for VH |
| `threshold_buffer_m` | 2000 | Metric sampling buffer for tile Otsu only; 0 uses AOI |
| `compare_bands` | true | Run both VV and VH on identical acquisition groups |
| `use_landcover` | true | Request historical WorldCover context; missing reference is explicitly unknown |
| `band_thresholds` | `{}` | Per-band overrides for water_db, drop_db and adaptive_min/max_db |
| `max_pixels` | 5,000,000 | Memory guard for each bounding grid, including the sampling buffer |

Thresholds are initial development values, not calibrated recommendations. Changing band to VH requires reconsidering thresholds; the VV defaults should not be assumed suitable. All effective settings are saved in the manifest and each successful observation's metadata.

Permanent water uses `JRC/GSW1_4/YearlyHistory`, taking `min(event year - 1, 2021)`. Class 3 is excluded. Class 0/no data and masked pixels are flagged missing; strict excludes them, while partial permits unscreened radar analysis. This avoids using an incomplete event year or water observations from the future. The old reference may miss new reservoirs, drainage changes and seasonal water. The chosen year is recorded as `water_reference_year`.

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
| `flood_mask_raw.tif` | `flood_mask_raw` | Same classes/grid; before connected-patch removal, after optional Lee filtering |
| `quality_flags.tif` | `quality_flags` | uint16 bit flags; legend in TIFF tags and metadata |
| `flood_extent.geojson` | `flood_extent` | EPSG:4326 FeatureCollection of potential flood pixels |
| `valid_coverage.geojson` | `valid_coverage` | EPSG:4326 FeatureCollection of analysed pixels |
| `metadata.json` | separate `metadata_path` | Acquisition times, exact scene IDs, baseline IDs, configuration, grid, quality warnings |

The run also contains `candidates.json`; the manifest contains reasons for observations that could not be analysed. Observations without enough baseline have no analytical outputs. A downloaded observation with zero valid coverage exports an all-nodata mask, empty coverage/flood collections and its radar preview, but its status is `waiting_for_data`, **not** a zero-flood result.

All layer `bounds` arrays use geographic `[west, south, east, north]`, including GeoTIFF bounds. Layer `crs` describes the actual raster/geometry CRS. PNGs use EPSG:3857; only their bounds are EPSG:4326. Leaflet converts them to `[[south,west],[north,east]]`. Preview coverage can exceed analysis coverage because a radar image may exist where baseline comparison is unavailable.

`valid_coverage_pct` = valid analysed AOI grid cells / all AOI grid cells × 100. The denominator includes permanent water and terrain exclusions. This is coverage, not accuracy or confidence. A valid zero-detection area remains in `valid_coverage.geojson`; missing radar/baseline areas do not. Under partial water policy, this coverage includes radar-valid pixels without water screening; use the quality flags and `water_unscreened_valid_pixel_count` to distinguish them. The land-cover limitation layer flags urban/vegetated and unknown context; it is not a detector suitability guarantee or flood label. `meets_min_coverage=false` means an AOI-wide inference should not be made even if files exist.

Quality bits can overlap: 1 outside AOI; 2 missing radar; 4 insufficient baseline; 8 angle mismatch; 16 missing water reference; 32 excluded known water; 64 slope missing/excluded; 128 shadow missing/excluded; 256 no shadow mask supplied; 512 water exclusion disabled; 1024 small candidate patch removed; 2048 urban interpretation limitation; 4096 vegetated interpretation limitation; 8192 unknown land-cover context. Bits 16 (under partial), 256, 512, 1024, 2048, 4096 and 8192 are warnings, not automatically unknown pixels. Read the flood mask to determine validity. The quality raster has no nodata sentinel; bit 1 identifies outside AOI.

For example, `flags & 16 != 0` selects missing-water-reference pixels. `flags & 64 != 0` selects pixels excluded by the slope check. Counts in `exclusion_counts` are independent and overlap; `remaining_pixels_after_checks` shows the cumulative effect of checks in order.

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
- Upsert by `(event_id, source, observation_id, layer_type, format, band when present)`. Both TIFF and GeoJSON may share a layer_type; VV/VH layers share types but differ in band. Observation IDs stay stable across runs; run directories are unique. Preserve the old published run until a new run has uploaded successfully. Configuration/baseline changes can change historical results, so retain version provenance.
- Existing `event_layers` fields cannot store this whole contract: source currently uses `Sentinel-1`, image kind uses `image`, and the status constraint only has `available/unavailable`. Map source casing explicitly, use `image` for PNG and `geojson` for GeoJSON. Do not put processing status `partial` directly into that old constraint. Preserve processing status/reason/quality in a separate processing record or extend the schema deliberately.
- The current frontend only draws EMS GeoJSON plus satellite PNGs. It needs explicit support for Sentinel-1 `flood_extent` and `valid_coverage`; this function does not make those UI changes. GeoTIFF is an analysis/download product, not a Leaflet ImageOverlay URL. New layer types such as `valid_coverage` may require a database constraint update.
- Use actual `acquired_at` to show evolution. No `after` period is inferred. If the existing UI needs periods, all observations in this search window may be labelled `during`, with precise dates retained.
- New raw-mask, quality, comparison and land-cover layers are optional for map display; upload/store them as diagnostic files. Existing consumers should select layers by `layer_type`, not position or a fixed number of outputs. Preserve `meets_min_coverage`, water-screening coverage and quality flags.
- Never show an empty flood collection as “no flood” without checking coverage and observation status. Label partial outputs, show coverage boundaries, and distinguish no detection from unavailable data.

## 7. Tests and remaining verification

Run `python -m pytest sentinel1/tests -q`. Tests additionally cover partial and strict patchy water references, known-water exclusion, adaptive selection and fallbacks, connected patches and nodata preservation. Existing tests cover input/date boundaries, grid alignment, orbit/polarization/platform separation, deduplication, configurable classification, unknown pixels, dry valid pixels, shadow checks, status transitions, independent observation failures, repeat runs, actual GeoTIFF/PNG/GeoJSON export, tiled download alignment, and offline Earth Engine graph serialization.

These use synthetic arrays or mocked remote responses. They do **not** prove real satellite access, live asset metadata availability, catalogue completeness, server execution, visual alignment on real scenes, or flood-detection accuracy. Credentials are not available in this environment, so no live satellite run was performed.

First live check: run the example on your account, inspect `candidates.json`, confirm matched baseline/event orbit metadata, verify TIFF CRS/transform/nodata in QGIS, overlay the PNG and both GeoJSON layers, and compare date-matched potential flood results against an independent reference. Assess commission and omission inside common valid coverage; do not tune and report accuracy on the same reference pixels.

Downloads are tiled into 512x512 requests to stay below EE's direct-download size limit. A buffered seven-band stack is held in memory one polarization at a time, plus retained AOI arrays for the two bands and land-cover arrays; a 5-million-pixel bounding grid uses about 140 MB just for that stack, plus other arrays and geometry. Very large AOIs require partitioning or a future streaming/batch export implementation. Antimeridian-crossing, polar (outside +/-85 degrees), and invalid projected AOIs are rejected. Fine noisy masks can produce large GeoJSON files. This is a bounded first implementation, not an unrestricted global service.

## Official references and attribution

- [Earth Engine Sentinel-1 preprocessing and comparable subsets](https://developers.google.com/earth-engine/guides/sentinel1)
- [S1 GRD collection](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD)
- [Direct-download limits and transform parameters](https://developers.google.com/earth-engine/apidocs/ee-image-getdownloadurl)
- [Authentication and project setup](https://developers.google.com/earth-engine/guides/auth)
- [JRC yearly water classifications](https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_YearlyHistory)
- [Copernicus DEM 2024_1](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30_2024_1)

Satellite attribution: Copernicus Sentinel data. Water attribution: Source: EC JRC/Google; Pekel et al., Nature 540, 418–422 (2016), doi:10.1038/nature20584. DEM derivative attribution: produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30. Preserve the dataset notices when publishing derived layers.

## Research references and what is actually implemented

- [UN-SPIDER Sentinel-1 GEE practice](https://un-spider.org/advisory-support/recommended-practices/recommended-practice-google-earth-engine-flood-mapping/step-by-step): motivation for noise reduction and connected-pixel cleanup. We retain physically meaningful dB differences rather than dividing negative dB values. Its example thresholds and smoothing radius are not universal settings.
- [Hierarchical split-based thresholding, 2017](https://doi.org/10.1109/TGRS.2017.2737664): motivation for checking class separation and using suitable subsets. Our bounded tile Otsu implementation is simpler and requires independent validation.
- [Urban-aware U-Net, 2022](https://repositum.tuwien.at/bitstream/20.500.12708/91419/1/Zhao-2022-IEEE%20Transactions%20on%20Geoscience%20and%20Remote%20Sensing-vor.pdf): explains why intensity-only open-water detection misses urban flooding. Its SLC/coherence model is not implemented here.
- [Flood-DamageSense](https://arxiv.org/html/2506.06667v1): uses additional multimodal inputs and trained models; not implemented or claimed by this package.

Keep an unchanged fixed/no-filter run as a comparator. Compare precision, recall and IoU inside common reference coverage, plus analysis coverage and urban/open-area breakdowns. Do not tune on the same events used for final evaluation. Optional historical references can support evaluation without becoming a runtime dependency.

To diagnose historical-water source coverage separately (requires your existing EE login):

```powershell
.\.venv\Scripts\python.exe -m sentinel1.diagnose_water --event .\sentinel1\examples\valencia.json --project floodlens-b7eb1
```

This prints class histograms at native spacing and on the output grid. A missing native reference is not the same as a reprojection error. Counts at different resolutions are not directly comparable; examine missing fractions and class presence. The diagnostic is read-only and is not called by production processing.

## Version 0.3.0: buffered adaptive thresholds

`threshold_method="tile_otsu"` uses `threshold_buffer_m` (default 2000 m) in the supplied projected CRS. The processing rectangle is enlarged without changing the origin or resolution. Pixel-centre membership uses the buffered AOI polygon; output masks, statistics, PNGs and GeoJSON remain on the original AOI grid, including its holes.

Samples need finite, comparable baseline/event radar, sufficient baseline count, angle agreement and the configured slope check. Known built-up and snow/ice classes are excluded from threshold estimation. Known permanent water is deliberately retained as a water-class sample, then excluded from flood detection according to the existing policy. Missing land-cover samples may be used but their count is recorded. A supplied AOI shadow mask is applied inside the AOI; the buffer outside it is not shadow-screened. This limitation remains in the threshold metadata.

Only scenes belonging to the AOI-selected acquisition groups are used. We do not add unrelated acquisitions solely because they intersect the buffer. If those scenes do not cover the buffer, those samples remain missing. Every band records the sampling grid, sample counts, accepted tiles, threshold, and fallback. A larger buffer can introduce nonrepresentative land cover and increases processing time; 2000 m is an experimental starting point, not a universal optimum. If the buffered rectangle exceeds `max_pixels`, processing fails explicitly instead of silently shrinking it.

## Version 0.3.0: polarization comparison

`band` selects the primary product, preserving the old contract. `compare_bands=true` adds the other polarization using the same baseline and event scene IDs. Each is filtered, thresholded and patch-cleaned independently. Settings can differ by polarization:

```python
event["sentinel1"] = {
    "band": "VV", "compare_bands": True,
    "threshold_method": "tile_otsu", "threshold_buffer_m": 2000,
    "use_landcover": True,
    "band_thresholds": {
        "VV": {"water_db": -17, "drop_db": 3, "adaptive_min_db": -25, "adaptive_max_db": -10},
        "VH": {"water_db": -23, "drop_db": 3, "adaptive_min_db": -32, "adaptive_max_db": -15},
    },
}
```

These are experimental initial settings. For the primary band, old top-level threshold settings still apply unless overridden in `band_thresholds`. The secondary band's defaults are VV (-17, 3, -25…-10) or VH (-23, 3, -32…-15), rather than copying another band's ceiling. When primary VH thresholds are omitted, validation uses VH-specific defaults (-23, -32…-15). Explicitly supplied top-level values are preserved. These defaults still require validation.

Each observation has `band_results` with per-band settings, threshold evidence, valid coverage, candidate counts and a land-cover breakdown. Existing main `quality` fields describe the primary band. The app must not confuse them with combined coverage. A secondary processing error leaves primary products available with a partial status and a failed comparison reason.

Additional comparison outputs:

| File | Interpretation |
| --- | --- |
| Secondary `vv/` or `vh/` outputs | Same six products as primary, tagged with band and primary=false |
| `polarization_comparison.tif` | 0 neither; 1 VV only; 2 VH only; 3 both; 255 one/both invalid or outside AOI |
| `flood_mask_agreement.tif` | 1 both cleaned masks detect; 0 no joint detection; 255 unknown |
| `flood_extent_agreement.geojson` | Polygonized intersection of cleaned masks |
| `comparison_valid_coverage.geojson` | Coverage valid in both bands |

Agreement is evaluated only where both bands are valid. `interband_iou_not_accuracy` measures agreement between detectors, not reference accuracy; it is null when there are no union candidates. The conservative intersection can miss real floods. Its intersection patches are not filtered a second time and may be smaller than either band's patch minimum. Neither band is automatically chosen as more accurate. There is no trained fusion model or urban coherence processing.

## Version 0.3.0: land-cover interpretation context

[ESA WorldCover v200](https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200) represents 2021; [v100](https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v100) represents 2020. For event years 2022 onward use v200; for 2021 use v100. For earlier events there is no supported earlier reference: context is unknown. We avoid future reference years but do not simulate which products were published at the historical event instant. For current events, old land cover may be stale.

`landcover_limitations.tif` and `.geojson` use: 0 other mapped cover (not a reliability guarantee); 1 built-up; 2 vegetated; 3 missing/unsupported context; 255 outside AOI in TIFF. GeoJSON contains warning classes 1–3 only, with the reference year and `is_flood_evidence=false`. Built-up is WorldCover class 50; vegetation includes 10,20,30,40,90,95,100. These broad categories flag potential detection limitations; their presence does not prove sub-canopy flooding or complete detector failure.

The context flags do not remove radar pixels from detection and are not a substitute for geometry-specific radar shadow. Missing or failed land-cover retrieval leaves an unknown layer, records the reason, and produces a partial result while preserving usable radar outputs. Setting `use_landcover=false` skips the download and layer export, but context remains unknown in quality flags. Class counts, source, year, coverage and per-band detection counts by category are recorded. Reports of fewer detections in a class are not recall estimates.

Attribution when publishing: ESA WorldCover Consortium, CC BY 4.0. Cite [2021 v200](https://doi.org/10.5281/zenodo.7254221) or [2020 v100](https://doi.org/10.5281/zenodo.5571936) according to the recorded asset.
