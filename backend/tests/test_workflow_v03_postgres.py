"""Mandatory V0.3 reliability checks on actual PostgreSQL 16, isolated test DB."""
import os
import threading
import uuid
import pytest
from app.db.repository import connect,seed
from app.db.integrated import seed_effective_bom,read_integrated_run
from app.workflow.runtime import create,read,dispatch
from app.workflow.worker import claim,finish
from app.workflow.scheduler import handle_notification,durable_mrp_runner
from pathlib import Path

@pytest.fixture
def db():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required')
    if 'industrial_lab_test' not in url: pytest.fail('isolated test database required')
    with connect(url) as conn:
        conn.autocommit=True
        yield conn

def fresh(db):
    wid='WF-V03-'+uuid.uuid4().hex
    create(db,'SO-2026-001',wid)
    with db.cursor() as cur:
        cur.execute('SELECT message_id FROM platform.workflow_outbox WHERE instance_id=%s',(wid,))
        mid=cur.fetchone()[0]
    return wid,mid

@pytest.mark.integration
def test_v03_initial_notification_auto_progress(db):
    wid,mid=fresh(db)
    msg=next(x for x in claim(db,'v03-init',100) if x['message_id']==mid)
    assert handle_notification(db,msg,'2026-11-20')['state']=='VALIDATING'
    assert finish(db,mid,'v03-init')
    assert read(db,wid)['version']==1

@pytest.mark.integration
def test_v03_two_workers_never_claim_same_message(db):
    wid,mid=fresh(db)
    barrier=threading.Barrier(2)
    results=[]; errors=[]
    def task(n):
        try:
            with connect(os.environ['TEST_DATABASE_URL']) as c:
                c.autocommit=True
                barrier.wait(timeout=10)
                results.extend((n,x['message_id']) for x in claim(c,'v03-'+str(n),100))
        except Exception as exc: errors.append(exc)
    a=threading.Thread(target=task,args=(1,)); b=threading.Thread(target=task,args=(2,))
    a.start(); b.start(); a.join(15); b.join(15)
    assert not errors,errors
    assert len([r for r in results if r[1]==mid])==1
    assert len([m for _,m in results])==len(set(m for _,m in results))

@pytest.mark.integration
def test_v03_expired_lease_reclaim_and_fencing(db):
    wid,mid=fresh(db)
    first=next(x for x in claim(db,'v03-old',100) if x['message_id']==mid)
    with db.transaction():
        with db.cursor() as cur:
            cur.execute("UPDATE platform.workflow_outbox SET lease_until=now()-interval '1 second' WHERE message_id=%s",(mid,))
    second=next(x for x in claim(db,'v03-new',100) if x['message_id']==mid)
    assert second['attempts']==first['attempts']+1
    assert finish(db,mid,'v03-old') is False
    assert finish(db,mid,'v03-new') is True

@pytest.mark.integration
def test_v03_retry_backoff_and_dead_not_reclaimed(db):
    wid,mid=fresh(db)
    claim(db,'v03-retry',100)
    assert finish(db,mid,'v03-retry',error='transient',max_attempts=2,retry_base_seconds=60)
    with db.cursor() as cur:
        cur.execute('SELECT status,next_attempt_at>now() FROM platform.workflow_outbox WHERE message_id=%s',(mid,))
        assert cur.fetchone()==('PENDING',True)
    assert mid not in [m['message_id'] for m in claim(db,'v03-too-early',100)]
    with db.transaction():
        with db.cursor() as cur:
            cur.execute("UPDATE platform.workflow_outbox SET next_attempt_at=now()-interval '1 second' WHERE message_id=%s",(mid,))
    assert mid in [m['message_id'] for m in claim(db,'v03-retry2',100)]
    assert finish(db,mid,'v03-retry2',error='permanent',max_attempts=2)
    with db.cursor() as cur:
        cur.execute('SELECT status FROM platform.workflow_outbox WHERE message_id=%s',(mid,))
        assert cur.fetchone()[0]=='DEAD'
    assert mid not in [m['message_id'] for m in claim(db,'v03-after-dead',100)]

@pytest.mark.integration
def test_v03_m2_runner_replay_and_workflow_recovery(db):
    from app.workflow.scheduler import durable_mrp_runner
    base=Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json'
    seed(db,base)
    seed_effective_bom(db)
    wid,_=fresh(db)
    dispatch(db,wid,'V03-START-'+wid,'START',{})
    dispatch(db,wid,'V03-VALID-'+wid,'VALIDATION_PASSED',{})
    rid=durable_mrp_runner(db,wid,'SO-2026-001','2026-11-20')
    assert rid==durable_mrp_runner(db,wid,'SO-2026-001','2026-11-20')
    assert read_integrated_run(db,rid)['status']=='COMPLETED'
    dispatch(db,wid,'V03-MRP-'+wid,'MRP_COMPLETED',{'mrp_run_id':rid})
    assert read(db,wid)['state']=='GENERATING_ADVICE'
    # A crashed worker replays old notifications, but version fence blocks re-advancing.
    old={'topic':'workflow.state_changed','workflow_id':wid,'payload':{'version':0}}
    assert handle_notification(db,old,'2026-11-20')['stale']
