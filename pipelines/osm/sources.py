"""Reading raw data. Everything here takes a bbox (west, south, east, north)
in EPSG:4326 and returns a GeoDataFrame in EPSG:4326."""
import gzip
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import geopandas as gpd
import mercantile
import pandas as pd
import pyogrio

from . import config
from .geo_utils import OsmDataError, clean


def read_osm_roads(bbox):
    path = Path(config.GEOFABRIK_DIR) / "gis_osm_roads_free_1.shp"
    if not path.exists():
        raise OsmDataError(
            f"Geofabrik roads file not found: {path}. "
            "Set OSM_GEOFABRIK_DIR to the unzipped Romania extract."
        )
    gdf = pyogrio.read_dataframe(path, bbox=tuple(bbox))  # reads only the event area
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    gdf = gdf.to_crs(4326)
    keep = [c for c in ("osm_id", "name", "fclass") if c in gdf.columns]
    gdf = gdf[keep + ["geometry"]]
    return clean(gdf) if len(gdf) else gdf


def _download(url, dest, retries=3):
    dest = Path(dest)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(retries):
        try:
            urllib.request.urlretrieve(url, tmp)
            tmp.replace(dest)
            return dest
        except Exception as exc:
            if attempt == retries - 1:
                raise OsmDataError(f"download failed: {url} ({exc})")
            time.sleep(2 * (attempt + 1))


def _ms_index():
    tag = hashlib.sha1(config.MS_INDEX_URL.encode()).hexdigest()[:8]
    path = _download(config.MS_INDEX_URL, Path(config.CACHE_DIR) / f"ms_index_{tag}.csv")
    df = pd.read_csv(path, dtype=str)  # str keeps leading zeros in QuadKey
    return df[df["Location"] == config.MS_COUNTRY]


def read_ms_buildings(bbox):
    """Microsoft ML building footprints that fall in the bbox. Tiles are cached."""
    w, s, e, n = bbox
    quadkeys = {mercantile.quadkey(t) for t in mercantile.tiles(w, s, e, n, zooms=config.MS_ZOOM)}
    rows = _ms_index()
    rows = rows[rows["QuadKey"].isin(quadkeys)]

    parts = []
    for _, row in rows.iterrows():
        tile = _download(row["Url"], Path(config.CACHE_DIR) / "ms_tiles" / f"{row['QuadKey']}.gz")
        with gzip.open(tile, "rt", encoding="utf-8") as f:
            feats = [json.loads(line) for line in f if line.strip()]
        if feats:
            parts.append(gpd.GeoDataFrame.from_features(feats, crs=4326))

    if not parts:  # area outside the dataset: empty, not an error
        return gpd.GeoDataFrame(geometry=[], crs=4326)
    gdf = pd.concat(parts, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=4326).cx[w:e, s:n]
    cols = [c for c in ("height", "confidence", "geometry") if c in gdf.columns]
    return clean(gdf[cols])
