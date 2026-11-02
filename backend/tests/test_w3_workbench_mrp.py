"""W3-02A contract and fail-closed checks; no PostgreSQL required."""
from fastapi.testclient import TestClient
from app.main import app
from app import workbench

client=TestClient(app)
URL='/api/v1/workbench/mrp/runs'
BODY={'as_of':'2026-11-20','order_scope':{'mode':'selected_orders','order_ids':['SO-2026-001']}}

def test_w3_requires_explicit_write_enable(monkeypatch):
    monkeypatch.delenv('DEMO_WRITE_ENABLED',raising=False)
    monkeypatch.setenv('DEMO_OPERATOR_KEY','secret')
    r=client.post(URL,json=BODY,headers={'X-Operator-Key':'secret'})
    assert r.status_code==403 and r.json()['detail']['code']=='MRP_WRITE_DISABLED'

def test_w3_requires_configured_operator_key(monkeypatch):
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.delenv('DEMO_OPERATOR_KEY',raising=False)
    r=client.post(URL,json=BODY)
    assert r.status_code==403 and r.json()['detail']['code']=='OPERATOR_KEY_REQUIRED'

def test_w3_wrong_key_is_forbidden(monkeypatch):
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','secret')
    r=client.post(URL,json=BODY,headers={'X-Operator-Key':'wrong'})
    assert r.status_code==403

def test_w3_public_readonly_cannot_be_overridden(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_ONLY','1')
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','secret')
    r=client.post(URL,json=BODY,headers={'X-Operator-Key':'secret'})
    assert r.status_code==403

def test_w3_reuses_integrated_engine_without_database(monkeypatch):
    monkeypatch.delenv('PUBLIC_READ_ONLY',raising=False)
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','secret')
    class FakeConn:
        def __enter__(self):return self
        def __exit__(self,*args):pass
    seen={}
    monkeypatch.setattr(workbench,'connect',lambda:FakeConn())
    def fake_run(conn,as_of,order_scope):
        seen.update(as_of=as_of,scope=order_scope.model_dump())
        return {'run_id':'W3-TEST','input_hash':'abc','result_hash':'def'}
    monkeypatch.setattr(workbench,'run_integrated',fake_run)
    r=client.post(URL,json=BODY,headers={'X-Operator-Key':'secret'})
    assert r.status_code==201,r.text
    assert seen=={'as_of':'2026-11-20','scope':BODY['order_scope']}

def test_w3_invalid_scope_is_rejected(monkeypatch):
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.setenv('DEMO_OPERATOR_KEY','secret')
    bad={'as_of':'2026-11-20','order_scope':{'mode':'selected_orders','order_ids':[]}}
    r=client.post(URL,json=bad,headers={'X-Operator-Key':'secret'})
    assert r.status_code==422
