"""W3-04 freeze gate: offline safety, compatibility and routing contracts."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import workbench

client = TestClient(app)
URL = '/api/v1/workbench/mrp/runs'
KEY = {'X-Operator-Key': 'w3-test-key'}
SELECTED = {'as_of': '2026-11-20', 'order_scope': {'mode': 'selected_orders', 'order_ids': ['SO-2026-001']}}
GLOBAL = {'as_of': '2026-11-20', 'order_scope': {'mode': 'global', 'order_ids': []}}

class FakeConn:
    def __enter__(self): return self
    def __exit__(self, *args): return False

def test_freeze_readonly_denies_without_database_access(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY', '1')
    monkeypatch.setenv('DEMO_WRITE_ENABLED', '1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY', 'w3-test-key')
    monkeypatch.setattr(workbench, 'connect', lambda: (_ for _ in ()).throw(AssertionError('DB should not be reached')))
    assert client.post(URL, json=SELECTED, headers=KEY).status_code == 403

def test_freeze_global_scope_reuses_existing_engine(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY', '0')
    monkeypatch.setenv('DEMO_WRITE_ENABLED', '1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY', 'w3-test-key')
    monkeypatch.setattr(workbench, 'connect', lambda: FakeConn())
    called = {}
    def fake_engine(conn, as_of, order_scope):
        called.update(as_of=as_of, scope=order_scope.model_dump())
        return {'run_id': 'W3-GLOBAL', 'input_hash': 'a', 'result_hash': 'b'}
    monkeypatch.setattr(workbench, 'run_integrated', fake_engine)
    assert client.post(URL, json=GLOBAL, headers=KEY).status_code == 201
    assert called == {'as_of': '2026-11-20', 'scope': GLOBAL['order_scope']}

def test_freeze_selected_scope_forwards_order_ids(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY', '0')
    monkeypatch.setenv('DEMO_WRITE_ENABLED', '1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY', 'w3-test-key')
    monkeypatch.setattr(workbench, 'connect', lambda: FakeConn())
    called = {}
    def fake_engine(conn, as_of, order_scope):
        called.update(as_of=as_of, scope=order_scope.model_dump())
        return {'run_id': 'W3-SELECTED', 'input_hash': 'a', 'result_hash': 'b'}
    monkeypatch.setattr(workbench, 'run_integrated', fake_engine)
    assert client.post(URL, json=SELECTED, headers=KEY).status_code == 201
    assert called == {'as_of': '2026-11-20', 'scope': SELECTED['order_scope']}

def test_freeze_erp_endpoints_remain_read_only():
    paths = app.openapi()['paths']
    assert 'get' in paths['/api/v1/erp/sales-orders']
    assert 'get' in paths['/api/v1/erp/sales-orders/{order_id}']
    assert not any(method in ('post', 'put', 'patch', 'delete') for path, methods in paths.items()
                   if path.startswith('/api/v1/erp/') for method in methods)

def test_freeze_existing_workbench_routes_preserved():
    paths = app.openapi()['paths']
    for path in ('/api/v1/workbench/snapshot', '/api/v1/workbench/mrp/{run_id}/details',
                 '/api/v1/workbench/workflows/{workflow_id}/history'):
        assert 'get' in paths[path]
    assert 'post' in paths['/api/v1/workbench/mrp/runs']

def test_freeze_ui_has_local_status_and_attribution_transparency():
    js = (Path(__file__).resolve().parents[1] / 'app' / 'web' / 'app.js').read_text(encoding='utf-8')
    for marker in ('w3Submitting', 'MRP 计算中', 'w3Status', 'role="status"',
                   '未归属（原始为空）', 'Input Hash', 'Result Hash'):
        assert marker in js
