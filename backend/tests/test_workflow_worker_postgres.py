import os,uuid
import pytest
from app.db.repository import connect
from app.workflow.runtime import create,dispatch,read
from app.workflow.worker import claim,finish,pump_once,auto_advance

@pytest.fixture
def db():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required')
    if 'industrial_lab_test' not in url: pytest.fail('isolated test database required')
    with connect(url) as conn:
        conn.autocommit=True
        yield conn

def fresh(db):
    wid='WF-'+uuid.uuid4().hex
    create(db,'SO-2026-001',wid)
    dispatch(db,wid,'EV-'+uuid.uuid4().hex,'START',{})
    return wid

@pytest.mark.integration
def test_claim_and_delivery(db):
    wid=fresh(db)
    with db.cursor() as cur:
        cur.execute('SELECT message_id FROM platform.workflow_outbox WHERE instance_id=%s',(wid,))
        mid=cur.fetchone()[0]
    rows=claim(db,'owner-'+uuid.uuid4().hex,100)
    mine=next(r for r in rows if r['message_id']==mid)
    owner=db_owner(db,mid)
    assert mine['attempts']>=1
    assert finish(db,mid,'wrong-owner') is False
    assert finish(db,mid,owner) is True
    with db.cursor() as cur:
        cur.execute('SELECT status FROM platform.workflow_outbox WHERE message_id=%s',(mid,))
        assert cur.fetchone()[0]=='DELIVERED'

def db_owner(db,mid):
    with db.cursor() as cur:
        cur.execute('SELECT lease_owner FROM platform.workflow_outbox WHERE message_id=%s',(mid,))
        return cur.fetchone()[0]

@pytest.mark.integration
def test_claim_skip_locked_and_retry(db):
    wid=fresh(db)
    with db.cursor() as cur:
        cur.execute('SELECT message_id FROM platform.workflow_outbox WHERE instance_id=%s',(wid,))
        mid=cur.fetchone()[0]
    owner='worker-'+uuid.uuid4().hex
    claimed=claim(db,owner,100)
    assert any(x['message_id']==mid for x in claimed)
    assert not any(x['message_id']==mid for x in claim(db,'other-'+uuid.uuid4().hex,100))
    assert finish(db,mid,owner,error='temporary')
    with db.cursor() as cur:
        cur.execute('SELECT status,attempts,last_error FROM platform.workflow_outbox WHERE message_id=%s',(mid,))
        status,attempts,error=cur.fetchone()
    assert status=='PENDING' and attempts>=1 and error=='temporary'

@pytest.mark.integration
def test_dead_letter_after_max_attempts(db):
    wid=fresh(db)
    with db.cursor() as cur:
        cur.execute('SELECT message_id FROM platform.workflow_outbox WHERE instance_id=%s',(wid,))
        mid=cur.fetchone()[0]
    owner='worker-'+uuid.uuid4().hex
    claim(db,owner,100)
    assert finish(db,mid,owner,error='permanent',max_attempts=1)
    with db.cursor() as cur:
        cur.execute('SELECT status FROM platform.workflow_outbox WHERE message_id=%s',(mid,))
        assert cur.fetchone()[0]=='DEAD'

@pytest.mark.integration
def test_auto_progress_to_calculating(db):
    wid='WF-'+uuid.uuid4().hex
    create(db,'SO-2026-001',wid)
    assert auto_advance(db,wid)['state']=='VALIDATING'
    assert auto_advance(db,wid)['state']=='CALCULATING'
    assert auto_advance(db,wid)['reason']=='MRP_RUNNER_REQUIRED'
    assert read(db,wid)['version']==2
