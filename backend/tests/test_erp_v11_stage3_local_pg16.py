"""W2 Stage 3 isolated disposable local PG16 acceptance. Never runs on production.

Requires E06 verified local disposable PG16 and V11_LOCAL_PG16_ACK=YES.
Only in a verified disposable PG16 database: initialize effective BOM from legacy BOM when empty, then test MRP artifacts.
"""
import os
import uuid
import pytest
from app.db.repository import connect
from app.db.integrated import run_integrated, read_integrated_run, canonical_hash, seed_effective_bom
from app.erp.models import OrderScope
from app.erp.adapter import OrderNotFound, OrderNotConfirmed

pytestmark = pytest.mark.integration

def _guarded_connection():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL missing: isolated Neon branch not tested')
    if os.getenv('V11_LOCAL_PG16_ACK') != 'YES':
        pytest.skip('V11_LOCAL_PG16_ACK=YES required')
    from psycopg.conninfo import conninfo_to_dict
    info=conninfo_to_dict(url)
    if os.getenv('DATABASE_URL') and conninfo_to_dict(os.getenv('DATABASE_URL')) == info:
        pytest.fail('TEST_DATABASE_URL matches DATABASE_URL: refusing to run')
    # E06 collection guard validates local PG16 and the random container marker.
    # This module must only be run in the RC6 disposable container.
    conn=connect(url)
    with conn.cursor() as cur:
        cur.execute('SELECT current_database(), current_user, inet_server_addr()')
        print('Test connection identity:',cur.fetchone())
    conn.rollback()
    return conn

@pytest.fixture(scope='session')
def _v11_bom_preflight():
    # Runs after the E06 collection gate; no remote or production target is permitted.
    conn = _guarded_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM mock_erp.effective_bom_headers')
            effective_count = cur.fetchone()[0]
            cur.execute('SELECT COUNT(DISTINCT parent_id) FROM mock_erp.bom_items')
            legacy_count = cur.fetchone()[0]
        conn.rollback()
        if effective_count == 0:
            if legacy_count == 0:
                pytest.fail('V11_BOM_PREFLIGHT: no effective or legacy BOM; refusing empty-input acceptance')
            inserted = seed_effective_bom(conn)
            conn.commit()
            if inserted != legacy_count:
                pytest.fail('V11_BOM_PREFLIGHT: unexpected initialized BOM count')
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM mock_erp.effective_bom_headers')
            final_count = cur.fetchone()[0]
        conn.rollback()
        if final_count == 0:
            pytest.fail('V11_BOM_PREFLIGHT: effective BOM remains empty')
        print('V11 effective BOM preflight:', final_count)
    finally:
        conn.close()

@pytest.fixture
def db(_v11_bom_preflight):
    conn = _guarded_connection()
    try:
        yield conn
    finally:
        conn.close()

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
