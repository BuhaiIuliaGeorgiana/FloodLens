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
        water_db = middle.number_input("Event backscatter ceiling (dB)", value=-17.0)
        drop_db = right.number_input("Minimum decrease (dB)", min_value=0.1, value=3.0)
        minimum = st.number_input("Minimum baseline acquisitions", min_value=1, value=2, step=1)
        st.caption("Thresholds are experimental. Reconsider them when changing the band or event.")
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
        radar, flood = st.columns(2)
        for layer in obs.get("layers", []):
            path = Path(layer["local_path"])
            if not path.is_file():
                st.error(f"Output file missing: {path.name}")
                continue
            if layer["format"] == "png":
                radar.image(str(path), caption="Radar preview · image coverage may exceed analysis coverage")
            elif layer["layer_type"] == "flood_mask":
                with rasterio.open(path) as src:
                    mask = src.read(1)
                # Alb = fara detectie, albastru = candidat, gri = necunoscut.
                preview = np.full((*mask.shape, 3), 128, dtype="uint8")
                preview[mask == 0] = [255, 255, 255]
                preview[mask == 1] = [0, 140, 255]
                flood.image(preview, caption="Blue: potential flood · White: no detection · Grey: unknown/excluded")
            st.download_button(f"Download {layer['layer_type']}", data=path.read_bytes(),
                               file_name=path.name, key=f"{obs['observation_id']}_{layer['layer_type']}")
        with st.expander("Scene IDs and observation metadata"):
            st.json(obs)
    st.download_button("Download result JSON", json.dumps(result, indent=2),
                       file_name="sentinel1_result.json", mime="application/json")
    with st.expander("Exact function input"):
        st.json(st.session_state["s1_demo_event"])
        st.code("result = process_sentinel1(event, output_dir)", language="python")
else:
    st.caption("The form starts with the Pechea test case. Replace the polygon, dates and grid to demonstrate another event.")
