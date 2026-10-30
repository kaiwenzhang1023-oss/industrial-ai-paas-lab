"""Mandatory live PostgreSQL gates. Skips are NOT a pass or sign-off."""
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture
def dburl():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('LIVE_POSTGRES_NOT_CONFIGURED')
    if 'industrial_lab_test' not in url: pytest.fail('Use isolated industrial_lab_test')
    return url

def prepared(url):
    from app.db.repository import connect,seed
    from app.db.integrated import seed_effective_bom
    with connect(url) as c:
        seed(c,ROOT/'datasets/seed/multi_order.json')
        seed_effective_bom(c)

@pytest.mark.integration
def test_normalized_pegging_readback_and_conservation(dburl):
    from app.db.repository import connect
    from app.db.integrated import run_integrated,read_integrated_run
    prepared(dburl)
    with connect(dburl) as conn:
        created=run_integrated(conn,'2026-11-20')
        read=read_integrated_run(conn,created['run_id'])
        report=read['result']['pegging']
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM platform.mrp_supply_sources WHERE run_id=%s',(created['run_id'],))
            assert cur.fetchone()[0]==len(report['supply_ledger'])
            cur.execute('SELECT count(*) FROM platform.mrp_demand_allocations WHERE run_id=%s',(created['run_id'],))
            assert cur.fetchone()[0]==len(report['order_allocations'])
            cur.execute('SELECT count(*) FROM platform.mrp_plan_child_edges WHERE run_id=%s',(created['run_id'],))
            assert cur.fetchone()[0]==len(report['plan_child_edges'])
            cur.execute('''SELECT count(*) FROM platform.mrp_supply_sources
              WHERE run_id=%s AND capacity_qty<>allocated_qty+remaining_qty''',(created['run_id'],))
            assert cur.fetchone()[0]==0
            cur.execute('''SELECT count(*) FROM platform.mrp_supply_sources
              WHERE run_id=%s AND supply_kind='RECEIPT' AND source_document_id LIKE 'RECEIPT:%%' ''',(created['run_id'],))
            assert cur.fetchone()[0]==0

@pytest.mark.integration
def test_atomic_rollback_on_relational_write_failure(dburl):
    from app.db.repository import connect
    from app.db.integrated import run_integrated
    prepared(dburl)
    with connect(dburl) as conn:
        # Reject all inserted normalized rows; JSONB and run must roll back too.
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('''CREATE OR REPLACE FUNCTION pg_temp.fail_pegging() RETURNS trigger
                  LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'INJECTED_PEGGING_FAILURE'; END $$''')
                cur.execute('''CREATE TRIGGER fail_pegging BEFORE INSERT ON platform.mrp_supply_sources
                  FOR EACH ROW EXECUTE FUNCTION pg_temp.fail_pegging()''')
        run_id='ROLLBACK-CONTRACT-V02'
        with pytest.raises(Exception,match='INJECTED_PEGGING_FAILURE'):
            run_integrated(conn,'2026-11-20',run_id=run_id)
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM platform.requirement_runs WHERE run_id=%s',(run_id,))
            assert cur.fetchone()[0]==0
            cur.execute('SELECT count(*) FROM platform.integrated_mrp_payloads WHERE run_id=%s',(run_id,))
            assert cur.fetchone()[0]==0
        with conn.transaction():
            with conn.cursor() as cur: cur.execute('DROP TRIGGER fail_pegging ON platform.mrp_supply_sources')

@pytest.mark.integration
def test_concurrent_source_writer_blocked_by_share_lock(dburl):
    from app.db.repository import connect
    prepared(dburl)
    # Conn A holds SHARE on source; conn B UPDATE needs ROW EXCLUSIVE and must time out.
    with connect(dburl) as a, connect(dburl) as b:
        with a.transaction():
            with a.cursor() as ca:
                ca.execute('LOCK TABLE mock_erp.sales_orders IN SHARE MODE')
            with pytest.raises(Exception) as exc:
                with b.transaction():
                    with b.cursor() as cb:
                        cb.execute("SET LOCAL lock_timeout='150ms'")
                        cb.execute("UPDATE mock_erp.sales_orders SET priority=priority WHERE order_id='SO-2026-001'")
            assert getattr(exc.value,'sqlstate',None)=='55P03'

@pytest.mark.integration
def test_receipt_origin_stable_across_repeat_runs(dburl):
    from app.db.repository import connect
    from app.db.integrated import run_integrated
    prepared(dburl)
    with connect(dburl) as conn:
        a=run_integrated(conn,'2026-11-20')['run_id']
        b=run_integrated(conn,'2026-11-20')['run_id']
        with conn.cursor() as cur:
            cur.execute('''SELECT run_id,source_system,source_document_id,source_line_id,material_id
             FROM platform.mrp_supply_sources WHERE run_id IN (%s,%s) AND supply_kind='RECEIPT'
             ORDER BY run_id,source_document_id''',(a,b))
            rows=cur.fetchall()
        left=sorted(tuple(r[1:]) for r in rows if r[0]==a)
        right=sorted(tuple(r[1:]) for r in rows if r[0]==b)
        assert left and left==right
