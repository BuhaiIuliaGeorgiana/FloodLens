"""Formular local pentru demonstrarea pipeline-ului Sentinel-1."""
import json
import os
from pathlib import Path
import sys

# Permitem pornirea din terminal prin Streamlit.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ee
import numpy as np
import rasterio
import streamlit as st
from sentinel1 import process_sentinel1
from sentinel1.core import validate, make_grid

st.set_page_config(page_title="FloodLens · Sentinel-1 demo", page_icon="🌊", layout="wide")
st.title("FloodLens · Sentinel-1")
st.caption("Local pipeline demo · potential flooding, not confirmed damage")
st.info("Choose an event, run the Python function, and inspect its outputs. No EMS or Supabase connection is required.")

example = json.loads((ROOT / "sentinel1/examples/pechea.json").read_text(encoding="utf-8"))

with st.form("sentinel1_event"):
    st.subheader("1 · Event")
    event_id = st.text_input("Event ID", value=example["event_id"])
    left, middle, right = st.columns(3)
    baseline_start = left.text_input("Baseline start (UTC)", value=example["baseline_start"])
    event_start = middle.text_input("Event start (UTC)", value=example["event_start"])
    search_end = right.text_input("Search end (UTC, exclusive)", value=example["search_end"])
    st.caption("Baseline: [baseline start, event start). Event observations: [event start, search end). For an ongoing event, advance search end; no after image is required.")
    aoi_text = st.text_area("AOI — GeoJSON Polygon, [longitude, latitude]", value=json.dumps(example["aoi"], indent=2), height=180)

    with st.expander("2 · Shared grid and detection settings"):
        left, middle, right = st.columns(3)
        crs = left.text_input("Processing CRS (metres)", value=example["grid"]["crs"])
        origin_x = middle.number_input("Grid origin X", value=0.0)
        origin_y = right.number_input("Grid origin Y", value=0.0)
        st.caption("Grid spacing is fixed at 10 m. Use the CRS and alignment agreed for this event; 10 m spacing is not the radar's effective resolution.")
        left, middle, right = st.columns(3)
        band = left.selectbox("Radar band", ["VV", "VH"])
        water_db = middle.number_input("Event backscatter ceiling (dB)", value=-17.0 if band == "VV" else -23.0)
        drop_db = right.number_input("Minimum decrease (dB)", min_value=0.1, value=3.0)
        minimum = st.number_input("Minimum baseline acquisitions", min_value=1, value=2, step=1)
        st.caption("Thresholds are experimental. Reconsider them when changing the band or event.")
        method = st.selectbox("Threshold method", ["fixed", "tile_otsu"], index=1)
        buffer_m = st.number_input("Threshold sampling buffer (metres)", min_value=0.0, max_value=10000.0, value=2000.0, step=500.0)
        compare_bands = st.checkbox("Compare VV and VH on the same acquisitions", value=True)
        other_band = "VH" if band == "VV" else "VV"
        other_ceiling = st.number_input(f"{other_band} comparison water ceiling (dB)", value=-23.0 if other_band == "VH" else -17.0)
        other_drop = st.number_input(f"{other_band} comparison minimum decrease (dB)", min_value=0.1, value=3.0)
        use_landcover = st.checkbox("Add urban/vegetation limitation layer (ESA WorldCover)", value=True)
        speckle = st.selectbox("Speckle filter", ["lee", "none"])
        lee_window = st.selectbox("Lee window (pixels)", [3, 5, 7], index=1)
        enl = st.number_input("Lee equivalent number of looks (experimental)", min_value=0.1, value=4.4)
        min_patch = st.number_input("Minimum retained patch area (m²)", min_value=0.0, value=300.0, step=100.0)
        st.caption("Tile Otsu uses suitable buffered samples, excluding known built-up/snow pixels; outputs stay inside the AOI; otherwise it records a fallback to the fixed ceiling above. Small urban AOIs may not provide suitable samples. Raw mask means before patch removal, after any speckle filter.")
        use_water = st.checkbox("Exclude permanent water when available", value=True)
        policy = st.selectbox("Missing water-reference policy", ["partial", "strict"])
        st.caption("Partial: keep usable radar analysis and flag the skipped water filter. Strict: leave those analysis pixels unknown. This form supplies no radar-shadow mask.")

    with st.expander("3 · Local setup", expanded=True):
        project = st.text_input("Earth Engine project", value=os.getenv("EE_PROJECT", "floodlens-b7eb1"))
        output_dir = st.text_input("Output folder", value="outputs/sentinel1_demo")
        st.caption("Uses your existing Earth Engine login. Files are saved on the computer running this page.")
    submitted = st.form_submit_button("Run Sentinel-1", type="primary")

if submitted:
    # Stergem rezultatul vechi pentru a nu-l confunda cu o rulare noua.
    st.session_state.pop("s1_demo_result", None)
    st.session_state.pop("s1_demo_event", None)
    try:
        event = {
            "event_id": event_id.strip(), "aoi": json.loads(aoi_text),
            "baseline_start": baseline_start.strip(), "event_start": event_start.strip(),
            "search_end": search_end.strip(),
            "grid": {"crs": crs.strip(), "resolution": 10, "origin": [origin_x, origin_y]},
            "sentinel1": {"band": band, "water_db": water_db, "drop_db": drop_db,
                          "min_baseline_observations": int(minimum),
                          "threshold_method": method, "speckle_filter": speckle,
                          "threshold_buffer_m": buffer_m, "compare_bands": compare_bands,
                          "use_landcover": use_landcover,
                          "band_thresholds": {other_band: {"water_db": other_ceiling, "drop_db": other_drop}},
                          "lee_window": lee_window, "lee_enl": enl, "min_patch_area_m2": min_patch,
                          "use_permanent_water": use_water, "missing_water_policy": policy},
        }
        dates, settings = validate(event)
        make_grid(event, settings["max_pixels"])
        if not project.strip() or not output_dir.strip():
            raise ValueError("Enter an Earth Engine project and output folder.")
        folder = Path(output_dir).expanduser()
        if not folder.is_absolute():
            folder = ROOT / folder
        with st.spinner("Searching scenes and processing observations. This may take several minutes…"):
            ee.Initialize(project=project.strip())
            result = process_sentinel1(event, str(folder))
        # Schimbarea observatiei nu reporneste procesarea.
        st.session_state["s1_demo_result"] = result
        st.session_state["s1_demo_event"] = event
    except Exception as error:
        st.error(f"Could not run: {error}")
        st.caption("For authentication errors, use the terminal login command in DEMO.md, then retry.")

result = st.session_state.get("s1_demo_result")
if result:
    st.divider()
    st.subheader("Result")
    state = result["status"]
    message = f"{state.upper()} — {result.get('reason') or 'Processing completed.'}"
    if state == "ready":
        st.success(message)
    elif state == "failed":
        st.error(message)
    else:
        st.warning(message)
    st.caption(f"Event: {result['event_id']} · Pipeline: {result.get('pipeline_version', 'unknown')}")
    observations = result.get("observations", [])
    if observations:
        index = st.selectbox("Observation", range(len(observations)),
                             format_func=lambda i: f"{observations[i]['acquired_at']} · {observations[i]['observation_id']}")
        obs = observations[index]
        st.write(f"Observation status: **{obs['status']}**")
        if obs.get("reason"):
            st.warning(obs["reason"])
        coverage = obs["quality"].get("valid_coverage_pct")
        st.metric("Valid analysis coverage — not accuracy", "Unknown" if coverage is None else f"{coverage:.2f}%")
        with st.expander("Quality warnings and filters", expanded=True):
            for warning in obs["quality"].get("warnings", []):
                st.write(f"• {warning}")
            st.json(obs["quality"].get("filters", {}))
            st.json(obs["quality"].get("threshold", {}))
            st.json(obs["quality"].get("remaining_pixels_after_checks", {}))
            st.caption(f"Valid pixels without water screening: {obs['quality'].get('water_unscreened_valid_pixel_count', 'unknown')}")
        if obs["quality"].get("meets_min_coverage") is False:
            st.error("Insufficient analysis coverage for an AOI-wide conclusion. These files are diagnostic results.")
        if obs.get("band_results"):
            st.write("Per-band results — detections, not accuracy")
            st.dataframe([{
                "band": band_name,
                "valid pixels": data["valid_pixel_count"],
                "candidate pixels": data["potential_flood_pixel_count"],
                "threshold dB": data["quality"]["threshold"]["water_db"],
                "method": data["quality"]["threshold"]["used_method"],
            } for band_name, data in obs["band_results"].items()])
        with st.expander("VV/VH agreement and land-cover context"):
            st.json(obs.get("band_comparison", {}))
            st.json(obs["quality"].get("landcover", {}))
            st.caption("Agreement is not accuracy. Urban/vegetated pixels with no detection remain inconclusive.")
        radar, flood = st.columns(2)
        for layer in obs.get("layers", []):
            path = Path(layer["local_path"])
            if not path.is_file():
                st.error(f"Output file missing: {path.name}")
                continue
            if layer["format"] == "png":
                radar.image(str(path), caption=f"{layer.get('band', '')} radar · image coverage may exceed analysis coverage")
            elif layer["layer_type"] == "flood_mask":
                with rasterio.open(path) as src:
                    mask = src.read(1)
                # Alb = fara detectie, albastru = candidat, gri = necunoscut.
                preview = np.full((*mask.shape, 3), 128, dtype="uint8")
                preview[mask == 0] = [255, 255, 255]
                preview[mask == 1] = [0, 140, 255]
                flood.image(preview, caption=f"{layer.get('band', '')} · Blue: potential flood · White: no detection · Grey: unknown/excluded")
            st.download_button(f"Download {layer['layer_type']} {layer.get('band', '')} ({layer['format']})", data=path.read_bytes(),
                               file_name=path.name, key=f"{obs['observation_id']}_{layer['layer_type']}_{layer.get('band', '')}_{layer['format']}")
        agreement_view, limitations_view = st.columns(2)
        for layer in obs.get("layers", []):
            kind = layer["layer_type"]
            if layer["format"] != "geotiff" or kind not in ("polarization_comparison", "landcover_limitations"):
                continue
            with rasterio.open(layer["local_path"]) as src:
                classes = src.read(1)
            preview = np.full((*classes.shape, 3), 128, dtype="uint8")
            if kind == "polarization_comparison":
                colors = {0:[255,255,255],1:[0,140,255],2:[255,165,0],3:[130,30,180]}
                target, caption = agreement_view, "VV only: blue · VH only: orange · Both: purple · Neither: white · Unknown: grey"
            else:
                colors = {0:[240,240,240],1:[230,70,70],2:[65,160,80],3:[160,160,160]}
                target, caption = limitations_view, "Interpretation limits — Built-up: red · Vegetated: green · Missing reference: grey · Other mapped cover: white (not guaranteed reliable)"
            for value, color in colors.items():
                preview[classes == value] = color
            target.image(preview, caption=caption)
        with st.expander("Scene IDs and observation metadata"):
            st.json(obs)
    st.download_button("Download result JSON", json.dumps(result, indent=2),
                       file_name="sentinel1_result.json", mime="application/json")
    with st.expander("Exact function input"):
        st.json(st.session_state["s1_demo_event"])
        st.code("result = process_sentinel1(event, output_dir)", language="python")
else:
    st.caption("The form starts with the Pechea test case. Replace the polygon, dates and grid to demonstrate another event.")
