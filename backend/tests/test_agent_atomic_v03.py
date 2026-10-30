"""V0.3 PostgreSQL transaction contract: fact audit + draft + workflow commit together."""
import os
from pathlib import Path
import pytest

pytestmark = pytest.mark.integration


def test_agent_atomic_rollback_then_success(monkeypatch):
    from app.db.repository import connect, seed
    from app.db.integrated import seed_effective_bom
    from app.workflow.runtime import create, dispatch, read
    from app.workflow.scheduler import durable_mrp_runner
    from app.agent import generate_and_persist
    import app.workflow.runtime as runtime

    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.fail('TEST_DATABASE_URL is required for integration test')
    with connect(dsn) as db:
        db.autocommit = True
        seed(db, Path(__file__).resolve().parents[2] / 'datasets/seed/multi_order.json')
        seed_effective_bom(db)
        wid = create(db, 'SO-2026-001')['workflow_id']
        dispatch(db, wid, 'v03-start-'+wid, 'START', {})
        dispatch(db, wid, 'v03-validated-'+wid, 'VALIDATION_PASSED', {})
        run_id = durable_mrp_runner(db, wid, 'SO-2026-001', '2026-11-20')
        dispatch(db, wid, 'v03-mrp-'+wid, 'MRP_COMPLETED', {'mrp_run_id':run_id})
        before = read(db, wid)
        assert before['state'] == 'GENERATING_ADVICE'

        original = runtime.dispatch_in_transaction
        def simulate_failure(*args, **kwargs):
            raise RuntimeError('SIMULATED_DISPATCH_FAILURE')
        monkeypatch.setattr(runtime, 'dispatch_in_transaction', simulate_failure)
        with pytest.raises(RuntimeError, match='SIMULATED_DISPATCH_FAILURE'):
            generate_and_persist(db, wid)
        assert read(db, wid) == before
        with db.cursor() as cur:
            cur.execute('SELECT count(*) FROM platform.agent_drafts WHERE workflow_id=%s', (wid,))
            assert cur.fetchone()[0] == 0
            cur.execute('SELECT count(*) FROM platform.agent_tool_audit WHERE workflow_id=%s', (wid,))
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM platform.workflow_outbox WHERE instance_id=%s AND event_id LIKE 'AGENT:%%'", (wid,))
            assert cur.fetchone()[0] == 0
        monkeypatch.setattr(runtime, 'dispatch_in_transaction', original)
        result = generate_and_persist(db, wid)
        assert result['workflow']['state'] == 'WAITING_REVIEW'
        assert result['tool_calls'][0]['tool'] == 'mrp.read'
        with db.cursor() as cur:
            cur.execute('SELECT count(*) FROM platform.agent_drafts WHERE workflow_id=%s', (wid,))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT count(*) FROM platform.agent_tool_audit WHERE workflow_id=%s AND outcome='ALLOWED' AND tool_name='mrp.read'", (wid,))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT count(*) FROM platform.workflow_outbox WHERE instance_id=%s AND event_id LIKE 'AGENT:%%'", (wid,))
            assert cur.fetchone()[0] == 1
