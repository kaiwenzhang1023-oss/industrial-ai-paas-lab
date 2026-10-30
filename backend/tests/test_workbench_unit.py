"""M4 UI contract smoke checks; no DB required."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.workbench import NewWorkflow, Advance

def test_workbench_served():
    client=TestClient(app)
    r=client.get('/workbench/')
    assert r.status_code==200
    assert '工业智能运营平台' in r.text
    assert '/workbench/app.js' in r.text
    assert client.get('/workbench/app.js').status_code==200
    assert client.get('/workbench/style.css').status_code==200

def test_workbench_contract():
    paths=app.openapi()['paths']
    assert '/api/v1/workbench/snapshot' in paths
    assert '/api/v1/workbench/workflows/{workflow_id}/advance' in paths
    assert Advance(expected_version=0).as_of.isoformat()=='2026-11-20'
    assert NewWorkflow(order_id='SO-2026-001').order_id=='SO-2026-001'

def test_frontend_explicit_simulation_disclaimer():
    html=(Path(__file__).resolve().parents[1]/'app/web/index.html').read_text(encoding='utf-8')
    js=(Path(__file__).resolve().parents[1]/'app/web/app.js').read_text(encoding='utf-8')
    assert '非生产环境' in html
    assert 'WAITING_REVIEW 不提供自动审批' in js
    assert 'offline-contract-v1' in js
