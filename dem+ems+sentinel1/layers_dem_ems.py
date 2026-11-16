"""Straturi pentru browser: Copernicus DEM + Copernicus EMS (EMSR758, AOI 03 Pechea).

Doua functii, fiecare intoarce o LISTA de dictionare in formatul cerut de aplicatie:

    {"id", "source", "period", "type", "url", "bounds", "acquired_at_utc", "status"}

  pregateste_straturi_dem(aoi)  -> 2 imagini PNG (elevatie cu relief, panta)
  pregateste_straturi_ems(aoi)  -> poligoane GeoJSON din EMS (AOI, inundatie, adancime, extindere maxima)

`aoi` = [vest, sud, est, nord] in grade (WGS84). `bounds` din rezultat are aceeasi ordine.
PNG-urile sunt in proiectia Web Mercator (ca sa se potriveasca exact pe harta din browser),
asa ca pot fi puse direct ca imagine cu colturile `bounds`.

Folosire (din radacina repo-ului):   python dem+ems+sentinel1/layers_dem_ems.py
Necesita: rasterio, numpy, matplotlib, pillow. Ruleaza dupa export_ems.py (citeste export/summary_ems.json).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from matplotlib import colormaps
from PIL import Image

# Aceeasi zona ca in notebook-uri: vest, sud, est, nord.
PECHEA_BOUNDS = [27.61, 45.46, 27.87, 45.74]

# Aceleasi intervale ca in notebook-uri (ultima zi exclusa, UTC).
INTERVALE = {
    "before": ("2024-08-15", "2024-09-14"),
    "during": ("2024-09-14", "2024-09-19"),
    "after": ("2024-09-19", "2024-10-04"),
}

DEM_PATH = Path("data/dem/dem_m.tif")
SLOPE_PATH = Path("data/dem/slope_deg.tif")
OUT_DIR = Path("export")          # aici se scriu PNG-urile; GeoJSON-urile sunt deja aici
URL_PREFIX = "/data/pechea"       # sub ce cale serveste aplicatia fisierele din OUT_DIR
NODATA = -9999
PIXEL_M_WEB = 20                  # rezolutia PNG-urilor pentru browser (sursa ramane 10 m)

# Scari fixe de culoare, ca sa fie la fel pe tot proiectul. Valorile reale: ~6-168 m, panta 0-~21 grade.
ELEV_MIN_M, ELEV_MAX_M = 0, 170
SLOPE_MAX_DEG = 15


# --- coordonate -------------------------------------------------------------------------
def utm35(lon, lat):
    """WGS84 lon/lat -> UTM 35N (EPSG:32635), in metri. Formula Kruger, fara pyproj."""
    a, f, k0, lon0 = 6378137.0, 1 / 298.257223563, 0.9996, math.radians(27.0)
    n = f / (2 - f)
    A = a / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    al = [n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16, 13 * n**2 / 48 - 3 * n**3 / 5, 61 * n**3 / 240]
    phi, lam = np.radians(lat), np.radians(lon) - lon0
    e = math.sqrt(f * (2 - f))
    t = np.sinh(np.arctanh(np.sin(phi)) - e * np.arctanh(e * np.sin(phi)))
    xi = np.arctan2(t, np.cos(lam))
    eta = np.arctanh(np.sin(lam) / np.sqrt(1 + t**2))
    x = eta + sum(c * np.cos(2 * (j + 1) * xi) * np.sinh(2 * (j + 1) * eta) for j, c in enumerate(al))
    y = xi + sum(c * np.sin(2 * (j + 1) * xi) * np.cosh(2 * (j + 1) * eta) for j, c in enumerate(al))
    return 500000 + k0 * A * x, k0 * A * y


def _y_mercator(lat_rad):
    return np.log(np.tan(np.pi / 4 + lat_rad / 2))


def perioada(acquired_at_utc):
    """'before' / 'during' / 'after' dupa data scenei, sau None daca e in afara intervalelor."""
    zi = acquired_at_utc[:10]
    for nume, (start, sfarsit) in INTERVALE.items():
        if start <= zi < sfarsit:
            return nume
    return None


def _strat(id_, source, period, tip, url, bounds, acquired, status="available"):
    return {"id": id_, "source": source, "period": period, "type": tip, "url": url,
            "bounds": bounds, "acquired_at_utc": acquired, "status": status}


# --- raster -> PNG pe grila Web Mercator ---------------------------------------------------
def _citeste(cale):
    with rasterio.open(cale) as src:
        a = src.read(1).astype("float32")
        b = src.bounds
    a[(a == NODATA) | ~np.isfinite(a)] = np.nan   # NaN = in afara zonei / fara date
    return a, b.left, b.top, (b.right - b.left) / a.shape[1]


def _grila_web(aoi, pixel_m):
    """Coordonatele UTM ale centrelor pixelilor unei grile Web Mercator peste `aoi`."""
    w, s, e, n = aoi
    R = 6378137.0
    lat0 = math.radians((s + n) / 2)
    latitudine_rad = lambda v: math.radians(v)
    latime = max(int(round(math.radians(e - w) * R * math.cos(lat0) / pixel_m)), 2)
    ys, yn = _y_mercator(latitudine_rad(s)), _y_mercator(latitudine_rad(n))
    inaltime = max(int(round(latime * (yn - ys) / math.radians(e - w))), 2)
    lon = w + (np.arange(latime) + 0.5) / latime * (e - w)
    y = yn - (np.arange(inaltime) + 0.5) / inaltime * (yn - ys)
    lat = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
    lon2d, lat2d = np.broadcast_arrays(lon[None, :], lat[:, None])
    return utm35(lon2d, lat2d)


def _esantioneaza(arr, left, top, px, X, Y):
    """Interpolare bilineara; NaN unde lipsesc date sau in afara rasterului."""
    h, w = arr.shape
    c, r = (X - left) / px - 0.5, (top - Y) / px - 0.5
    c0, r0 = np.floor(c).astype(int), np.floor(r).astype(int)
    fc, fr = c - c0, r - r0
    ok = (c0 >= 0) & (c0 + 1 < w) & (r0 >= 0) & (r0 + 1 < h)
    c0, r0 = np.clip(c0, 0, w - 2), np.clip(r0, 0, h - 2)
    v = (arr[r0, c0] * (1 - fc) * (1 - fr) + arr[r0, c0 + 1] * fc * (1 - fr)
         + arr[r0 + 1, c0] * (1 - fc) * fr + arr[r0 + 1, c0 + 1] * fc * fr)
    v[~ok] = np.nan
    return v


def _scrie_png(valori, cmap, vmin, vmax, cale, umbra=None):
    t = np.clip((valori - vmin) / (vmax - vmin), 0, 1)
    rgba = colormaps[cmap](np.nan_to_num(t))
    if umbra is not None:
        rgba[..., :3] *= (0.6 + 0.4 * np.nan_to_num(umbra, nan=0.7))[..., None]
    rgba[..., 3] = np.where(np.isnan(valori), 0.0, 1.0)     # transparent in afara zonei
    Image.fromarray((np.clip(rgba, 0, 1) * 255).astype("uint8"), "RGBA").save(cale, optimize=True)


def _hillshade(dem, px):
    dy, dx = np.gradient(np.nan_to_num(dem, nan=float(np.nanmean(dem))), px)
    panta, aspect = np.arctan(np.hypot(dx, dy)), np.arctan2(-dx, dy)
    h = (np.sin(np.radians(45)) * np.cos(panta)
         + np.cos(np.radians(45)) * np.sin(panta) * np.cos(np.radians(315) - aspect))
    h[np.isnan(dem)] = np.nan
    return h


# --- 1. DEM ---------------------------------------------------------------------------------
def pregateste_straturi_dem(aoi=PECHEA_BOUNDS, *, dem_path=DEM_PATH, slope_path=SLOPE_PATH,
                            out_dir=OUT_DIR, url_prefix=URL_PREFIX, pixel_m=PIXEL_M_WEB):
    """PNG pentru elevatie (cu relief) si panta. DEM-ul e static: nu are data de achizitie."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = "Copernicus DEM GLO-30"
    straturi = []
    X = Y = None
    for id_, cale, cmap, vmin, vmax, cu_relief in (
        ("dem_elevation", dem_path, "terrain", ELEV_MIN_M, ELEV_MAX_M, True),
        ("dem_slope", slope_path, "YlOrRd", 0, SLOPE_MAX_DEG, False),
    ):
        if not Path(cale).exists():
            straturi.append(_strat(id_, source, "static", "image", None, None, None, "unavailable"))
            continue
        arr, left, top, px = _citeste(cale)
        if X is None:
            X, Y = _grila_web(aoi, pixel_m)
        valori = _esantioneaza(arr, left, top, px, X, Y)
        umbra = _esantioneaza(_hillshade(arr, px), left, top, px, X, Y) if cu_relief else None
        _scrie_png(valori, cmap, vmin, vmax, out_dir / f"{id_}.png", umbra)
        straturi.append(_strat(id_, source, "static", "image", f"{url_prefix}/{id_}.png",
                               list(aoi), None, "available"))
    return straturi


# --- 2. EMS ---------------------------------------------------------------------------------
def _coordonate(g):
    if isinstance(g, (list, tuple)) and g and isinstance(g[0], (int, float)):
        yield g
    elif isinstance(g, (list, tuple)):
        for x in g:
            yield from _coordonate(x)


def _bounds_geojson(cale):
    pct = [p for ft in json.loads(Path(cale).read_text(encoding="utf-8"))["features"]
           if ft.get("geometry") for p in _coordonate(ft["geometry"]["coordinates"])]
    if not pct:
        return None
    lon, lat = [p[0] for p in pct], [p[1] for p in pct]
    return [round(min(lon), 5), round(min(lat), 5), round(max(lon), 5), round(max(lat), 5)]


def pregateste_straturi_ems(aoi=PECHEA_BOUNDS, *, export_dir=OUT_DIR, url_prefix=URL_PREFIX):
    """Poligoane EMS ca GeoJSON (type 'vector'), cu data si ora reala a imaginii folosite de EMS.

    Citeste export/summary_ems.json (scris de export_ems.py). `aoi` e doar pentru semnatura
    comuna cu celelalte functii: GeoJSON-urile sunt deja taiate la zona in export_ems.py.
    """
    export_dir = Path(export_dir)
    sumar = json.loads((export_dir / "summary_ems.json").read_text(encoding="utf-8"))
    source = "Copernicus EMS"
    fisiere = [("ems_aoi", sumar["files"]["aoi"], "static", None)]
    for cheie, produs in sumar["products"].items():
        data = produs["acquired_at_utc"]
        for rol in ("flood", "depth", "max_extent"):
            if rol in produs["files"]:
                fisiere.append((f"ems_{cheie}_{rol}", produs["files"][rol], perioada(data), data))

    straturi = []
    for id_, nume, period, data in fisiere:
        cale = export_dir / nume
        if not cale.exists():
            straturi.append(_strat(id_, source, period, "vector", None, None, data, "unavailable"))
            continue
        straturi.append(_strat(id_, source, period, "vector", f"{url_prefix}/{nume}",
                               _bounds_geojson(cale), data, "available"))
    return straturi


if __name__ == "__main__":
    toate = pregateste_straturi_dem() + pregateste_straturi_ems()
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "layers_dem_ems.json").write_text(
        json.dumps(toate, indent=2, ensure_ascii=False), encoding="utf-8")
    for s in toate:
        print(f"{s['id']:24s} {s['type']:7s} {s['period']:7s} {s['status']:12s} {s['acquired_at_utc']}")
    print("\nscris:", OUT_DIR / "layers_dem_ems.json")