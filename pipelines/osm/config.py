"""Settings that do NOT depend on an event. No coordinates or dates here."""
import os
from pathlib import Path

# Repo root, found from this file (works from any working directory)
ROOT = Path(__file__).resolve().parents[2]

# Metric CRS for lengths/areas (Romania Stereo 70). Outside Romania we fall back to UTM.
MEASURE_CRS = 3844
STORE_CRS = 4326

# Where the Geofabrik Romania extract (unzipped .shp.zip) lives.
GEOFABRIK_DIR = Path(os.getenv("OSM_GEOFABRIK_DIR", ROOT / "data" / "raw" / "romania"))

# Cache for Microsoft tiles and the index (safe to delete, it is re-downloaded).
CACHE_DIR = Path(os.getenv("OSM_CACHE_DIR", ROOT / "data" / "raw" / "cache"))

MS_INDEX_URL = os.getenv(
    "MS_BUILDINGS_INDEX_URL",
    "https://bfppub.blob.core.windows.net/%24web/2026-07-24/dataset-links.csv",
)
MS_COUNTRY = "Romania" 
MS_ZOOM = 9

# Geofabrik road classes that are field tracks / paths, not real roads.
REAL_ROADS = [
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link",
    "unclassified", "residential", "living_street", "service",
]

FARM_CLASSES = ["farmland", "meadow", "orchard", "vineyard"]

MOSTLY_FLOODED_PCT = 50
NOTE = "Potential exposure at 10 m resolution, not confirmed damage."
