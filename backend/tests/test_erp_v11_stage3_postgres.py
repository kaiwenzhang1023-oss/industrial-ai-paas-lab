"""W2 Stage 3 isolated Neon branch acceptance. Never runs on production.

Requires explicit TEST_DATABASE_URL and V11_ISOLATED_BRANCH_ACK=YES.
No seed, no migration, no source data edits: inserts only new MRP run artifacts.
"""
import os
import uuid
import pytest
from app.db.repository import connect
from app.db.integrated import run_integrated, read_integrated_run, canonical_hash
from app.erp.models import OrderScope
from app.erp.adapter import OrderNotFound, OrderNotConfirmed

pytestmark = pytest.mark.integration

def _guarded_connection():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL missing: isolated Neon branch not tested')
    if os.getenv('V11_ISOLATED_BRANCH_ACK') != 'YES':
        pytest.skip('V11_ISOLATED_BRANCH_ACK=YES required')
    from psycopg.conninfo import conninfo_to_dict
    info=conninfo_to_dict(url)
    if os.getenv('DATABASE_URL') and conninfo_to_dict(os.getenv('DATABASE_URL')) == info:
        pytest.fail('TEST_DATABASE_URL matches DATABASE_URL: refusing to run')
    # A branch may retain the production database name. Verify branch endpoint
    # manually in Neon Console before setting the ACK; DB name is insufficient.
    conn=connect(url)
    with conn.cursor() as cur:
        cur.execute('SELECT current_database(), current_user, inet_server_addr()')
        print('Test connection identity:',cur.fetchone())
    conn.rollback()
    return conn

@pytest.fixture
def db():
    conn=_guarded_connection()
    try:yield conn
    finally:conn.close()

def _confirmed_ids(db):
    with db.cursor() as cur:
        cur.execute("SELECT order_id FROM mock_erp.sales_orders WHERE status='CONFIRMED' ORDER BY order_id LIMIT 2")
        ids=[r[0] for r in cur.fetchall()]
    db.rollback()
    if not ids:pytest.skip('No confirmed sales orders on test branch')
    return ids

def _run(db,scope=None,run_id=None):
    return run_integrated(db,as_of=os.getenv('V11_TEST_AS_OF','2026-11-20'),run_id=run_id,order_scope=scope)

def test_selected_order_persisted_scope_and_pegging(db):
    order_id=_confirmed_ids(db)[0]
    run=_run(db,OrderScope(mode='selected_orders',order_ids=[order_id]))
    loaded=read_integrated_run(db,run['run_id'])
    assert loaded['input_hash']==run['input_hash']
    assert loaded['result_hash']==run['result_hash']
    assert loaded['source_versions']['v11_order_scope']=={'mode':'selected_orders','order_ids':[order_id]}
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM platform.mrp_demand_allocations WHERE run_id=%s AND root_order_id IS NOT NULL AND root_order_id<>%s',(run['run_id'],order_id))
        assert cur.fetchone()[0]==0
        cur.execute('SELECT COUNT(*) FROM platform.integrated_mrp_payloads WHERE run_id=%s',(run['run_id'],))
        assert cur.fetchone()[0]==1
    db.rollback()

def test_selected_scope_repeatable_and_global_legacy_compatible(db):
    ids=_confirmed_ids(db)
    scope=OrderScope(mode='selected_orders',order_ids=[ids[0]])
    a=_run(db,scope); b=_run(db,scope)
    assert a['input_hash']==b['input_hash']
    assert a['result_hash']==b['result_hash']
    global_run=_run(db)
    loaded=read_integrated_run(db,global_run['run_id'])
    assert 'v11_order_scope' not in loaded['source_versions']
    assert global_run['orders']>=a['orders']

def test_missing_order_rolls_back_all_run_artifacts(db):
    rid='V11-ROLLBACK-'+uuid.uuid4().hex[:20]
    with pytest.raises(OrderNotFound):
        _run(db,OrderScope(mode='selected_orders',order_ids=['NONEXISTENT-'+uuid.uuid4().hex]),rid)
    with db.cursor() as cur:
        for table in ('platform.requirement_runs','platform.integrated_mrp_payloads','platform.mrp_supply_sources','platform.mrp_demand_allocations','platform.mrp_plan_child_edges'):
            cur.execute(f'SELECT COUNT(*) FROM {table} WHERE run_id=%s',(rid,))
            assert cur.fetchone()[0]==0,table
    db.rollback()

def test_duplicate_run_id_is_atomic(db):
    order_id=_confirmed_ids(db)[0]
    rid='V11-ATOMIC-'+uuid.uuid4().hex[:20]
    a=_run(db,OrderScope(mode='selected_orders',order_ids=[order_id]),rid)
    with pytest.raises(Exception):
        _run(db,OrderScope(mode='selected_orders',order_ids=[order_id]),rid)
    b=read_integrated_run(db,rid)
    assert b['input_hash']==a['input_hash']
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM platform.requirement_runs WHERE run_id=%s',(rid,))
        assert cur.fetchone()[0]==1
    db.rollback()
