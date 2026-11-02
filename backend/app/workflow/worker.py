"""Lease-based PostgreSQL outbox dispatcher; at-least-once delivery.

The publish callback is supplied by the application. For M3-01 V0.2 it can be a
local deterministic workflow driver, but no external broker or ERP write is assumed.
"""
from __future__ import annotations
import uuid
from datetime import timedelta
from app.workflow.runtime import dispatch, read, WorkflowConflict


def claim(conn, owner: str, limit: int = 10, lease_seconds: int = 30):
    if not owner or not 1 <= limit <= 100 or not 1 <= lease_seconds <= 3600:
        raise ValueError('INVALID_CLAIM_ARGUMENT')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("""WITH eligible AS (
              SELECT message_id FROM platform.workflow_outbox
              WHERE ((status='PENDING' AND next_attempt_at<=now())
                 OR (status='PROCESSING' AND lease_until<now()))
              ORDER BY message_id FOR UPDATE SKIP LOCKED LIMIT %s)
              UPDATE platform.workflow_outbox o
              SET status='PROCESSING',lease_owner=%s,
                  lease_until=now()+(%s * interval '1 second'),attempts=attempts+1
              FROM eligible e WHERE o.message_id=e.message_id
              RETURNING o.message_id,o.instance_id,o.topic,o.payload,o.attempts""",
              (limit,owner,lease_seconds))
            return [dict(zip(('message_id','workflow_id','topic','payload','attempts'),r)) for r in cur.fetchall()]


def finish(conn, message_id: int, owner: str, error: str | None = None,
           max_attempts: int = 5, retry_base_seconds: int = 2):
    if max_attempts < 1 or retry_base_seconds < 1: raise ValueError('INVALID_RETRY_POLICY')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("""SELECT attempts FROM platform.workflow_outbox
                           WHERE message_id=%s AND status='PROCESSING' AND lease_owner=%s
                             AND lease_until>=now() FOR UPDATE""",(message_id,owner))
            r=cur.fetchone()
            if r is None: return False
            attempts=r[0]
            if error is None:
                cur.execute("""UPDATE platform.workflow_outbox SET status='DELIVERED',
                    delivered_at=now(),lease_owner=NULL,lease_until=NULL,last_error=NULL
                    WHERE message_id=%s""",(message_id,))
            else:
                status='DEAD' if attempts>=max_attempts else 'PENDING'
                delay=min(3600,retry_base_seconds*(2**min(attempts-1,10)))
                cur.execute("""UPDATE platform.workflow_outbox SET status=%s,last_error=%s,
                    lease_owner=NULL,lease_until=NULL,
                    next_attempt_at=now()+(%s * interval '1 second')
                    WHERE message_id=%s""",(status,str(error)[:2000],delay,message_id))
            return True


def pump_once(conn, publisher, owner: str | None = None, limit: int = 10):
    """Publish outside transaction. Crash after publish => duplicate delivery possible."""
    owner=owner or 'worker-'+uuid.uuid4().hex
    messages=claim(conn,owner,limit)
    outcomes=[]
    for message in messages:
        try:
            publisher(message)
        except Exception as exc:
            recorded=finish(conn,message['message_id'],owner,error=str(exc))
            outcomes.append((message['message_id'],'RETRY_OR_DEAD' if recorded else 'LEASE_LOST'))
        else:
            recorded=finish(conn,message['message_id'],owner)
            outcomes.append((message['message_id'],'DELIVERED' if recorded else 'LEASE_LOST'))
    return outcomes


def auto_advance(conn, workflow_id: str, mrp_runner=None):
    """Controlled V0.2 automatic transitions, no invented MRP result.

    Only START and VALIDATION_PASSED are deterministic. For CALCULATING the
    caller MUST inject a real M2 runner returning a persisted run_id. The
    next Agent step is explicitly deferred to M3-02.
    """
    state=read(conn,workflow_id)
    transitions={'CREATED':'START','VALIDATING':'VALIDATION_PASSED'}
    if state['state'] in transitions:
        event=transitions[state['state']]
        return dispatch(conn,workflow_id,f'AUTO:{workflow_id}:{state["version"]}:{event}',event,{},expected_version=state['version'])
    if state['state']=='CALCULATING' and mrp_runner is not None:
        run_id=mrp_runner(state['order_id'])
        if not isinstance(run_id,str) or not run_id: raise ValueError('MRP_RUNNER_MUST_RETURN_RUN_ID')
        return dispatch(conn,workflow_id,f'AUTO:{workflow_id}:{state["version"]}:MRP_COMPLETED',
                        'MRP_COMPLETED',{'mrp_run_id':run_id},expected_version=state['version'])
    return {'workflow_id':workflow_id,'state':state['state'],'blocked':True,
            'reason':'MRP_RUNNER_REQUIRED' if state['state']=='CALCULATING' else 'NEXT_STAGE_NOT_IMPLEMENTED'}
