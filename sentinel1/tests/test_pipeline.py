import copy
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from PIL import Image
from shapely.geometry import shape

from sentinel1.core import DEFAULTS, utc, validate, make_grid, classify, group_observations, comparison_key
from sentinel1.pipeline import process_sentinel1
from sentinel1 import earth_engine as backend
from sentinel1.outputs import read_shadow


@pytest.fixture(autouse=True)
def legacy_mode(monkeypatch):
    # Verificarile vechi izoleaza fluxul cu o singura polarizare.
    monkeypatch.setitem(DEFAULTS, "compare_bands", False)
    monkeypatch.setitem(DEFAULTS, "use_landcover", False)


@pytest.fixture
def event():
    return {"event_id": "test-event", "aoi": {"type": "Polygon", "coordinates": [
        [[27.8, 45.6], [27.801, 45.6], [27.801, 45.601], [27.8, 45.601], [27.8, 45.6]]]},
        "baseline_start": "2024-08-01", "event_start": "2024-09-14", "search_end": "2024-09-19",
        "grid": {"crs": "EPSG:32635", "resolution": 10, "origin": [0, 0]}}


def scene(date, orbit=109, absolute=1, slice_=1, suffix="A"):
    return {"asset_id": f"COPERNICUS/S1_GRD/test_{absolute}_{slice_}_{suffix}",
            "acquired_at": utc(date), "mode": "IW", "relative_orbit": orbit,
            "absolute_orbit": absolute, "direction": "DESCENDING", "polarizations": ["VV", "VH"],
            "platform": "A", "datatake": absolute, "slice": slice_}


def data(grid):
    stack = np.zeros((7, grid["height"], grid["width"]), dtype="float32")
    stack[0] = -10
    stack[1] = -20
    stack[2] = 2
    stack[3:5] = 35
    stack[5] = 1
    return stack


def fake_backend(monkeypatch, records):
    monkeypatch.setattr(backend, "discover", lambda *args: records)
    monkeypatch.setattr(backend, "build_stack", lambda event, obs, baseline, grid, options: grid)
    monkeypatch.setattr(backend, "download_stack", lambda image, grid: data(grid))


def test_dates_and_fractional_boundary():
    assert utc("2024-09-14") == utc("2024-09-14T03:00:00+03:00")
    assert utc("2024-09-14T00:00:00.001Z") > utc("2024-09-14")
    with pytest.raises(ValueError):
        utc("2024-09-14T00:00:00")


@pytest.mark.parametrize("change", [
    {"event_start": "2024-07-01"}, {"search_end": "2024-09-14"},
    {"sentinel1": {"drop_db": -3}}, {"sentinel1": {"drop_db": float("nan")}},
    {"sentinel1": {"misspelled": 1}}, {"sentinel1": {"min_baseline_observations": 0}},
])
def test_validation(event, change):
    event.update(change)
    with pytest.raises(ValueError):
        validate(event)


def test_grid_alignment_and_limit(event):
    event["grid"]["origin"] = [3, 7]
    grid = make_grid(event, 1000)
    assert (grid["transform"].c - 3) % 10 == 0
    assert (grid["transform"].f - 7) % 10 == 0
    with pytest.raises(ValueError):
        make_grid(event, 1)
    event["grid"]["crs"] = "EPSG:4326"
    with pytest.raises(ValueError):
        make_grid(event, 1000)


def test_mask_unknown_permanent_water_slope_shadow_and_no_detection():
    grid = {"width": 8, "height": 1}
    stack = data(grid)
    stack[1, 0, 1] = -11
    stack[0, 0, 2] = np.nan
    stack[5, 0, 3] = 3
    stack[6, 0, 4] = 20
    stack[2, 0, 5] = 1
    stack[4, 0, 6] = 40
    shadow = np.zeros((1, 8)); shadow[0, 7] = 1
    mask, valid = classify(stack, np.ones((1, 8), bool), DEFAULTS, shadow)
    assert mask.tolist() == [[1, 0, 255, 255, 255, 255, 255, 255]]
    assert valid.sum() == 2


def test_thresholds_configurable():
    grid = {"width": 1, "height": 1}
    stack = data(grid)
    settings = {**DEFAULTS, "drop_db": 11}
    mask, valid = classify(stack, np.ones((1, 1), bool), settings)
    assert valid.all() and mask.item() == 0


def test_group_slices_deduplicate_and_keep_dates():
    records = [scene("2024-09-14T04:00:00Z", suffix="A"),
               scene("2024-09-14T04:00:00Z", suffix="B"),
               scene("2024-09-14T04:00:25Z", slice_=2),
               scene("2024-09-26", absolute=2)]
    grouped = group_observations(records)
    assert len(grouped) == 2
    assert len(grouped[0]["records"]) == 2
    assert len(grouped[0]["discarded_duplicate_scene_ids"]) == 1


@pytest.mark.parametrize("field,value", [("relative_orbit", 36), ("direction", "ASCENDING"),
                                         ("mode", "EW"), ("polarizations", ["VV"]), ("platform", "B")])
def test_no_cross_geometry_comparisons(field, value):
    first = scene("2024-09-14")
    second = copy.deepcopy(first); second[field] = value
    assert comparison_key(first) != comparison_key(second)


def test_no_scenes_is_waiting(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, [])
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == "waiting_for_data"
    assert result["observations"] == []
    assert json.loads(Path(result["manifest_path"]).read_text()) == result


def records():
    return [scene("2024-08-21", absolute=1), scene("2024-09-02", absolute=2),
            scene("2024-09-14", absolute=3)]


def test_export_roundtrip_and_rerun(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, records())
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == "partial"  # Lipseste masca de umbra.
    obs = result["observations"][0]
    assert len(obs["baseline_scene_ids"]) == 2
    assert obs["quality"]["valid_coverage_pct"] == 100
    assert len(obs["layers"]) == 6
    paths = {layer["format"] + layer["layer_type"]: layer["local_path"] for layer in obs["layers"]}
    with rasterio.open(paths["geotiff" + "flood_mask"]) as src:
        assert src.nodata == 255 and src.res == (10, 10)
        assert src.crs.to_epsg() == 32635
        assert src.read(1, masked=True).compressed().min() == 1
    for layer in obs["layers"]:
        if layer["format"] == "geojson":
            content = json.loads(Path(layer["local_path"]).read_text())
            assert content["features"]
            assert all(shape(f["geometry"]).is_valid for f in content["features"])
        assert all(np.isfinite(layer["bounds"]))
    with Image.open(paths["pngsatellite_image"]) as image:
        assert image.mode == "RGBA"
        assert max(image.size) == 1400
    again = process_sentinel1(event, str(tmp_path))
    assert again["manifest_path"] != result["manifest_path"]
    assert again["observations"][0]["observation_id"] == obs["observation_id"]


def test_no_coverage_is_not_no_flood(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, records())
    monkeypatch.setattr(backend, "download_stack", lambda image, grid: np.full((7, grid["height"], grid["width"]), np.nan))
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == "waiting_for_data"
    obs = result["observations"][0]
    assert obs["quality"]["valid_coverage_pct"] == 0
    path = next(x["local_path"] for x in obs["layers"] if x["format"] == "geotiff")
    with rasterio.open(path) as src:
        assert np.all(src.read(1) == 255)


def test_missing_baseline(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, [scene("2024-09-14")])
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == "waiting_for_data"
    assert result["observations"][0]["layers"] == []


def test_error_does_not_look_like_missing_data(event, tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("authentication failed")
    monkeypatch.setattr(backend, "discover", fail)
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == "failed"
    assert "authentication failed" in result["reason"]


def test_partial_success_keeps_other_observation(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, records() + [scene("2024-09-15", absolute=4)])
    calls = []
    def download(image, grid):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("download interrupted")
        return data(grid)
    monkeypatch.setattr(backend, "download_stack", download)
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == "partial"
    assert [o["status"] for o in result["observations"]] == ["partial", "failed"]


def test_shadow_grid_validation_and_ready(event, tmp_path, monkeypatch):
    grid = make_grid(event, 1000)
    path = tmp_path / "shadow.tif"
    with rasterio.open(path, "w", driver="GTiff", width=grid["width"], height=grid["height"],
                       count=1, dtype="uint8", crs=grid["crs"], transform=grid["transform"], nodata=255) as dst:
        dst.write(np.zeros((grid["height"], grid["width"]), dtype="uint8"), 1)
    assert not read_shadow(path, grid).any()
    fake_backend(monkeypatch, records())
    event["sentinel1"] = {"shadow_masks": {"s1_A_3_3": str(path)}}
    assert process_sentinel1(event, str(tmp_path))["status"] == "ready"
    with pytest.raises(ValueError):
        read_shadow(path, {**grid, "crs": "EPSG:3857"})


def test_earth_engine_graph_builds_without_network(event, monkeypatch):
    import ee
    from ee.apitestcase import GetAlgorithms
    ee.Reset()
    monkeypatch.setattr(ee.data, "_install_cloud_api_resource", lambda: None)
    monkeypatch.setattr(ee.data, "getAlgorithms", GetAlgorithms)
    monkeypatch.setattr(ee.data, "computeValue", lambda x: [])
    ee.Initialize(None, "", project="offline-test")
    try:
        dates, options = validate(event)
        assert backend.discover(event, dates) == []
        options["water_reference_year"] = 2021
        groups = group_observations(records())
        grid = make_grid(event, 1000)
        image = backend.build_stack(event, groups[-1], groups[:2], grid, options)
        serialized = image.serialize()
        assert "COPERNICUS/S1_GRD" in serialized
        assert "JRC/GSW1_4/YearlyHistory" in serialized
        assert "Image.reproject" in serialized
        assert "Image.reduceNeighborhood" in serialized
    finally:
        ee.Reset()


def test_empty_flood_extent_can_still_have_valid_coverage(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, records())
    def dry(image, grid):
        stack = data(grid); stack[1] = -11
        return stack
    monkeypatch.setattr(backend, "download_stack", dry)
    result = process_sentinel1(event, str(tmp_path))
    obs = result["observations"][0]
    assert obs["quality"]["valid_coverage_pct"] == 100
    assert obs["quality"]["potential_flood_pixel_count"] == 0
    for layer in obs["layers"]:
        if layer["layer_type"] == "flood_extent":
            assert json.loads(Path(layer["local_path"]).read_text())["features"] == []
        elif layer["layer_type"] == "valid_coverage":
            assert json.loads(Path(layer["local_path"]).read_text())["features"]


def test_downloader_tile_alignment(monkeypatch):
    from affine import Affine
    from rasterio.io import MemoryFile
    grid = {"width": 513, "height": 2, "crs": "EPSG:32635", "transform": Affine(10, 0, 500000, 0, -10, 5000000)}
    calls = []
    class FakeImage:
        def getDownloadURL(self, options):
            calls.append(options)
            return "https://example.test/tile"
    class Response:
        def raise_for_status(self):
            pass
        @property
        def content(self):
            config = calls[-1]; width, height = config["dimensions"]
            with MemoryFile() as memory:
                with memory.open(driver="GTiff", width=width, height=height, count=7,
                                 crs=config["crs"], transform=Affine(*config["crs_transform"]), dtype="float32") as dst:
                    dst.write(np.full((7, height, width), len(calls), dtype="float32"))
                return memory.read()
    monkeypatch.setattr(backend.requests.Session, "get", lambda *args, **kwargs: Response())
    stack = backend.download_stack(FakeImage(), grid)
    assert len(calls) == 2
    assert calls[1]["crs_transform"][2] == 505120
    assert np.all(stack[:, :, :512] == 1)
    assert np.all(stack[:, :, 512:] == 2)


@pytest.mark.parametrize("policy,expected", [("partial", "partial"), ("strict", "waiting_for_data")])
def test_missing_water_policy(event, tmp_path, monkeypatch, policy, expected):
    fake_backend(monkeypatch, records())
    def missing_water(image, grid):
        stack = data(grid)
        stack[5] = np.nan
        stack[0, 0, :] = np.nan
        return stack
    monkeypatch.setattr(backend, "download_stack", missing_water)
    event["sentinel1"] = {"missing_water_policy": policy}
    result = process_sentinel1(event, str(tmp_path))
    assert result["status"] == expected
    obs = result["observations"][0]
    assert obs["quality"]["filters"]["permanent_water"]["applied"] is False
    assert result["configuration"]["sentinel1"]["use_permanent_water"] is True
    path = next(layer["local_path"] for layer in obs["layers"] if layer["format"] == "geotiff")
    with rasterio.open(path) as src:
        assert np.all(src.read(1)[0] == 255)
    if policy == "partial":
        assert obs["quality"]["valid_pixel_count"] > 0
        assert obs["quality"]["water_unscreened_valid_pixel_count"] > 0


def test_partially_missing_water_partial_keeps_radar(event, tmp_path, monkeypatch):
    fake_backend(monkeypatch, records())
    def patchy_water(image, grid):
        stack = data(grid)
        stack[5, :, :grid["width"] // 2] = np.nan
        return stack
    monkeypatch.setattr(backend, "download_stack", patchy_water)
    result = process_sentinel1(event, str(tmp_path))
    obs = result["observations"][0]
    assert obs["effective_settings"]["use_permanent_water"] is True
    assert obs["quality"]["valid_coverage_pct"] == 100
    assert 0 < obs["quality"]["filters"]["permanent_water"]["reference_coverage_pct"] < 100


def test_quality_export_and_cleaned_vector_roundtrip(event, tmp_path, monkeypatch):
    from rasterio.features import rasterize
    from rasterio.warp import transform_geom
    from sentinel1.analysis import QUALITY_BITS
    fake_backend(monkeypatch, records())
    def patchy(image, grid):
        stack = data(grid)
        stack[5, :, :grid['width']//2] = np.nan
        stack[5, :, -1] = 3
        return stack
    monkeypatch.setattr(backend, 'download_stack', patchy)
    result = process_sentinel1(event, str(tmp_path))
    obs = result['observations'][0]
    layers = {layer['layer_type']: layer for layer in obs['layers']}
    with rasterio.open(layers['quality_flags']['local_path']) as src:
        flags = src.read(1)
        assert src.dtypes == ('uint16',)
        assert json.loads(src.tags()['quality_bits']) == QUALITY_BITS
        assert np.any(flags & QUALITY_BITS['water_reference_missing'])
    with rasterio.open(layers['flood_mask']['local_path']) as src:
        mask = src.read(1)
        collection = json.loads(Path(layers['flood_extent']['local_path']).read_text())
        geometries = [(transform_geom('EPSG:4326', src.crs, f['geometry']),1) for f in collection['features']]
        restored = rasterize(geometries, out_shape=src.shape, transform=src.transform)
        assert np.array_equal(restored == 1, mask == 1)
    assert all(layer['bounds_crs'] == 'EPSG:4326' for layer in obs['layers'])
