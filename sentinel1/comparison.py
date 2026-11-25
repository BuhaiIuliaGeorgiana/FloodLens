"""Context spatial, polarizari separate si limite de interpretare."""
import numpy as np
from . import earth_engine as backend
from .core import classify, context_grid, options_for_band
from .analysis import analyze, choose_threshold, QUALITY_BITS

LANDCOVER_CODES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
VEGETATION_CODES = [10, 20, 30, 40, 90, 95, 100]
LIMITATION_CLASSES = {
    0: 'other_mapped_landcover_not_a_reliability_guarantee',
    1: 'built_up_detection_limited', 2: 'vegetated_detection_limited',
    3: 'landcover_unknown', 255: 'outside_aoi',
}


def load_context(event, dates, grid, options):
    work, crop = context_grid(event, grid, options)
    landcover = np.full(work['inside'].shape, np.nan, dtype='float32')
    source = backend.landcover_source(dates['event_start'])
    info = {**source, 'requested': options['use_landcover'], 'status': 'unavailable',
            'reason': None, 'resampling': 'nearest',
            'interpretation': 'Historical context, not flood evidence or detector accuracy.',
            'attribution': 'ESA WorldCover Consortium, CC BY 4.0',
            'temporal_policy': 'Reference calendar year ends before event_start; historical product availability at event time is not simulated.'}
    if not options['use_landcover']:
        info['reason'] = 'Land-cover context disabled; limitation layer is unknown.'
    elif source['asset'] is None:
        info['reason'] = 'No supported WorldCover reference year earlier than this event.'
    else:
        try:
            landcover = backend.download_landcover(source, work)
            if landcover.shape != work['inside'].shape:
                raise ValueError('Unexpected land-cover grid dimensions')
            info['status'] = 'available'
        except Exception as error:
            info['reason'] = f'Land-cover retrieval failed: {type(error).__name__}: {error}'
            landcover = np.full(work['inside'].shape, np.nan, dtype='float32')
    aoi_classes = landcover[crop]
    known = np.isin(aoi_classes, LANDCOVER_CODES) & grid['inside']
    info['aoi_reference_coverage_pct'] = float(100 * known.sum() / grid['inside'].sum())
    if options['use_landcover'] and info['status'] == 'available' and not np.all(known[grid['inside']]):
        info.update(status='partial', reason='Land-cover reference is missing or invalid for part of the AOI.')
    info['class_counts_on_aoi_grid'] = {str(c): int((grid['inside'] & (aoi_classes == c)).sum()) for c in LANDCOVER_CODES}
    limitation = np.full(grid['inside'].shape, 255, dtype='uint8')
    limitation[grid['inside']] = 3
    limitation[known] = 0
    limitation[grid['inside'] & (aoi_classes == 50)] = 1
    limitation[grid['inside'] & np.isin(aoi_classes, VEGETATION_CODES)] = 2
    return {'grid': work, 'crop': crop, 'landcover': landcover,
            'landcover_info': info, 'limitations': limitation}


def analyze_band(event, obs, baseline, grid, context, options, band, shadow):
    settings = options_for_band(options, band)
    work, crop = context['grid'], context['crop']
    stack = backend.download_stack(backend.build_stack(event, obs, baseline, work, settings), work)
    threshold = None
    if settings['threshold_method'] == 'tile_otsu':
        # Apa permanenta este utila pentru separarea apa/uscat, dar se exclude la detectie.
        _, samples = classify(stack, work['inside'], {**settings, 'use_permanent_water': False})
        if shadow is not None:
            samples[crop] &= np.isfinite(shadow) & (shadow == 0)
        lc = context['landcover']
        # Nu estimam pragul din cladiri sau zapada cunoscuta.
        samples &= ~np.isin(lc, [50, 70])
        threshold = choose_threshold(stack[1], samples, settings)
        threshold.update(
            estimation_domain='buffered AOI on shared grid; output cropped to original AOI',
            buffer_m=settings['threshold_buffer_m'], sample_pixel_count=int(samples.sum()),
            aoi_sample_pixel_count=int((samples[crop] & grid['inside']).sum()),
            unknown_landcover_sample_count=int((samples & ~np.isin(lc, LANDCOVER_CODES)).sum()),
            sampling_grid={'crs': work['crs'], 'transform': list(work['transform'])[:6],
                           'width': work['width'], 'height': work['height']},
            exclusions='missing/comparability radar checks, configured slope, known built-up/snow; permanent water retained for sampling',
            shadow_screening='Supplied shadow mask applied within AOI only; buffer is not shadow-screened.',
            scene_scope='Same acquisition groups and scene IDs as the AOI; no unrelated buffer-only scenes added.',
        )
    # Copia elibereaza matricea mare a bufferului dupa procesarea acestei benzi.
    aoi_stack = stack[(slice(None), *crop)].copy()
    del stack
    mask, valid, raw, flags, report = analyze(aoi_stack, grid['inside'], settings, shadow, threshold)
    limitations = context['limitations']
    flags[limitations == 1] |= QUALITY_BITS['urban_limitation']
    flags[limitations == 2] |= QUALITY_BITS['vegetation_limitation']
    flags[limitations == 3] |= QUALITY_BITS['landcover_unknown']
    report['landcover_breakdown'] = stratify(mask, valid, limitations)
    coverage = float(100 * valid.sum() / grid['inside'].sum())
    report.update(valid_coverage_pct=coverage, meets_min_coverage=coverage >= options['min_coverage_pct'],
                  valid_pixel_count=int(valid.sum()), potential_flood_pixel_count=int((mask == 1).sum()))
    return {'stack': aoi_stack, 'mask': mask, 'valid': valid, 'raw': raw,
            'flags': flags, 'quality': report, 'settings': settings}


def stratify(mask, valid, limitations):
    result = {}
    for code, label in LIMITATION_CLASSES.items():
        if code == 255:
            continue
        region = limitations == code
        count = int((valid & region).sum())
        detected = int(((mask == 1) & region).sum())
        result[label] = {'aoi_pixel_count': int(region.sum()), 'valid_pixel_count': count,
                         'potential_flood_pixel_count': detected, 'potential_flood_area_ha': detected / 100}
    return result


def compare_masks(vv, vh, limitations):
    """Acordul intre benzi nu este o masura a preciziei."""
    common = vv['valid'] & vh['valid']
    left, right = vv['mask'] == 1, vh['mask'] == 1
    classes = np.full(common.shape, 255, dtype='uint8')
    classes[common] = left[common].astype('uint8') + 2 * right[common].astype('uint8')
    agreement = np.full(common.shape, 255, dtype='uint8')
    agreement[common] = (left & right)[common].astype('uint8')
    union = int((common & (left | right)).sum())
    both = int((classes == 3).sum())
    report = {
        'status': 'available' if common.any() else 'unavailable',
        'reason': None if common.any() else 'No common valid VV/VH pixels; no agreement conclusion.',
        'combination': 'intersection of cleaned VV and VH candidates, only on common valid coverage',
        'common_valid_pixel_count': int(common.sum()),
        'vv_only_pixel_count': int((classes == 1).sum()),
        'vh_only_pixel_count': int((classes == 2).sum()),
        'both_pixel_count': both, 'neither_pixel_count': int((classes == 0).sum()),
        'union_candidate_pixel_count': union,
        'interband_iou_not_accuracy': both / union if union else None,
        'warning': 'Bands are correlated. Agreement is not truth, confidence or accuracy; intersection can miss genuine flooding.',
        'landcover_breakdown': {},
    }
    for code, label in LIMITATION_CLASSES.items():
        if code != 255:
            region = limitations == code
            report['landcover_breakdown'][label] = {
                'common_valid_pixel_count': int((region & common).sum()),
                'vv_only': int((region & (classes == 1)).sum()),
                'vh_only': int((region & (classes == 2)).sum()),
                'both': int((region & (classes == 3)).sum()),
            }
    return classes, agreement, common, report
