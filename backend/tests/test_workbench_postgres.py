import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.repository import connect,seed
from app.db.integrated import seed_effective_bom

pytestmark=pytest.mark.integration

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('DEMO_WRITE_ENABLED','1')
    monkeypatch.delenv('DEMO_OPERATOR_KEY',raising=False)
    dsn=os.getenv('TEST_DATABASE_URL')
    if not dsn: pytest.skip('TEST_DATABASE_URL required')
    import app.workbench as wb
    monkeypatch.setattr(wb,'connect',lambda:connect(dsn))
    with connect(dsn) as conn:
        conn.autocommit=True
        seed(conn,Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json')
        seed_effective_bom(conn)
    return TestClient(app)

def test_workbench_postgres_snapshot_and_safe_workflow(client):
    response=client.get('/api/v1/workbench/snapshot')
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload['source']=='postgresql' and payload['simulation'] is True
    assert any(o['order_id']=='SO-2026-001' for o in payload['orders'])
    created=client.post('/api/v1/workbench/workflows',json={'order_id':'SO-2026-001'})
    assert created.status_code==201,created.text
    wid=created.json()['workflow_id']
    start=client.post(f'/api/v1/workbench/workflows/{wid}/advance',json={'expected_version':0})
    assert start.status_code==200,start.text
    assert start.json()['state']=='VALIDATING'
    stale=client.post(f'/api/v1/workbench/workflows/{wid}/advance',json={'expected_version':0})
    assert stale.status_code==409
    history=client.get(f'/api/v1/workbench/workflows/{wid}/history')
    assert history.status_code==200
    assert len(history.json()['outbox'])==2  # CREATED and START; not a duplicate

def test_v02_persisted_mrp_details_and_outbox_summary(client):
    created=client.post('/api/v1/workbench/workflows',json={'order_id':'SO-2026-001'})
    assert created.status_code==201,created.text
    wid=created.json()['workflow_id']
    for version in range(3):
        step=client.post(f'/api/v1/workbench/workflows/{wid}/advance',json={'expected_version':version})
        assert step.status_code==200,step.text
    state=step.json()
    assert state['state']=='GENERATING_ADVICE'
    run_id=state['mrp_run_id']
    details=client.get(f'/api/v1/workbench/mrp/{run_id}/details')
    assert details.status_code==200,details.text
    body=details.json()
    assert body['scope']=='ALL_CONFIRMED_ORDERS' and body['read_only'] is True
    assert body['run']['status']=='COMPLETED'
    assert len(body['lines'])>0 and len(body['allocations'])>0
    assert len(body['supplies'])>0
    assert client.get('/api/v1/workbench/mrp/does-not-exist/details').status_code==404
    outbox=client.get('/api/v1/workbench/outbox/summary')
    assert outbox.status_code==200,outbox.text
    assert outbox.json()['delivery_mode']=='EXPLICIT_WORKER_ONLY'
    assert any(m['workflow_id']==wid for m in outbox.json()['messages'])

def test_v1_normalized_provenance_and_receipt_sink(client):
    """Use actual MRP persistence, and ensure receipt delivery never advances workflow."""
    from app.workflow.receipt_dispatcher import dispatch_receipts
    import app.workbench as wb
    from app.workflow.runtime import read
    created=client.post('/api/v1/workbench/workflows',json={'order_id':'SO-2026-001'})
    assert created.status_code==201,created.text
    wid=created.json()['workflow_id']
    for version in range(3):
        step=client.post(f'/api/v1/workbench/workflows/{wid}/advance',json={'expected_version':version})
        assert step.status_code==200,step.text
    run_id=step.json()['mrp_run_id']
    details=client.get(f'/api/v1/workbench/mrp/{run_id}/details')
    assert details.status_code==200,details.text
    body=details.json()
    assert body['provenance_source']=='platform.mrp_demand_allocations'
    assert body['provenance'] and body['allocations']
    assert all(float(row['allocated_qty'])>0 for row in body['provenance'])
    dsn=os.environ['TEST_DATABASE_URL']
    with connect(dsn) as conn:
        conn.autocommit=True
        before=read(conn,wid)
        outcomes=dispatch_receipts(conn,100,owner='v1-test')
        assert outcomes and all(result=='DELIVERED' for _,result in outcomes)
        assert read(conn,wid)==before
        with conn.cursor() as cur:
            cur.execute('''SELECT count(*) FROM platform.workflow_outbox
                WHERE instance_id=%s AND status='DELIVERED' ''',(wid,))
            delivered=cur.fetchone()[0]
            assert delivered==4
            cur.execute('''SELECT count(*) FROM platform.outbox_delivery_receipts r
                JOIN platform.workflow_outbox o USING(message_id)
                WHERE o.instance_id=%s''',(wid,))
            assert cur.fetchone()[0]==4
        assert dispatch_receipts(conn,100,owner='v1-test-repeat')==[]
