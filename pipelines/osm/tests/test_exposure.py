"""Run from the repo root:  python -m pytest pipelines/osm/tests
No Geofabrik file or internet needed: the data is made up."""
import json

import geopandas as gpd
from shapely.geometry import LineString, box, mapping

from pipelines.osm import calculate_exposure

EVENT = {"event_id": "t1", "polygon": mapping(box(27.74, 45.59, 27.78, 45.62))}


def _fc(geoms, props=None):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": (props or [{}] * len(geoms))[i], "geometry": mapping(g)}
        for i, g in enumerate(geoms)]}


def _setup(tmp_path, flood_geoms):
    b = tmp_path / "buildings.geojson"
    r = tmp_path / "roads.geojson"
    f = tmp_path / "flood.geojson"
    b.write_text(json.dumps(_fc([box(27.752, 45.602, 27.7525, 45.6025),    # inside flood
                                 box(27.770, 45.610, 27.7705, 45.6105)])))  # outside
    r.write_text(json.dumps(_fc([LineString([(27.745, 45.605), (27.765, 45.605)])],
                                [{"fclass": "primary", "is_real_road": True}])))
    f.write_text(json.dumps(_fc(flood_geoms)))
    obs = {"source": "sentinel1", "status": "ready", "date": "2024-09-15",
           "files": [{"type": "flood_geojson", "path": str(f)}]}
    return {"buildings": str(b), "roads": str(r)}, obs


def test_exposure_counts(tmp_path):
    osm, obs = _setup(tmp_path, [box(27.750, 45.600, 27.760, 45.610)])
    res = calculate_exposure(EVENT, obs, osm, tmp_path / "out")
    s = res["summary"]
    assert res["status"] == "ready"
    assert s["buildings_exposed"] == 1 and s["buildings_total"] == 2
    assert s["buildings_mostly_flooded"] == 1  # the building is fully inside the flood
    assert 0.6 < s["roads_exposed_km"] < 0.9
    assert s["flooded_area_ha"] > 50
    assert {f["type"] for f in res["files"]} == {"exposed_buildings", "exposed_roads", "exposure_summary"}


def test_no_flood_gives_zeros(tmp_path):
    osm, obs = _setup(tmp_path, [])
    s = calculate_exposure(EVENT, obs, osm, tmp_path / "out")["summary"]
    assert s["buildings_exposed"] == 0 and s["roads_exposed_km"] == 0 and not s["flood_detected"]


def test_not_ready_is_skipped(tmp_path):
    osm, obs = _setup(tmp_path, [])
    obs["status"] = "waiting_for_data"
    assert calculate_exposure(EVENT, obs, osm, tmp_path / "out")["status"] == "skipped"


def test_sentinel1_format(tmp_path):
    osm, obs = _setup(tmp_path, [box(27.750, 45.600, 27.760, 45.610)])
    f = obs["files"][0]["path"]
    s1 = {"event_id": "t1", "source": "sentinel1", "status": "ready",
          "observations": [{"observation_id": "a", "acquisition_date": "2024-09-15",
                            "layers": [{"layer_type": "flood_extent", "local_path": f}]}]}
    res = calculate_exposure({"id": "t1", "aoi_geojson": EVENT["polygon"]}, s1, osm, tmp_path / "out")
    assert res["summary"]["buildings_exposed"] == 1
    assert res["summary"]["observation_date"] == "2024-09-15"


def test_sentinel2_format(tmp_path):
    osm, obs = _setup(tmp_path, [box(27.750, 45.600, 27.760, 45.610)])
    f = obs["files"][0]["path"]
    s2 = {"source": "sentinel2", "status": "ready", "files": {"flood_extent_geojson": f, "valid_mask": "valid_mask.tif"}}
    res = calculate_exposure({"id": "t1", "geometry": EVENT["polygon"]}, s2, osm, tmp_path / "out")
    assert res["summary"]["buildings_exposed"] == 1 and res["summary"]["valid_area_ha"] is None
