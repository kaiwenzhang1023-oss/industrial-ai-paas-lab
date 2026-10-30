"""Real PG16 integration tests. Apply 008_workflow_runtime.sql first."""
import os
import uuid
import pytest
from app.db.repository import connect
from app.workflow.runtime import create,read,dispatch,WorkflowConflict,pending_outbox,acknowledge_outbox

@pytest.fixture
def db():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required')
    if 'industrial_lab_test' not in url: pytest.fail('isolated test database required')
    with connect(url) as conn:
        conn.autocommit=True
        yield conn

def unique(): return uuid.uuid4().hex

@pytest.mark.integration
def test_durable_restart_and_idempotency(db):
    wid='WF-'+unique(); eid='EV-'+unique()
    create(db,'SO-2026-001',wid)
    first=dispatch(db,wid,eid,'START',{},expected_version=0)
    assert first['state']=='VALIDATING'
    assert dispatch(db,wid,eid,'START',{})['duplicate'] is True
    assert read(db,wid)['version']==1
    with db.cursor() as cur:
        cur.execute('SELECT count(*) FROM platform.workflow_audit WHERE instance_id=%s',(wid,))
        assert cur.fetchone()[0]==1
        cur.execute('SELECT event_id,topic,payload FROM platform.workflow_outbox WHERE instance_id=%s ORDER BY message_id',(wid,))
        events=cur.fetchall()
        assert len(events)==2  # create notification + one START transition
        assert [r[0] for r in events]==['INIT:'+wid,eid]
        assert all(r[1]=='workflow.state_changed' for r in events)
        assert [r[2]['to_state'] for r in events]==['CREATED','VALIDATING']

@pytest.mark.integration
def test_invalid_transition_rolls_back(db):
    wid='WF-'+unique(); create(db,'SO-2026-001',wid)
    with pytest.raises(WorkflowConflict): dispatch(db,wid,'EV-'+unique(),'MRP_COMPLETED',{'mrp_run_id':'fake'})
    assert read(db,wid)['state']=='CREATED'

@pytest.mark.integration
def test_payload_conflict_and_stale_version(db):
    wid='WF-'+unique(); eid='EV-'+unique(); create(db,'SO-2026-001',wid)
    dispatch(db,wid,eid,'START',{})
    with pytest.raises(WorkflowConflict,match='EVENT_ID_PAYLOAD_CONFLICT'):
        dispatch(db,wid,eid,'START',{'changed':True})
    with pytest.raises(WorkflowConflict,match='STALE_WORKFLOW_VERSION'):
        dispatch(db,wid,'EV-'+unique(),'VALIDATION_PASSED',{},expected_version=0)
    assert read(db,wid)['version']==1

@pytest.mark.integration
def test_outbox_ack(db):
    wid='WF-'+unique(); create(db,'SO-2026-001',wid)
    dispatch(db,wid,'EV-'+unique(),'START',{})
    message=next(m for m in pending_outbox(db,10000) if m['workflow_id']==wid)
    assert acknowledge_outbox(db,message['message_id']) is True
    assert acknowledge_outbox(db,message['message_id']) is False

@pytest.mark.integration
def test_reject_fake_mrp_result(db):
    wid='WF-'+unique(); create(db,'SO-2026-001',wid)
    dispatch(db,wid,'EV-'+unique(),'START',{})
    dispatch(db,wid,'EV-'+unique(),'VALIDATION_PASSED',{})
    with pytest.raises(WorkflowConflict,match='MRP_RESULT_NOT_PERSISTED'):
        dispatch(db,wid,'EV-'+unique(),'MRP_COMPLETED',{'mrp_run_id':'NONEXISTENT-'+unique()})
    assert read(db,wid)['state']=='CALCULATING'

@pytest.mark.integration
def test_m2_workflow_schema_and_approval_fk_compatible(db):
    with db.cursor() as cur:
        cur.execute("""SELECT column_name FROM information_schema.columns
            WHERE table_schema='platform' AND table_name='workflow_instances'""")
        columns={row[0] for row in cur.fetchall()}
        assert {'instance_id','trace_id','mrp_run_id','error_code','created_at','updated_at'} <= columns
        assert 'workflow_id' not in columns
        cur.execute("""SELECT count(*) FROM pg_constraint
            WHERE conrelid='platform.approval_tasks'::regclass
              AND contype='f' AND confrelid='platform.workflow_instances'::regclass""")
        assert cur.fetchone()[0]>=1
    workflow=create(db,'SO-2026-001')
    assert workflow['version']==0
    with db.cursor() as cur:
        cur.execute('SELECT trace_id FROM platform.workflow_instances WHERE instance_id=%s',(workflow['workflow_id'],))
        assert cur.fetchone()[0].startswith('TRACE-')
