"""Comparam referinta de apa in proiectia nativa si pe grila evenimentului."""
import argparse
import json
from pathlib import Path
import ee
from .core import validate, make_grid
from .earth_engine import WATER_ASSET


def diagnose_water(event):
    dates, options = validate(event)
    grid = make_grid(event, options['max_pixels'])
    year = min(int(dates['event_start'][:4]) - 1, 2021)
    region = ee.Geometry(event['aoi'], proj='EPSG:4326', geodesic=False)
    collection = ee.ImageCollection(WATER_ASSET).filter(ee.Filter.eq('year', year))
    size = collection.size().getInfo()
    report = {'asset': WATER_ASSET, 'year': year, 'images': size}
    if not size:
        return {**report, 'reason': 'No image for this reference year'}
    water = ee.Image(collection.first()).select('waterClass')
    report['image_id'] = water.id().getInfo()
    report['native_projection'] = water.projection().getInfo()
    # -9999 inseamna mascat; clasa 0 inseamna fara date in produs.
    report['native_class_histogram'] = water.unmask(-9999, False).reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(), geometry=region,
        crs=water.projection(), scale=30, maxPixels=options['max_pixels'] * 2,
    ).getInfo()
    report['grid_class_histogram'] = water.unmask(-9999, False).reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(), geometry=region,
        crs=grid['crs'], crsTransform=list(grid['transform'])[:6],
        maxPixels=options['max_pixels'] * 2,
    ).getInfo()
    report['note'] = 'Counts differ with pixel spacing. Compare class presence and missing fractions, not raw totals.'
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', required=True)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    ee.Initialize(project=args.project)
    event = json.loads(Path(args.event).read_text(encoding='utf-8'))
    print(json.dumps(diagnose_water(event), indent=2))


if __name__ == '__main__':
    main()
