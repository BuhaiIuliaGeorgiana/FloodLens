"""Formularul apeleaza functia o singura data la trimitere."""
from pathlib import Path
import numpy as np
import pytest
import ee
from sentinel1 import earth_engine as backend
from sentinel1.core import utc


def test_demo_calls_function_and_preserves_results(tmp_path, monkeypatch):
    pytest.importorskip('streamlit')
    from streamlit.testing.v1 import AppTest
    calls = []
    def discover(*args):
        calls.append(1)
        return [{'asset_id': f'COPERNICUS/S1_GRD/test{i}', 'acquired_at': utc(date),
                 'mode': 'IW', 'relative_orbit': 109, 'absolute_orbit': i,
                 'direction': 'DESCENDING', 'polarizations': ['VV','VH'],
                 'platform':'A', 'datatake': i, 'slice':1}
                for i,date in enumerate(['2024-08-21','2024-09-02','2024-09-14'],1)]
    def download(image, grid):
        stack=np.zeros((7,grid['height'],grid['width']), dtype='float32')
        stack[0]=-10;stack[1]=-20;stack[2]=3;stack[3:5]=35;stack[5]=1
        return stack
    monkeypatch.setattr(ee, 'Initialize', lambda **kwargs: None)
    monkeypatch.setattr(backend, 'discover', discover)
    monkeypatch.setattr(backend, 'build_stack', lambda *args: None)
    monkeypatch.setattr(backend, 'download_stack', download)
    monkeypatch.setattr(backend, 'download_landcover', lambda source, grid: np.full(grid['inside'].shape, 60.0))
    path=Path(__file__).parents[1]/'demo_app.py'
    app=AppTest.from_file(str(path)).run()
    assert not app.exception
    for element in app.text_input:
        if element.label=='Output folder': element.set_value(str(tmp_path))
    next(x for x in app.text_area if x.label.startswith('AOI')).set_value('''{"type":"Polygon","coordinates":[[[27.8,45.6],[27.801,45.6],[27.801,45.601],[27.8,45.601],[27.8,45.6]]]}''')
    next(x for x in app.selectbox if x.label=='Threshold method').set_value('tile_otsu')
    app.button[0].click().run(timeout=30)
    assert not app.exception
    result=app.session_state['s1_demo_result']
    assert result['pipeline_version']=='0.3.0'
    assert len(result['observations'][0]['layers'])==18
    assert result['observations'][0]['quality']['threshold']['fallback_reason']
    assert len(calls)==1
    app.run()
    assert len(calls)==1
    app.text_area[0].set_value('invalid json')
    app.button[0].click().run()
    assert not app.exception
    assert 's1_demo_result' not in app.session_state
    assert len(calls)==1
