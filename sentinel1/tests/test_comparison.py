"""Buffer, polarizari si context de teren, fara acces la satelit."""
import copy
import json
from pathlib import Path
import numpy as np
import pytest
import rasterio
from sentinel1.core import DEFAULTS, validate, make_grid, context_grid, options_for_band, utc
from sentinel1.comparison import load_context, analyze_band, compare_masks, LIMITATION_CLASSES
from sentinel1.pipeline import process_sentinel1
from sentinel1 import earth_engine as backend


@pytest.fixture
def event():
    return {'event_id':'buffer-test', 'aoi':{'type':'Polygon', 'coordinates':[
        [[27.8,45.6],[27.802,45.6],[27.802,45.602],[27.8,45.602],[27.8,45.6]]]},
        'baseline_start':'2024-08-01', 'event_start':'2024-09-14', 'search_end':'2024-09-19',
        'grid':{'crs':'EPSG:32635','resolution':10,'origin':[3,7]},
        'sentinel1':{'threshold_method':'tile_otsu','threshold_buffer_m':400,
                     'tile_size':32,'min_tile_pixels':64,'min_threshold_tiles':2}}


def records():
    return [{'asset_id':f'COPERNICUS/S1_GRD/test{i}', 'acquired_at':utc(date),
             'mode':'IW','relative_orbit':109,'absolute_orbit':i,'datatake':i,
             'direction':'DESCENDING','polarizations':['VV','VH'],'platform':'A','slice':1}
            for i,date in enumerate(['2024-08-21','2024-09-02','2024-09-14'],1)]


def fake_access(monkeypatch):
    calls=[]
    monkeypatch.setattr(backend,'discover',lambda *args:records())
    def build(event, obs, baseline, grid, settings):
        calls.append((settings['band'], [r['asset_id'] for r in obs['records']],
                      [r['asset_id'] for b in baseline for r in b['records']]))
        return settings['band']
    def download(band, grid):
        stack=np.zeros((7,grid['height'],grid['width']),dtype='float32')
        stack[0]=-10 if band=='VV' else -17
        col=np.indices(grid['inside'].shape)[1]
        stack[1]=np.where(col%32<16, -23 if band=='VV' else -29, -12 if band=='VV' else -19)
        stack[2]=3;stack[3:5]=35;stack[5]=1
        return stack
    monkeypatch.setattr(backend,'build_stack',build)
    monkeypatch.setattr(backend,'download_stack',download)
    monkeypatch.setattr(backend,'download_landcover',lambda source,grid:np.full(grid['inside'].shape,60.0))
    return calls


def test_buffer_alignment_holes_and_pixel_limit(event):
    event['aoi']['coordinates'].append([[27.8005,45.6005],[27.8005,45.601],[27.801,45.601],[27.801,45.6005],[27.8005,45.6005]])
    _, options=validate(event)
    grid=make_grid(event,options['max_pixels'])
    work,crop=context_grid(event,grid,options)
    assert work['width']==grid['width']+80
    assert work['transform'].c+400==grid['transform'].c
    assert work['transform'].f-400==grid['transform'].f
    assert work['inside'][crop].shape==grid['inside'].shape
    assert np.all(work['inside'][crop][grid['inside']])
    with pytest.raises(ValueError,match='Buffered grid'):
        context_grid(event,grid,{**options,'max_pixels':grid['width']*grid['height']})
    no_buffer,crop=context_grid(event,grid,{**options,'threshold_method':'fixed'})
    assert no_buffer is grid


def test_buffer_samples_both_bands_and_exports_crop(event, tmp_path, monkeypatch):
    calls=fake_access(monkeypatch)
    result=process_sentinel1(event,str(tmp_path))
    assert result['status']=='partial'
    assert result['pipeline_version']=='0.3.0'
    obs=result['observations'][0]
    assert len(obs['layers'])==18
    assert calls[0][0]=='VV' and calls[1][0]=='VH'
    assert calls[0][1:]==calls[1][1:]
    grid=make_grid(event,DEFAULTS['max_pixels'])
    for band in ('VV','VH'):
        threshold=obs['band_results'][band]['quality']['threshold']
        assert threshold['used_method']=='tile_otsu'
        assert threshold['buffer_m']==400
        assert threshold['sample_pixel_count']>threshold['aoi_sample_pixel_count']
        assert threshold['sampling_grid']['width']>grid['width']
    assert obs['band_results']['VV']['quality']['threshold']['water_db'] != obs['band_results']['VH']['quality']['threshold']['water_db']
    for layer in obs['layers']:
        if layer['format']=='geotiff':
            with rasterio.open(layer['local_path']) as src:
                assert src.shape==grid['inside'].shape
                assert src.transform==grid['transform']
                if layer['layer_type']!='quality_flags':
                    assert np.all(src.read(1)[~grid['inside']]==255)
    assert obs['band_comparison']['common_valid_pixel_count']==int(grid['inside'].sum())
    assert json.loads(Path(obs['metadata_path']).read_text())['band_results']==obs['band_results']


def test_comparison_keeps_unknown_and_exposes_disagreement():
    vv={'mask':np.array([[0,1,0,1,1,255]],dtype='uint8'), 'valid':np.array([[1,1,1,1,1,0]],bool)}
    vh={'mask':np.array([[0,0,1,1,255,1]],dtype='uint8'), 'valid':np.array([[1,1,1,1,0,1]],bool)}
    classes,agreement,valid,report=compare_masks(vv,vh,np.array([[0,1,2,2,3,3]]))
    assert classes.tolist()==[[0,1,2,3,255,255]]
    assert agreement.tolist()==[[0,0,0,1,255,255]]
    assert report['common_valid_pixel_count']==4
    assert report['interband_iou_not_accuracy']==pytest.approx(1/3)


def test_empty_agreement_does_not_report_perfect_accuracy():
    bundle={'mask':np.zeros((2,2),dtype='uint8'),'valid':np.ones((2,2),bool)}
    assert compare_masks(bundle,bundle,np.zeros((2,2)))[3]['interband_iou_not_accuracy'] is None


def test_landcover_classes_and_missing_do_not_become_reliable(event, monkeypatch):
    dates,options=validate(event)
    grid=make_grid(event,options['max_pixels'])
    options={**options,'threshold_method':'fixed'}
    def classes(source,work):
        data=np.full(work['inside'].shape,60.0)
        for row,c in enumerate([50,10,20,30,40,90,95,100,0,np.nan]):
            data[row]=c
        return data
    monkeypatch.setattr(backend,'download_landcover',classes)
    ctx=load_context(event,dates,grid,options)
    inside=grid['inside']
    assert np.all(ctx['limitations'][0][inside[0]]==1)
    for row in range(1,8): assert np.all(ctx['limitations'][row][inside[row]]==2)
    for row in (8,9): assert np.all(ctx['limitations'][row][inside[row]]==3)
    assert ctx['landcover_info']['status']=='partial'
    assert np.all(ctx['limitations'][~inside]==255)


@pytest.mark.parametrize('date,asset,year',[('2024-01-01','ESA/WorldCover/v200',2021),('2021-05-01','ESA/WorldCover/v100',2020),('2020-05-01',None,None)])
def test_landcover_has_no_future_reference_year(date,asset,year):
    assert backend.landcover_source(date)=={'asset':asset,'reference_year':year}


def test_landcover_failure_preserves_radar_and_records_unknown(event,tmp_path,monkeypatch):
    fake_access(monkeypatch)
    def fail(*args): raise RuntimeError('auxiliary unavailable')
    monkeypatch.setattr(backend,'download_landcover',fail)
    result=process_sentinel1(event,str(tmp_path))
    obs=result['observations'][0]
    assert obs['quality']['valid_pixel_count']>0
    assert 'auxiliary unavailable' in obs['reason']
    assert obs['quality']['landcover']['status']=='unavailable'
    assert obs['quality']['landcover']['aoi_reference_coverage_pct']==0
    layer=next(l for l in obs['layers'] if l['layer_type']=='landcover_limitations' and l['format']=='geotiff')
    with rasterio.open(layer['local_path']) as src:
        assert set(np.unique(src.read(1))) <= {3,255}


def test_secondary_failure_keeps_primary(event,tmp_path,monkeypatch):
    fake_access(monkeypatch)
    original=backend.download_stack
    def download(band,grid):
        if band=='VH': raise RuntimeError('VH download failed')
        return original(band,grid)
    monkeypatch.setattr(backend,'download_stack',download)
    result=process_sentinel1(event,str(tmp_path));obs=result['observations'][0]
    assert result['status']=='partial'
    assert obs['band_comparison']['status']=='failed'
    assert len(obs['layers'])==8
    assert obs['band_results']['VV']['valid_pixel_count']>0
    assert 'VH download failed' in obs['reason']


def test_primary_without_coverage_keeps_secondary_result(event,tmp_path,monkeypatch):
    fake_access(monkeypatch)
    original=backend.download_stack
    def download(band,grid):
        stack=original(band,grid)
        if band=='VV': stack[0]=np.nan
        return stack
    monkeypatch.setattr(backend,'download_stack',download)
    result=process_sentinel1(event,str(tmp_path));obs=result['observations'][0]
    assert result['status']=='partial'
    assert obs['band_results']['VV']['valid_pixel_count']==0
    assert obs['band_results']['VH']['valid_pixel_count']>0
    assert obs['band_comparison']['status']=='unavailable'


def test_per_band_settings_do_not_copy_primary_thresholds():
    options={**DEFAULTS,'water_db':-18,'drop_db':5,'band_thresholds':{'VH':{'water_db':-24,'drop_db':4}}}
    assert options_for_band(options,'VV')['water_db']==-18
    assert options_for_band(options,'VH')['water_db']==-24
    assert options_for_band(options,'VH')['drop_db']==4
    assert options_for_band(options,'VH')['adaptive_min_db']==-32


@pytest.mark.parametrize('setting',[{'threshold_buffer_m':-1},{'threshold_buffer_m':float('nan')},
 {'threshold_buffer_m':10001},{'compare_bands':1},{'use_landcover':'yes'},
 {'band_thresholds':{'HH':{}}},{'band_thresholds':{'VH':{'drop_db':0}}},
 {'band_thresholds':{'VH':{'adaptive_min_db':-10,'adaptive_max_db':-20}}}])
def test_reject_invalid_extension_settings(event,setting):
    event['sentinel1'].update(setting)
    with pytest.raises(ValueError): validate(event)


def test_known_urban_excluded_from_threshold_samples_not_forced_dry(event,tmp_path,monkeypatch):
    fake_access(monkeypatch)
    monkeypatch.setattr(backend,'download_landcover',lambda source,grid:np.full(grid['inside'].shape,50.0))
    result=process_sentinel1(event,str(tmp_path));obs=result['observations'][0]
    assert obs['quality']['threshold']['sample_pixel_count']==0
    assert obs['quality']['threshold']['used_method']=='fixed'
    assert obs['quality']['threshold']['fallback_reason']
    assert obs['quality']['valid_pixel_count']>0
    assert obs['quality']['potential_flood_pixel_count']>0
    layer=next(l for l in obs['layers'] if l['layer_type']=='quality_flags' and l['band']=='VV')
    from sentinel1.analysis import QUALITY_BITS
    grid=make_grid(event,DEFAULTS['max_pixels'])
    with rasterio.open(layer['local_path']) as src:
        assert np.all(src.read(1)[grid['inside']] & QUALITY_BITS['urban_limitation'])


def test_single_band_context_download_graph(event,monkeypatch):
    import ee
    from ee.apitestcase import GetAlgorithms
    ee.Reset()
    monkeypatch.setattr(ee.data,'_install_cloud_api_resource',lambda:None)
    monkeypatch.setattr(ee.data,'getAlgorithms',GetAlgorithms)
    ee.Initialize(None,'',project='offline-test')
    seen=[]
    def download(image,grid,band_count=7):
        seen.append((image.serialize(),band_count))
        return np.ones((band_count,grid['height'],grid['width']),dtype='float32')
    monkeypatch.setattr(backend,'download_stack',download)
    try:
        grid=make_grid(event,DEFAULTS['max_pixels'])
        array=backend.download_landcover(backend.landcover_source('2024-09-14'),grid)
        assert array.shape==grid['inside'].shape
        assert seen[0][1]==1
        assert 'ESA/WorldCover/v200' in seen[0][0]
        assert 'Image.reproject' in seen[0][0]
    finally:
        ee.Reset()


def test_downloader_one_band_and_nodata(monkeypatch):
    from affine import Affine
    from rasterio.io import MemoryFile
    grid={'width':2,'height':2,'crs':'EPSG:32635','transform':Affine(10,0,500000,0,-10,5000000)}
    class Image:
        def getDownloadURL(self,options): return 'https://example.test/tile'
    class Response:
        def raise_for_status(self): pass
        @property
        def content(self):
            with MemoryFile() as mem:
                with mem.open(driver='GTiff',width=2,height=2,count=1,dtype='float32',crs=grid['crs'],transform=grid['transform']) as dst:
                    dst.write(np.array([[[50,10],[60,-9999]]],dtype='float32'))
                return mem.read()
    monkeypatch.setattr(backend.requests.Session,'get',lambda *a,**k:Response())
    data=backend.download_stack(Image(),grid,band_count=1)
    assert data.shape==(1,2,2)
    assert data[0,0,0]==50 and np.isnan(data[0,1,1])


def test_primary_vh_defaults_and_explicit_overrides(event):
    event['sentinel1']['band']='VH'
    _,options=validate(event)
    assert options['water_db']==-23
    assert options['adaptive_min_db']==-32 and options['adaptive_max_db']==-15
    event['sentinel1'].update(water_db=-24,adaptive_min_db=-33)
    _,options=validate(event)
    assert options['water_db']==-24 and options['adaptive_min_db']==-33
