"""Explicit one-time cloud demo bootstrap, run from backend folder.

Creates schema, seeds synthetic data, and prepares one reviewed-by-nobody
WAITING_REVIEW workflow. No ERP writes and no automated approvals.
"""
from pathlib import Path
import os
from app.db.repository import connect, seed
from app.db.integrated import seed_effective_bom
from app.workflow.runtime import create,read,dispatch
from app.workflow.scheduler import durable_mrp_runner
from app.agent import generate_and_persist
from app.workflow.receipt_dispatcher import dispatch_receipts

ROOT=Path(__file__).resolve().parents[2]
MIGRATIONS=['schema.sql','003_v03.sql','004_snapshot_fence.sql','005_effective_bom.sql',
 '006_m2_integration.sql','007_normalized_pegging.sql','008_workflow_runtime.sql',
 '009_workflow_worker.sql','010_agent_harness.sql','011_agent_governance.sql','012_outbox_receipts.sql']

def bootstrap():
    if os.getenv('CONFIRM_CLOUD_BOOTSTRAP')!='yes':
        raise SystemExit('Set CONFIRM_CLOUD_BOOTSTRAP=yes for explicit database initialization')
    with connect() as conn:
        conn.autocommit=True
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS public.lab_schema_migrations
                (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
        for name in MIGRATIONS:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM public.lab_schema_migrations WHERE filename=%s',(name,))
                if cur.fetchone(): continue
            sql=(ROOT/'database'/name).read_text(encoding='utf-8')
            # DDL migration files are shipped unchanged from the PG16 gate.
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute('INSERT INTO public.lab_schema_migrations(filename) VALUES(%s)',(name,))
            print('Applied',name)
        seed(conn,ROOT/'datasets/seed/multi_order.json')
        seed_effective_bom(conn)
        with conn.cursor() as cur:
            cur.execute('''SELECT instance_id FROM platform.workflow_instances
                WHERE order_id='SO-2026-001' ORDER BY created_at LIMIT 1''')
            found=cur.fetchone()
        wid=found[0] if found else create(conn,'SO-2026-001')['workflow_id']
        while True:
            current=read(conn,wid)
            state=current['state'];v=current['version']
            if state=='CREATED': dispatch(conn,wid,f'CLOUD:{wid}:START','START',{},expected_version=v)
            elif state=='VALIDATING': dispatch(conn,wid,f'CLOUD:{wid}:VALIDATED','VALIDATION_PASSED',{},expected_version=v)
            elif state=='CALCULATING':
                run_id=durable_mrp_runner(conn,wid,current['order_id'],'2026-11-20')
                dispatch(conn,wid,f'CLOUD:{wid}:MRP:{run_id}','MRP_COMPLETED',{'mrp_run_id':run_id},expected_version=v)
            elif state=='GENERATING_ADVICE': generate_and_persist(conn,wid)
            else: break
        if read(conn,wid)['state']!='WAITING_REVIEW':
            raise RuntimeError('CLOUD_DEMO_WORKFLOW_NOT_WAITING_REVIEW')
        outcomes=dispatch_receipts(conn,100,owner='v1-cloud-bootstrap')
        print('Cloud demo ready, workflow',wid,'receipts',len(outcomes))

if __name__=='__main__': bootstrap()
