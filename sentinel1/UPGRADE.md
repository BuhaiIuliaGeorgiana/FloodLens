# Install version 0.3.0

The archive contains a complete `sentinel1` package. It does not contain your old notebooks, Sentinel-2 code, outputs, credentials or database files.

1. Stop the Streamlit terminal with Ctrl+C.
2. Back up your current `sentinel1` folder outside the repository, or commit your current source changes. Extract the archive into a temporary folder. Copy its `sentinel1` contents into the repository's existing `sentinel1` folder, replacing matching files. Do not delete unrelated files or notebooks.
3. In PowerShell at the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\sentinel1\requirements-demo.txt
.\.venv\Scripts\python.exe -m pytest .\sentinel1\tests -q
```

There are 74 local tests, including one optional Streamlit test. Without Streamlit that test is skipped. No Earth Engine login is needed for these tests.

4. Run the real Valencia example using your existing login:

```powershell
.\.venv\Scripts\python.exe -m sentinel1.run --event .\sentinel1\examples\valencia.json --output .\outputs\sentinel1_v030 --project floodlens-b7eb1
```

If authentication has expired, run `python -c "import ee; ee.Authenticate()"` using the same virtual-environment Python executable before retrying.

5. Or reopen the updated form:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\sentinel1\demo_app.py --server.address 127.0.0.1
```

The form starts with Pechea. For Valencia, enter the values in `examples/valencia.json`. The Valencia CLI example enables tile Otsu; the form now defaults to tile Otsu with a 2000 m buffer, VV/VH comparison and land-cover context enabled. Match settings for a meaningful comparison.

## Call from another Python module

```python
import json
from pathlib import Path
import ee
from sentinel1 import process_sentinel1

# Autentificarea interactiva se face separat, o singura data.
ee.Initialize(project="floodlens-b7eb1")
event = json.loads(Path("sentinel1/examples/valencia.json").read_text())
result = process_sentinel1(event, "outputs/sentinel1_v030")
print(result["status"], result["reason"])
for observation in result["observations"]:
    print(observation["acquired_at"], observation["quality"])
```

Keep the same agreed signature: `process_sentinel1(event, output_dir)`. Other teammates still handle scheduling, uploads, database updates and exposure calculations.

## Check the result

- Confirm `pipeline_version` is `0.3.0`.
- Read `quality.threshold`: requested/used method, selected ceiling and fallback reason.
- Compare `water_screened_valid_pixel_count` with `water_unscreened_valid_pixel_count`.
- Inspect `remaining_pixels_after_checks` and `quality_flags.tif` to understand grey areas.
- Compare `flood_mask_raw.tif` with `flood_mask.tif`; raw is before patch removal but after any Lee filtering.
- Keep `partial` visible. If `meets_min_coverage` is false, do not use the result for an AOI-wide conclusion.
- Do not interpret a larger blue area as higher accuracy. Compare date-matched independent references where available. EMS is not required to run this function.

For a comparator, set `speckle_filter="none"`, `min_patch_area_m2=0`, and `threshold_method="fixed"` in a copied event dictionary, keeping the dates, grid, water policy and other settings identical. Change one processing choice at a time.

## Verification boundary

Local tests cover Python logic, mocked Earth Engine graph construction, actual local raster/vector/image exports and the demo workflow. They do not test live satellite catalogue access, server-side filtering, or flood accuracy. You must run the live example on your account. No claim of urban flood completeness or building damage accuracy is made.

## New controls and results

- Enable **Compare VV and VH** to process both polarizations on identical acquisitions. Their experimental thresholds differ; the form exposes the secondary ceiling and change threshold.
- **Threshold sampling buffer** applies only to tile Otsu. It improves available sampling context but does not enlarge exported flood coverage. Reduce it if the buffered grid exceeds the pixel limit.
- **Add urban/vegetation limitation layer** uses historical ESA WorldCover and displays its source year and coverage. The coloured layer warns about interpretation limits; it is not a flood map.
- The result shows per-band detections, comparison classes and land-cover context. Blue/orange disagreements are retained; purple means both detectors mark potential flooding, not confirmed flooding.
- Integrators must include `band` and `format` when identifying layers. Filter `primary=true` to select old primary products. There are normally 18 layers per observation with both features enabled, rather than six. Do not hardcode that count.

The live download and real-world accuracy of this version need your Earth Engine account and reference assessment. Synthetic tests and offline EE graph checks cannot prove scientific accuracy.
