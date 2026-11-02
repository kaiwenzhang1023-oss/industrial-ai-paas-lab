from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import workbench

ROOT=Path(__file__).resolve().parents[1]

def test_wms_navigation_and_readonly_view():
    html=(ROOT/'app/web/index.html').read_text(encoding='utf-8')
    js=(ROOT/'app/web/app.js').read_text(encoding='utf-8')
    assert 'data-tab="wms"' in html
    for marker in ('loadWms','bindWms','inventory-balances','warehouse_id','lot_id','snapshot_at','available'):
        assert marker in js

def test_mrp_wms_evidence_display_contract():
    js=(ROOT/'app/web/app.js').read_text(encoding='utf-8')
    assert 'wms_stock_attribution' in js
    assert 'wms_attribution_contract' in js
    assert '不是 WMS 实际预留' in js
    assert '历史运行保持原样' in js

def test_detail_source_exposes_persisted_evidence_not_recomputed():
    import inspect
    src=inspect.getsource(workbench.mrp_details)
    assert "(persisted or {}).get('wms_stock_attribution',[])" in src
    assert 'allocate_stock_evidence' not in src

def test_wms_routes_get_only():
    paths=app.openapi()['paths']
    assert set(paths['/api/v1/wms/inventory-balances'])=={'get'}
    assert set(paths['/api/v1/wms/inventory-summary'])=={'get'}
