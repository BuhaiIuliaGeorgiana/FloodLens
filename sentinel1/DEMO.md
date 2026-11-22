# Local Sentinel-1 demo

This separate Streamlit page calls the real `process_sentinel1(event, output_dir)` function. It is a local teaching/demo tool, not the shared React map or a deployment on Netlify. No database writes, scheduling, uploads, EMS comparisons or exposure calculations are included.

Use all package files from the version 0.3.0 archive together, including `analysis.py` and the updated requirements. Back up your existing folder before replacing matching files; keep any personal notebooks.

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\sentinel1\requirements-demo.txt
.\.venv\Scripts\python.exe -m streamlit run .\sentinel1\demo_app.py --server.address 127.0.0.1
```

Open http://localhost:8501 if the browser does not open automatically. Keep the terminal open; Ctrl+C stops the local server.

The demo uses your already configured Earth Engine login. If credentials are missing:

```powershell
.\.venv\Scripts\python.exe -c "import ee; ee.Authenticate()"
```

Enter the authorized project ID in the form. The default is the project used in your successful run; it is editable. Do not paste tokens or private keys into the form.

## Show your teammate

1. Start with the included Pechea event values. Explain that they are example inputs, not fixed processing parameters.
2. Show event ID, polygon and UTC dates. End dates are exclusive. Change search_end for an ongoing event; an after scene is not needed.
3. Show the shared projected CRS, 10 m grid origin, thresholds, Lee filter, minimum patch area and missing-water policy. Tile Otsu is selected by default with a 2000 m sampling buffer; it records fallback when suitable samples are unavailable. Outputs are cropped to the original AOI. Choose a suitable CRS for other regions.
4. Click Run Sentinel-1. The form calls the actual Python function once on submission. Changing the displayed observation or downloading a file does not call it again.
5. Show status, coverage, acquisition dates, radar preview, flood-mask preview and downloadable analytical layers. The mask preview is a pixel view, not an interactive geographic basemap. Quality warnings remain visible; partial does not mean validated flooding.
6. Open Exact function input and download the returned JSON. Your teammate will replace this form with the real event creation flow and handle storage/upload outside this function.

Output folders are relative to the repository root unless an absolute path is supplied. There is no historical-run browser: results are held in the current browser session; files remain on disk after closing the page. The function runs synchronously and has no progress percentage or cancellation button. Large AOIs remain subject to the pipeline's pixel limit. This launcher binds to localhost and is intended for screen sharing on your laptop, not public hosting.

Comments in the Python file are in Romanian. The interface is in English to match the current app. `st.form` collects the inputs; `st.form_submit_button` triggers processing; `st.session_state` preserves the returned dictionary across UI interactions; `st.download_button` exposes the already-generated files.

UI verification uses Streamlit AppTest with mocked Earth Engine access and synthetic radar arrays through the real local pipeline. Version 0.3.0 has not been run against live Earth Engine here. Earlier versions 0.1.1 and 0.2.0 were run by the user; that does not validate the new filters or server execution.

The demo also displays per-band counts, both radar previews and masks, VV/VH comparison colours and a spatial urban/vegetation context preview. Agreement is not accuracy. Downloads are identified by layer type, band and format to avoid duplicate UI keys.
