from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

def test_v02_routes_registered():
    paths=app.openapi()['paths']
    assert '/api/v1/workbench/mrp/{run_id}/details' in paths
    assert '/api/v1/workbench/outbox/summary' in paths

def test_v02_frontend_is_business_readable():
    js=(Path(__file__).resolve().parents[1]/'app/web/app.js').read_text(encoding='utf-8')
    assert '毛需求' in js and '净需求' in js
    assert '需求归因' in js and 'BOM 展开' in js
    assert 'PENDING 不等于已投递' in js
    assert 'WAITING_REVIEW 不提供自动审批' in js

def test_v02_setup_sql_never_null():
    ps=(Path(__file__).resolve().parents[2]/'setup_workbench_demo.ps1').read_text(encoding='utf-8')
    assert 'SELECT CASE WHEN EXISTS' in ps
    assert ').Trim()' not in ps
