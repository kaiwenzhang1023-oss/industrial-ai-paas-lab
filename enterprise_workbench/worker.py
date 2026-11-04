"""Version B RC2 internal execution worker, PostgreSQL SKIP LOCKED + leases.

DONE is a durable *internal* receipt. There is deliberately no ERP/MES/SRM
external write. Future external adapters must implement their own dedup ledger.
"""
from __future__ import annotations
import json
from uuid import UUID


def claim(conn, owner: str, *, tenant: str, limit: int = 10, lease_seconds: int = 30):
    if not owner or len(owner) > 100 or not tenant or len(tenant) > 128 or not 1 <= limit <= 100 or not 1 <= lease_seconds <= 3600:
        raise ValueError('INVALID_WORKER_CLAIM')
    with conn.transaction():
        rows = conn.execute("""WITH eligible AS (
          SELECT command_id FROM version_b_rc2.outbox
          WHERE tenant_id=%s AND ((status IN ('PENDING','RETRY') AND next_attempt_at <= now())
             OR (status = 'CLAIMED' AND lease_until < now()))
          ORDER BY created_at,command_id FOR UPDATE SKIP LOCKED LIMIT %s)
          UPDATE version_b_rc2.outbox o SET status='CLAIMED',
            lease_owner=%s,lease_until=now()+(%s * interval '1 second'),
            attempts=attempts+1,updated_at=now()
          FROM eligible e WHERE o.command_id=e.command_id
          RETURNING o.command_id,o.tenant_id,o.run_id,o.payload,o.attempts""",
          (tenant,limit,owner,lease_seconds)).fetchall()
        for command_id,tenant,run_id,*_ in rows:
            conn.execute("""UPDATE version_b_rc2.workflow_states SET status='RUNNING',
                 version=version+1,updated_at=now() WHERE tenant_id=%s AND run_id=%s
                 AND status IN ('APPROVED_QUEUED','RETRY_PENDING','RUNNING')""",(tenant,run_id))
        return [dict(zip(('command_id','tenant','run_id','payload','attempts'),r)) for r in rows]


def execute_internal(conn, command: dict):
    """Verify durable plan and decision, then return an internal-only receipt.

    The handler never talks to external systems or mutates inventory.
    """
    row=conn.execute("""SELECT r.status, d.decision FROM platform.requirement_runs r
      JOIN version_b_rc2.decisions d ON d.run_id=r.run_id AND d.tenant_id=%s
      WHERE r.run_id=%s AND d.command_id=%s""",
      (command['tenant'],command['run_id'],command['command_id'])).fetchone()
    if row != ('COMPLETED','APPROVED'):
        raise ValueError('PLAN_OR_APPROVAL_NOT_EXECUTABLE')
    return {'execution_type':'INTERNAL_VALIDATION_ONLY','mrp_run_id':command['run_id'],
            'external_effect':'NONE','execution_status':'EXECUTED_INTERNAL'}


def finish(conn, command_id, owner: str, *, receipt=None, error=None, max_attempts=4):
    if (receipt is None) == (error is None): raise ValueError('RECEIPT_XOR_ERROR_REQUIRED')
    if not 1 <= max_attempts <= 20: raise ValueError('INVALID_RETRY_LIMIT')
    with conn.transaction():
        row=conn.execute("""SELECT tenant_id,run_id,attempts FROM version_b_rc2.outbox
             WHERE command_id=%s AND status='CLAIMED' AND lease_owner=%s
               AND lease_until>now() FOR UPDATE""", (command_id,owner)).fetchone()
        if row is None: return False  # stale lease cannot acknowledge
        tenant,run_id,attempts=row
        if receipt is not None:
            if receipt.get('external_effect') != 'NONE' or receipt.get('execution_type') != 'INTERNAL_VALIDATION_ONLY':
                raise ValueError('UNAUTHORIZED_EXTERNAL_EFFECT_RECEIPT')
            conn.execute("""INSERT INTO version_b_rc2.execution_receipts
              (command_id,tenant_id,run_id,result) VALUES(%s,%s,%s,%s::jsonb)
              ON CONFLICT (command_id) DO NOTHING""",(command_id,tenant,run_id,json.dumps(receipt)))
            conn.execute("""UPDATE version_b_rc2.outbox SET status='DONE',last_error=NULL,
              lease_owner=NULL,lease_until=NULL,updated_at=now() WHERE command_id=%s""",(command_id,))
            status='EXECUTED_INTERNAL'
        else:
            status='FAILED_TERMINAL' if attempts>=max_attempts else 'RETRY_PENDING'
            next_status='DEAD' if attempts>=max_attempts else 'RETRY'
            delay=min(300, 2 ** min(attempts,8))
            conn.execute("""UPDATE version_b_rc2.outbox SET status=%s,last_error=%s,
             next_attempt_at=now()+(%s * interval '1 second'),lease_owner=NULL,
             lease_until=NULL,updated_at=now() WHERE command_id=%s""",
             (next_status,str(error)[:240],delay,command_id))
        conn.execute("""UPDATE version_b_rc2.workflow_states SET status=%s,version=version+1,
          updated_at=now() WHERE tenant_id=%s AND run_id=%s""",(status,tenant,run_id))
        conn.execute("""INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
          VALUES(%s,%s,%s,%s,%s::jsonb)""",
          (tenant,owner,'WORKER_'+status,str(command_id),json.dumps({'run_id':run_id,'attempt':attempts,'error':str(error)[:240] if error else None})))
        return True


def process_batch(connect, *, owner: str, tenant: str, limit=10, fail_injection=False):
    """One batch; no background daemon, queue broker, or external writes."""
    with connect() as conn:
        jobs=claim(conn,owner,tenant=tenant,limit=limit)
    results=[]
    for job in jobs:
        try:
            if fail_injection: raise RuntimeError('RC2_TEST_INJECTED_FAILURE')
            with connect() as conn:
                receipt=execute_internal(conn,job)
            with connect() as conn:
                ok=finish(conn,job['command_id'],owner,receipt=receipt)
            results.append({'command_id':str(job['command_id']),'status':'DONE' if ok else 'LEASE_EXPIRED'})
        except Exception:
            # Never publish credentials or raw DB errors in user-visible output.
            with connect() as conn:
                ok=finish(conn,job['command_id'],owner,error='INTERNAL_EXECUTION_FAILED')
            results.append({'command_id':str(job['command_id']),'status':'RETRY_OR_DEAD' if ok else 'LEASE_EXPIRED'})
    return results
