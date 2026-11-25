"""Verificari locale pentru apa lipsa, praguri si masti."""
import numpy as np
import pytest
from sentinel1.core import DEFAULTS, classify, validate
from sentinel1.analysis import analyze, QUALITY_BITS, choose_threshold


def stack_for(shape):
    stack = np.zeros((7, *shape), dtype='float32')
    stack[0] = -10
    stack[1] = -20
    stack[2] = 3
    stack[3:5] = 35
    stack[5] = 1
    return stack


@pytest.mark.parametrize('policy', ['partial', 'strict'])
def test_patchy_water_excludes_known_water_and_preserves_missing_radar(policy):
    stack = stack_for((1, 6))
    stack[5, 0] = [1, 3, np.nan, 0, 2, np.nan]
    stack[0, 0, 5] = np.nan
    settings = {**DEFAULTS, 'missing_water_policy': policy, 'min_patch_area_m2': 0}
    mask, valid, raw, flags, report = analyze(stack, np.ones((1, 6), bool), settings)
    assert mask.tolist() == ([[1, 255, 1, 1, 1, 255]] if policy == 'partial' else [[1, 255, 255, 255, 1, 255]])
    assert flags[0, 1] & QUALITY_BITS['water_excluded']
    assert flags[0, 2] & QUALITY_BITS['water_reference_missing']
    assert flags[0, 5] & QUALITY_BITS['missing_radar']
    assert report['remaining_pixels_after_checks']['shadow_excluded_or_missing'] == valid.sum()
    assert report['water_unscreened_valid_pixel_count'] == (2 if policy == 'partial' else 0)


def test_cleaning_respects_nodata_connectivity_and_area():
    stack = stack_for((5, 5)); stack[1] = -11
    stack[1, 0, 0] = -20
    stack[1, 1, 1] = -20
    stack[1, 3, 1:4] = -20
    stack[0, 2] = np.nan
    mask, valid, raw, flags, report = analyze(stack, np.ones((5, 5), bool), DEFAULTS)
    assert (raw == 1).sum() == 5
    assert (mask == 1).sum() == 3
    assert np.all(mask[2] == 255)
    assert report['removed_small_patch_pixel_count'] == 2
    assert flags[0, 0] & QUALITY_BITS['small_patch_removed']
    assert report['potential_flood_area_ha'] == .03


def test_adaptive_selects_reproducible_separable_tiles():
    rng = np.random.default_rng(83)
    current = rng.normal(-12, 1, (64, 64))
    for row in (0, 32):
        for col in (0, 32):
            current[row:row+32, col:col+16] = rng.normal(-23, 1, (32, 16))
    options = {**DEFAULTS, 'threshold_method': 'tile_otsu', 'tile_size': 32}
    result = choose_threshold(current, np.ones_like(current, bool), options)
    assert result['used_method'] == 'tile_otsu'
    assert len(result['accepted_tiles']) == 4
    assert -23 < result['water_db'] < -12
    assert result['fallback_reason'] is None


@pytest.mark.parametrize('kind', ['constant', 'no_valid', 'unimodal', 'small_water_class'])
def test_adaptive_rejects_unsuitable_histograms(kind):
    rng = np.random.default_rng(4)
    current = np.full((64, 64), -12.0)
    valid = np.ones_like(current, bool)
    if kind == 'no_valid': valid[:] = False
    if kind == 'unimodal': current[:] = rng.normal(-12, .5, current.shape)
    if kind == 'small_water_class': current[:1, :1] = -23
    result = choose_threshold(current, valid, {**DEFAULTS, 'threshold_method': 'tile_otsu', 'tile_size': 32})
    assert result['used_method'] == 'fixed'
    assert result['water_db'] == DEFAULTS['water_db']
    assert result['fallback_reason']


def test_no_radar_never_produces_dry_pixels():
    stack = np.full((7, 16, 16), np.nan)
    mask, valid, raw, flags, report = analyze(stack, np.ones((16, 16), bool), DEFAULTS)
    assert not valid.any()
    assert np.all(mask == 255) and np.all(raw == 255)
    assert report['potential_flood_area_ha'] == 0


def test_strict_and_partial_agree_with_full_reference():
    stack = stack_for((10, 10)); stack[5, :2] = 3
    masks = [classify(stack, np.ones((10, 10), bool), {**DEFAULTS, 'missing_water_policy': p})[0] for p in ('strict', 'partial')]
    assert np.array_equal(*masks)


@pytest.mark.parametrize('options', [
    {'lee_window': 4}, {'lee_enl': 0}, {'min_patch_area_m2': -1},
    {'threshold_method': 'anything'}, {'speckle_filter': 'anything'},
    {'otsu_min_separability': 1.1}, {'otsu_min_class_fraction': 0},
    {'adaptive_min_db': -10, 'adaptive_max_db': -25}, {'tile_size': 16, 'min_tile_pixels': 1000},
])
def test_invalid_analysis_settings(options):
    event = {'event_id': 'test', 'aoi': {'type':'Polygon', 'coordinates':[[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
             'baseline_start':'2024-01-01', 'event_start':'2024-02-01', 'search_end':'2024-03-01',
             'grid':{}, 'sentinel1':options}
    with pytest.raises(ValueError): validate(event)
