"""Cautare si descarcare din Earth Engine. Autentificarea se face separat."""
import numpy as np
import requests
import ee
from affine import Affine
from rasterio.io import MemoryFile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

COLLECTION = "COPERNICUS/S1_GRD"
WATER_ASSET = "JRC/GSW1_4/YearlyHistory"
DEM_ASSET = "COPERNICUS/DEM/GLO30_2024_1"
NODATA = -9999.0


def discover(event, dates):
    aoi = ee.Geometry(event["aoi"], proj="EPSG:4326", geodesic=False)
    collection = (ee.ImageCollection(COLLECTION).filterBounds(aoi)
                  .filterDate(dates["baseline_start"], dates["search_end"])
                  .filter(ee.Filter.eq("instrumentMode", "IW"))
                  .filter(ee.Filter.eq("resolution_meters", 10))
                  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
                  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))

    def record(image):
        return image.set("record", {
            "asset_id": ee.String(COLLECTION + "/").cat(image.get("system:index")),
            "acquired_at": image.date().format("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", "UTC"),
            "mode": image.get("instrumentMode"),
            "relative_orbit": image.get("relativeOrbitNumber_start"),
            "absolute_orbit": image.get("orbitNumber_start"),
            "direction": image.get("orbitProperties_pass"),
            "polarizations": image.get("transmitterReceiverPolarisation"),
            "platform": image.get("platform_number"),
            "datatake": image.get("missionDataTakeID"),
            "slice": image.get("sliceNumber"),
        })

    records = collection.map(record).aggregate_array("record").getInfo()
    from .core import utc
    for item in records:
        if any(item[k] is None for k in item):
            raise ValueError("Scene has missing orbit/slice metadata; cannot compare safely")
        item["acquired_at"] = utc(item["acquired_at"])
    return records


def mosaic(observation, band):
    images = []
    for record in sorted(observation["records"], key=lambda r: r["asset_id"]):
        image = ee.Image(record["asset_id"])
        # Pastram numai pixelii valizi in ambele polarizari si in unghi.
        valid = image.select(["VV", "VH", "angle"]).mask().reduce(ee.Reducer.min())
        images.append(image.select([band, "angle"]).updateMask(valid))
    return ee.ImageCollection.fromImages(images).mosaic()


def build_stack(event, observation, baseline, grid, options):
    band = options["band"]
    # Proiectam fiecare trecere inainte de calculul statisticilor.
    def aligned(obs):
        return mosaic(obs, band).reproject(crs=grid["crs"], crsTransform=list(grid["transform"])[:6])

    old = ee.ImageCollection.fromImages([aligned(obs) for obs in baseline])
    current = aligned(observation)

    def power(image):
        return ee.Image.constant(10).pow(image.select(band).divide(10)).rename("power")

    # Mediana puterii liniare se transforma inapoi in dB.
    before = old.map(power).median().log10().multiply(10).rename("baseline_db")
    count = old.select(band).count().rename("baseline_count")
    old_angle = old.select("angle").median().rename("baseline_angle")
    water = ee.Image.constant(0).rename("water_class")
    if options["use_permanent_water"]:
        water = (ee.ImageCollection(WATER_ASSET)
                 .filter(ee.Filter.eq("year", options["water_reference_year"]))
                 .first().select("waterClass").rename("water_class"))
    slope = ee.Image.constant(0).rename("slope")
    if options["use_dem"]:
        dem = ee.ImageCollection(DEM_ASSET).select("DEM").mosaic()
        # Panta se calculeaza la 30 m, nu pe proiectia implicita a mozaicului.
        slope = ee.Terrain.slope(dem.reproject(crs=grid["crs"], scale=30)).rename("slope")
    return (before.addBands(current.select(band).rename("event_db"))
            .addBands(count).addBands(old_angle)
            .addBands(current.select("angle").rename("event_angle"))
            .addBands(water).addBands(slope).toFloat().unmask(NODATA, False))


def download_stack(image, grid):
    """Descarcam dale mici pe exact aceeasi grila."""
    array = np.full((7, grid["height"], grid["width"]), np.nan, dtype="float32")
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retries))
        # 512 x 512 x 7 x 4 octeti este sub limita EE de 32 MB.
        for row in range(0, grid["height"], 512):
            for col in range(0, grid["width"], 512):
                height = min(512, grid["height"] - row)
                width = min(512, grid["width"] - col)
                affine = Affine(10, 0, grid["transform"].c + col * 10,
                                0, -10, grid["transform"].f - row * 10)
                url = image.getDownloadURL({
                    "crs": grid["crs"], "crs_transform": list(affine)[:6],
                    "dimensions": [width, height], "format": "GEO_TIFF",
                })
                response = session.get(url, timeout=(30, 180))
                response.raise_for_status()
                with MemoryFile(response.content) as memory, memory.open() as src:
                    if (src.count != 7 or src.width != width or src.height != height
                            or src.crs.to_string() != grid["crs"]
                            or not src.transform.almost_equals(affine)):
                        raise ValueError("Earth Engine returned an unexpected grid")
                    tile = src.read().astype("float32")
                    tile[tile == NODATA] = np.nan
                    array[:, row:row + height, col:col + width] = tile
    return array
