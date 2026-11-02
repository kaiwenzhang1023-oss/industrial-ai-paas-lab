'''M3-01 durable workflow state machine. Requires real PostgreSQL; no in-memory fallback.

Event delivery is at-least-once; event_id is an idempotency key scoped globally.
Outbox delivery is also at-least-once: consumers MUST deduplicate message_id.
'''
import hashlib
import json
import uuid

TRANSITIONS = {
 ('CREATED','START'): 'VALIDATING',
 ('VALIDATING','VALIDATION_PASSED'): 'CALCULATING',
 ('CALCULATING','MRP_COMPLETED'): 'GENERATING_ADVICE',
 ('GENERATING_ADVICE','ADVICE_DRAFTED'): 'WAITING_REVIEW',
 ('VALIDATING','FAIL'): 'FAILED',
 ('CALCULATING','FAIL'): 'FAILED',
 ('GENERATING_ADVICE','FAIL'): 'FAILED',
 ('FAILED','RETRY'): 'VALIDATING',
 ('CREATED','CANCEL'): 'CANCELLED',
 ('VALIDATING','CANCEL'): 'CANCELLED',
 ('CALCULATING','CANCEL'): 'CANCELLED',
 ('GENERATING_ADVICE','CANCEL'): 'CANCELLED',
 ('WAITING_REVIEW','CANCEL'): 'CANCELLED',
}

class WorkflowConflict(ValueError): pass
class WorkflowNotFound(KeyError): pass

def _hash(event_type, payload):
    return hashlib.sha256(json.dumps({'event_type':event_type,'payload':payload},sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def create(conn, order_id, workflow_id=None):
    workflow_id=workflow_id or 'WF-'+uuid.uuid4().hex
    if conn.info.transaction_status.name != 'IDLE': raise RuntimeError('WORKFLOW_REQUIRES_IDLE_CONNECTION')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('INSERT INTO platform.workflow_instances(instance_id,order_id,state,version,trace_id) VALUES(%s,%s,%s,%s,%s)',(workflow_id,order_id,'CREATED',0,'TRACE-'+uuid.uuid4().hex))
        with conn.cursor() as cur:
            from psycopg.types.json import Jsonb
            init_event='INIT:'+workflow_id
            cur.execute('''INSERT INTO platform.workflow_inbox(event_id,instance_id,event_type,payload_hash,resulting_version)
                           VALUES(%s,%s,%s,%s,0)''',(init_event,workflow_id,'WORKFLOW_CREATED',_hash('WORKFLOW_CREATED',{})))
            cur.execute('''INSERT INTO platform.workflow_outbox(instance_id,event_id,topic,payload)
                           VALUES(%s,%s,%s,%s)''', (workflow_id,init_event,'workflow.state_changed',
                           Jsonb({'workflow_id':workflow_id,'event_id':init_event,'from_state':None,'to_state':'CREATED','version':0})))
    return read(conn,workflow_id)

def read(conn,workflow_id):
    with conn.cursor() as cur:
        cur.execute('SELECT instance_id,order_id,state,version,mrp_run_id,error_code FROM platform.workflow_instances WHERE instance_id=%s',(workflow_id,))
        row=cur.fetchone()
    if row is None: raise WorkflowNotFound(workflow_id)
    return dict(zip(('workflow_id','order_id','state','version','mrp_run_id','error_code'),row))

def dispatch(conn,workflow_id,event_id,event_type,payload=None,expected_version=None, *, _within_transaction=False):
    '''Atomically update state, inbox, audit, outbox; duplicate event returns original result.

    A duplicate event with changed payload/type is rejected, even after a state change.
    '''
    payload=payload if payload is not None else {}
    if not isinstance(payload,dict): raise ValueError('EVENT_PAYLOAD_MUST_BE_OBJECT')
    digest=_hash(event_type,payload)
    if _within_transaction:
        if conn.info.transaction_status.name != 'INTRANS': raise RuntimeError('WORKFLOW_ATOMIC_REQUIRES_TRANSACTION')
    elif conn.info.transaction_status.name != 'IDLE':
        raise RuntimeError('WORKFLOW_REQUIRES_IDLE_CONNECTION')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT state,version,mrp_run_id FROM platform.workflow_instances WHERE instance_id=%s FOR UPDATE',(workflow_id,))
            row=cur.fetchone()
            if row is None: raise WorkflowNotFound(workflow_id)
            state,version,existing_mrp=row
            cur.execute('SELECT instance_id,payload_hash,resulting_version FROM platform.workflow_inbox WHERE event_id=%s',(event_id,))
            seen=cur.fetchone()
            if seen:
                if seen[0]!=workflow_id or seen[1]!=digest: raise WorkflowConflict('EVENT_ID_PAYLOAD_CONFLICT')
                return {'workflow_id':workflow_id,'state':state,'version':version,'duplicate':True,'original_version':seen[2]}
            if expected_version is not None and expected_version!=version: raise WorkflowConflict('STALE_WORKFLOW_VERSION')
            target=TRANSITIONS.get((state,event_type))
            if target is None: raise WorkflowConflict(f'INVALID_TRANSITION:{state}:{event_type}')
            mrp_run_id=existing_mrp
            if event_type=='MRP_COMPLETED':
                mrp_run_id=payload.get('mrp_run_id')
                if not isinstance(mrp_run_id,str) or not mrp_run_id: raise ValueError('MRP_RUN_ID_REQUIRED')
                # Prevent fabricated completion; M2's durable result must exist.
                cur.execute('SELECT 1 FROM platform.requirement_runs WHERE run_id=%s AND status=%s',(mrp_run_id,'COMPLETED'))
                if cur.fetchone() is None: raise WorkflowConflict('MRP_RESULT_NOT_PERSISTED')
            error_code=payload.get('error_code') if event_type=='FAIL' else None
            cur.execute('''UPDATE platform.workflow_instances SET state=%s,version=version+1,mrp_run_id=%s,error_code=%s,updated_at=now()
                           WHERE instance_id=%s''',(target,mrp_run_id,error_code,workflow_id))
            cur.execute('''INSERT INTO platform.workflow_inbox(event_id,instance_id,event_type,payload_hash,resulting_version)
                           VALUES(%s,%s,%s,%s,%s)''',(event_id,workflow_id,event_type,digest,version+1))
            cur.execute('''INSERT INTO platform.workflow_audit(instance_id,event_id,from_state,to_state,version)
                           VALUES(%s,%s,%s,%s,%s)''',(workflow_id,event_id,state,target,version+1))
            cur.execute('''INSERT INTO platform.workflow_outbox(instance_id,event_id,topic,payload)
                           VALUES(%s,%s,%s,%s)''',(workflow_id,event_id,'workflow.state_changed',__import__('psycopg').types.json.Jsonb({'workflow_id':workflow_id,'event_id':event_id,'from_state':state,'to_state':target,'version':version+1})))
    return {'workflow_id':workflow_id,'state':target,'version':version+1,'duplicate':False}

def pending_outbox(conn,limit=20):
    '''Read pending notifications; acknowledge only after external publish succeeds.'''
    with conn.cursor() as cur:
        cur.execute('''SELECT message_id,instance_id,topic,payload FROM platform.workflow_outbox
                       WHERE status='PENDING' ORDER BY message_id LIMIT %s''',(limit,))
        return [dict(zip(('message_id','workflow_id','topic','payload'),r)) for r in cur.fetchall()]

def acknowledge_outbox(conn,message_id):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("UPDATE platform.workflow_outbox SET status='DELIVERED',delivered_at=now(),attempts=attempts+1 WHERE message_id=%s AND status='PENDING' RETURNING message_id",(message_id,))
            return cur.fetchone() is not None


def dispatch_in_transaction(conn, workflow_id, event_id, event_type, payload=None, expected_version=None):
    """Internal composition point: dispatch participates in caller's transaction.

    The nested psycopg transaction is a savepoint, not an independent commit.
    The caller controls final commit/rollback of draft, audit, inbox and outbox.
    """
    return dispatch(conn, workflow_id, event_id, event_type, payload,
                    expected_version, _within_transaction=True)
