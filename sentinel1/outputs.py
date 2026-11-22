"""Fisiere locale pentru analiza si harta web."""
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.features import shapes
from rasterio.transform import array_bounds, from_bounds
from rasterio.warp import transform_bounds, transform_geom, reproject, Resampling


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def geographic_bounds(grid):
    return list(transform_bounds(grid["crs"], "EPSG:4326",
                *array_bounds(grid["height"], grid["width"], grid["transform"]), densify_pts=21))


def read_shadow(path, grid):
    # Masca trebuie sa fie deja aliniata si specifica trecerii radar.
    with rasterio.open(path) as src:
        if (src.count != 1 or src.crs.to_string() != grid["crs"]
                or src.shape != (grid["height"], grid["width"])
                or not src.transform.almost_equals(grid["transform"])):
            raise ValueError("Shadow mask must match the shared grid exactly")
        data = src.read(1, masked=True).astype("float32").filled(np.nan)
    if not np.isin(data[np.isfinite(data)], [0, 1]).all():
        raise ValueError("Shadow mask values must be 0=clear, 1=shadow/layover, or nodata")
    return data


def vectorize(binary, grid, acquired_at, classification):
    features = []
    for geom, value in shapes(binary.astype("uint8"), mask=binary,
                              transform=grid["transform"], connectivity=4):
        features.append({"type": "Feature", "geometry": transform_geom(grid["crs"], "EPSG:4326", geom),
                         "properties": {"classification": classification, "acquired_at": acquired_at}})
    return {"type": "FeatureCollection", "features": features}


def save_preview(current, grid, path, band):
    # PNG in Web Mercator; marginile sunt returnate in longitudine/latitudine.
    bounds = transform_bounds(grid["crs"], "EPSG:3857",
                              *array_bounds(grid["height"], grid["width"], grid["transform"]), densify_pts=21)
    x0, y0, x1, y1 = bounds
    scale = max(x1 - x0, y1 - y0) / 1400
    width, height = max(1, round((x1 - x0) / scale)), max(1, round((y1 - y0) / scale))
    affine = from_bounds(*bounds, width, height)
    source = np.where(grid["inside"], current, np.nan).astype("float32")
    dest = np.full((height, width), np.nan, dtype="float32")
    reproject(source, dest, src_transform=grid["transform"], src_crs=grid["crs"],
              dst_transform=affine, dst_crs="EPSG:3857", src_nodata=np.nan,
              dst_nodata=np.nan, resampling=Resampling.nearest)
    low, high = (-25, 0) if band == "VV" else (-30, -5)
    gray = (np.clip((np.nan_to_num(dest, nan=low) - low) / (high - low), 0, 1) * 255).astype("uint8")
    rgba = np.dstack([gray, gray, gray, (np.isfinite(dest) * 255).astype("uint8")])
    Image.fromarray(rgba).save(path)
    return list(transform_bounds("EPSG:3857", "EPSG:4326", *bounds)), [low, high]


def export_observation(folder, stack, mask, valid, grid, observation, options, raw=None, quality_flags=None):
    folder.mkdir(parents=True, exist_ok=True)
    bounds = geographic_bounds(grid)
    layers = []

    def layer(kind, format_, path, crs, bbox=bounds, **extra):
        layers.append({"layer_type": kind, "format": format_, "local_path": str(path.resolve()),
                       "bounds": bbox, "crs": crs, "bounds_crs": "EPSG:4326", **extra})

    mask_path = folder / "flood_mask.tif"
    with rasterio.open(mask_path, "w", driver="GTiff", width=grid["width"], height=grid["height"],
                       count=1, dtype="uint8", crs=grid["crs"], transform=grid["transform"],
                       nodata=255, compress="deflate") as dst:
        dst.write(mask, 1)
        dst.update_tags(classes="0=no_detection,1=potential_flood,255=unknown_or_excluded",
                        acquired_at=observation["acquired_at"])
    layer("flood_mask", "geotiff", mask_path, grid["crs"])
    for kind, array, nodata in (("flood_mask_raw", raw, 255), ("quality_flags", quality_flags, None)):
        if array is None:
            continue
        path = folder / f"{kind}.tif"
        with rasterio.open(path, "w", driver="GTiff", width=grid["width"], height=grid["height"],
                           count=1, dtype=str(array.dtype), crs=grid["crs"], transform=grid["transform"],
                           nodata=nodata, compress="deflate") as dst:
            dst.write(array, 1)
            dst.update_tags(acquired_at=observation["acquired_at"])
            if kind == "quality_flags":
                from .analysis import QUALITY_BITS
                dst.update_tags(quality_bits=json.dumps(QUALITY_BITS),
                                interpretation="Bit flags can overlap; not all flags exclude analysis")
        layer(kind, "geotiff", path, grid["crs"])
    for kind, binary, label in (("flood_extent", mask == 1, "potential_flood"),
                                ("valid_coverage", valid, "valid_analysis")):
        path = folder / f"{kind}.geojson"
        write_json(path, vectorize(binary, grid, observation["acquired_at"], label))
        layer(kind, "geojson", path, "EPSG:4326")
    path = folder / f"radar_{options['band'].lower()}.png"
    bbox, limits = save_preview(stack[1], grid, path, options["band"])
    layer("satellite_image", "png", path, "EPSG:3857", bbox,
          band=options["band"], display_range_db=limits, bounds_crs="EPSG:4326")
    return layers


def export_context_layers(folder, grid, observation, limitations, landcover_info, comparison=None):
    """Layere suplimentare pentru harta si compararea benzilor."""
    from .comparison import LIMITATION_CLASSES
    layers = []
    bounds = geographic_bounds(grid)

    def add(kind, format_, path, **extra):
        layers.append({'layer_type': kind, 'format': format_, 'local_path': str(path.resolve()),
                       'bounds': bounds, 'bounds_crs': 'EPSG:4326',
                       'crs': 'EPSG:4326' if format_ == 'geojson' else grid['crs'], **extra})

    def raster(kind, array, legend):
        path = folder / f'{kind}.tif'
        with rasterio.open(path, 'w', driver='GTiff', width=grid['width'], height=grid['height'],
                           count=1, dtype='uint8', crs=grid['crs'], transform=grid['transform'],
                           nodata=255, compress='deflate') as dst:
            dst.write(array, 1)
            dst.update_tags(classes=json.dumps(legend), acquired_at=observation['acquired_at'])
        add(kind, 'geotiff', path, classes=legend)

    if landcover_info['requested']:
        raster('landcover_limitations', limitations, LIMITATION_CLASSES)
        path = folder / 'landcover_limitations.geojson'
        features = []
        for code in (1, 2, 3):
            # Data radar este separata de anul referintei de acoperire a terenului.
            part = vectorize(limitations == code, grid, observation['acquired_at'], LIMITATION_CLASSES[code])
            for feature in part['features']:
                feature['properties'].update(reference_year=landcover_info['reference_year'],
                                             source=landcover_info['asset'], is_flood_evidence=False)
            features.extend(part['features'])
        write_json(path, {'type': 'FeatureCollection', 'features': features})
        add('landcover_limitations', 'geojson', path, reference_year=landcover_info['reference_year'])
    if comparison is not None:
        classes, agreement, common, report = comparison
        raster('polarization_comparison', classes, {0:'neither', 1:'VV_only', 2:'VH_only', 3:'both', 255:'unknown_or_excluded'})
        raster('flood_mask_agreement', agreement, {0:'no_joint_detection', 1:'both_bands_potential_flood', 255:'unknown_or_excluded'})
        for kind, binary, label in (
            ('flood_extent_agreement', agreement == 1, 'both_bands_potential_flood'),
            ('comparison_valid_coverage', common, 'common_valid_VV_VH'),
        ):
            path = folder / f'{kind}.geojson'
            write_json(path, vectorize(binary, grid, observation['acquired_at'], label))
            add(kind, 'geojson', path, combination='VV_AND_VH')
    return layers
