"""M3-01 V0.3 polling worker, driven by durable PostgreSQL outbox.

The handler is deliberately local: no external ERP write or AI invocation.
Delivery is at-least-once; deterministic MRP run IDs make crash replay safe.
"""
from __future__ import annotations
import argparse
import hashlib
import logging
import os
import signal
import threading
import time
from datetime import date
from app.db.repository import connect
from app.db.integrated import run_integrated, read_integrated_run
from app.workflow.runtime import read, WorkflowConflict
from app.workflow.worker import pump_once, auto_advance
from app.agent import generate_and_persist

LOG = logging.getLogger(__name__)


def durable_mrp_runner(conn, workflow_id: str, order_id: str, as_of: str):
    """Use M2 integrated PostgreSQL planner, with a replay-safe run ID.

    M2 integrated planning covers ALL confirmed orders; do not imply that it
    plans only the named order. Verify order membership before running.
    """
    date.fromisoformat(as_of)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM mock_erp.sales_orders WHERE order_id=%s AND status='CONFIRMED'", (order_id,))
        if cur.fetchone() is None:
            raise ValueError('WORKFLOW_ORDER_NOT_CONFIRMED')
    run_id='WFMRP-'+hashlib.sha256((workflow_id+'|'+as_of).encode()).hexdigest()[:32]
    with conn.cursor() as cur:
        cur.execute('SELECT status FROM platform.requirement_runs WHERE run_id=%s',(run_id,))
        existing=cur.fetchone()
    if existing is not None:
        saved=read_integrated_run(conn,run_id)
        if saved['status']!='COMPLETED' or saved['snapshot_as_of']!=as_of:
            raise WorkflowConflict('MRP_RUN_REPLAY_MISMATCH')
        return run_id
    # If a concurrent worker wins the same run ID, caller retries on next poll.
    return run_integrated(conn,as_of=as_of,run_id=run_id)['run_id']


def handle_notification(conn, message: dict, as_of: str):
    """Advance at most one step per notification. Each step emits a new outbox event."""
    if message['topic']!='workflow.state_changed':
        raise ValueError('UNSUPPORTED_OUTBOX_TOPIC')
    workflow_id=message['workflow_id']
    state=read(conn,workflow_id)
    payload=message['payload']
    # Old messages are harmless: the current state is authoritative.
    if int(payload.get('version',-1)) != state['version']:
        return {'workflow_id':workflow_id,'stale':True}
    if state['state']=='GENERATING_ADVICE':
        return generate_and_persist(conn,workflow_id)
    def runner(order_id):
        return durable_mrp_runner(conn,workflow_id,order_id,as_of)
    return auto_advance(conn,workflow_id,mrp_runner=runner)


def poll_once(dsn: str, owner: str, as_of: str, limit: int = 10):
    """Use independent DB connections per worker; publisher is outside claim transaction."""
    with connect(dsn) as conn:
        conn.autocommit=True
        return pump_once(conn,lambda msg:handle_notification(conn,msg,as_of),owner=owner,limit=limit)


def run_forever(dsn: str, owner: str, as_of: str, interval: float=1.0,
                stop: threading.Event | None=None, max_cycles: int | None=None):
    if interval <= 0: raise ValueError('INTERVAL_MUST_BE_POSITIVE')
    stop=stop or threading.Event()
    cycles=0
    while not stop.is_set():
        try:
            results=poll_once(dsn,owner,as_of)
            for message_id,outcome in results:
                LOG.info('outbox message=%s outcome=%s worker=%s',message_id,outcome,owner)
        except Exception:
            LOG.exception('worker poll failed; will retry')
        cycles+=1
        if max_cycles is not None and cycles>=max_cycles: break
        stop.wait(interval)
    return cycles


def main():
    parser=argparse.ArgumentParser(description='M3-01 V0.3 PostgreSQL workflow worker')
    parser.add_argument('--as-of',default=os.getenv('MRP_AS_OF','2026-11-20'))
    parser.add_argument('--owner',default='m3-worker-'+str(os.getpid()))
    parser.add_argument('--interval',type=float,default=1.0)
    parser.add_argument('--max-cycles',type=int,default=None)
    args=parser.parse_args()
    dsn=os.getenv('DATABASE_URL')
    if not dsn: parser.error('DATABASE_URL must be set')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    stop=threading.Event()
    def shutdown(*_): stop.set()
    signal.signal(signal.SIGINT,shutdown)
    if hasattr(signal,'SIGTERM'): signal.signal(signal.SIGTERM,shutdown)
    run_forever(dsn,args.owner,args.as_of,args.interval,stop,args.max_cycles)

if __name__=='__main__': main()
