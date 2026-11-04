"""Version B RC2: authenticated tenant-scoped, PostgreSQL-only business boundary.

Execution receipts describe an INTERNAL validation process. No external ERP/MES
write is implied. In contrast, RC8 Workbench calculations remain local.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from app.db.repository import connect, calculate_and_save, read_run
from .reconciliation import numeric_diff
from .worker import process_batch

router = APIRouter(prefix='/api/v1/version-b/enterprise', tags=['Version B RC2'])

class Identity(BaseModel):
    actor: str
    tenant: str
    role: str

class Decision(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    decision: Literal['APPROVED','REJECTED']
    reason: str = Field(min_length=3, max_length=1000)
    idempotency_key: str = Field(min_length=8, max_length=128)

class Reconcile(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    a_snapshot: dict
    a_result: dict
    idempotency_key: str = Field(min_length=8, max_length=128)
    mappings: list[dict] = Field(default_factory=lambda:[
        {'name':'shortage_qty','a_path':'metrics.shortage_qty','b_path':'summary.net_qty','unit':'EA','tolerance':'0.001'}])

class McpCall(BaseModel):
    tool: Literal['mrp.get_run','workflow.get_command','reconciliation.get']
    arguments: dict = Field(default_factory=dict)

# AuthN is independent of role authorization; unconfigured system fails closed.
def identity(authorization: str | None = Header(default=None)) -> Identity:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401,detail='AUTH_REQUIRED')
    token=authorization[7:]
    config=os.environ.get('VERSION_B_RC2_IDENTITIES_JSON','')
    if not config: raise HTTPException(503,detail='IDENTITIES_NOT_CONFIGURED')
    try:
        entries=json.loads(config)
        if not isinstance(entries,list) or len(entries)>100: raise ValueError()
    except (ValueError,TypeError): raise HTTPException(503,detail='INVALID_IDENTITY_CONFIGURATION')
    if not 8 <= len(token) <= 512: raise HTTPException(401,detail='INVALID_CREDENTIALS')
    for entry in entries:
        if isinstance(entry,dict) and isinstance(entry.get('token'),str) and hmac.compare_digest(token,entry['token']):
            try: i=Identity(actor=entry['actor'],tenant=entry['tenant'],role=entry['role'])
            except (KeyError,ValueError): raise HTTPException(503,detail='INVALID_IDENTITY_CONFIGURATION')
            if not i.actor or not i.tenant or i.role not in {'viewer','planner','approver','operator','admin'}:
                raise HTTPException(503,detail='INVALID_IDENTITY_CONFIGURATION')
            return i
    raise HTTPException(401,detail='INVALID_CREDENTIALS')

def require(i: Identity, allowed: set[str]):
    if i.role not in allowed: raise HTTPException(403,detail='ROLE_FORBIDDEN')

def pg():
    try: return connect()
    except Exception: raise HTTPException(503,detail='DATABASE_UNAVAILABLE')

def fingerprint(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()

def check_run(conn,i,run_id):
    found=conn.execute('SELECT 1 FROM version_b_rc2.run_tenants WHERE tenant_id=%s AND run_id=%s',(i.tenant,run_id)).fetchone()
    if not found: raise HTTPException(404,detail='RUN_NOT_FOUND')

def _workflow(conn, i, run_id, lock=False):
    check_run(conn,i,run_id)
    q='SELECT status,version FROM version_b_rc2.workflow_states WHERE tenant_id=%s AND run_id=%s'
    if lock:q+=' FOR UPDATE'
    r=conn.execute(q,(i.tenant,run_id)).fetchone()
    if not r: raise HTTPException(409,detail='WORKFLOW_MISSING')
    return r

def _command(conn,i,command_id):
    row=conn.execute('''SELECT d.run_id,d.decision,d.actor_id,o.status,o.attempts,o.last_error,
             e.result FROM version_b_rc2.decisions d
             LEFT JOIN version_b_rc2.outbox o ON o.command_id=d.command_id
             LEFT JOIN version_b_rc2.execution_receipts e ON e.command_id=d.command_id
             WHERE d.tenant_id=%s AND d.command_id=%s''',(i.tenant,command_id)).fetchone()
    if not row: raise HTTPException(404,detail='COMMAND_NOT_FOUND')
    return {'command_id':str(command_id),'run_id':row[0],'decision':row[1],
            'actor':row[2],'status':row[3] or 'NOT_EXECUTED',
            'attempts':row[4] or 0,'last_error':row[5],
            'receipt':row[6], 'external_execution':False}

@router.get('/me')
def me(i: Identity=Depends(identity)): return i.model_dump()

@router.post('/mrp/runs',status_code=201)
def mrp_run(i: Identity=Depends(identity)):
    require(i,{'planner','admin'})
    try:
        with pg() as conn:
            # Tenant registration, snapshot, workflow and plan all commit together.
            result=calculate_and_save(conn,rc2_identity=(i.tenant,i.actor))
        return {'tenant':i.tenant,'source':'postgresql','simulation':False,**result}
    except HTTPException:raise
    except ValueError:raise HTTPException(422,detail='MRP_VALIDATION_ERROR')
    except Exception:raise HTTPException(503,detail='MRP_PERSISTENCE_UNAVAILABLE')

@router.get('/mrp/runs/{run_id}')
def get_run(run_id: str,i: Identity=Depends(identity)):
    require(i,{'viewer','planner','approver','operator','admin'})
    try:
        with pg() as conn:
            check_run(conn,i,run_id)
            result=read_run(conn,run_id)
            snapshot=conn.execute('''SELECT payload,input_hash FROM version_b_rc2.run_inputs
              WHERE tenant_id=%s AND run_id=%s''',(i.tenant,run_id)).fetchone()
            if snapshot is None:raise HTTPException(409,detail='SNAPSHOT_EVIDENCE_MISSING')
        return {'tenant':i.tenant,'run':result,'canonical_snapshot':snapshot[0],
                'snapshot_hash':snapshot[1],'source':'postgresql'}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='MRP_READ_UNAVAILABLE')

@router.get('/workflows/{run_id}')
def workflow(run_id: str,i: Identity=Depends(identity)):
    try:
        with pg() as conn:
            state,version=_workflow(conn,i,run_id)
            events=conn.execute('''SELECT action,actor_id,ref_id,created_at FROM version_b_rc2.audit
              WHERE tenant_id=%s AND details->>'run_id'=%s ORDER BY id DESC LIMIT 30''',
              (i.tenant,run_id)).fetchall()
        return {'run_id':run_id,'state':state,'version':version,
                'events':[{'action':a,'actor':b,'reference':c,'at':d.isoformat()} for a,b,c,d in events]}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='WORKFLOW_READ_UNAVAILABLE')

@router.post('/decisions',status_code=202)
def decision(body: Decision,i: Identity=Depends(identity)):
    require(i,{'approver','admin'})
    try:
        with pg() as conn:
            with conn.transaction():
                state,version=_workflow(conn,i,body.run_id,lock=True)
                existing=conn.execute('''SELECT run_id,decision,reason,command_id,actor_id
                  FROM version_b_rc2.decisions WHERE tenant_id=%s AND idempotency_key=%s''',
                  (i.tenant,body.idempotency_key)).fetchone()
                if existing:
                    if existing[0]!=body.run_id or existing[1]!=body.decision or existing[2]!=body.reason or existing[4]!=i.actor:
                        raise HTTPException(409,detail='IDEMPOTENCY_CONFLICT')
                    return {**_command(conn,i,existing[3]),'idempotent_replay':True}
                if state!='WAITING_REVIEW':raise HTTPException(409,detail='WORKFLOW_NOT_REVIEWABLE')
                command_id=uuid.uuid4()
                conn.execute('''INSERT INTO version_b_rc2.decisions
                  (tenant_id,run_id,actor_id,idempotency_key,decision,reason,command_id)
                  VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                  (i.tenant,body.run_id,i.actor,body.idempotency_key,body.decision,body.reason,command_id))
                new='APPROVED_QUEUED' if body.decision=='APPROVED' else 'REJECTED'
                conn.execute('''UPDATE version_b_rc2.workflow_states SET status=%s,
                  version=version+1,updated_at=now() WHERE tenant_id=%s AND run_id=%s''',
                  (new,i.tenant,body.run_id))
                if body.decision=='APPROVED':
                    conn.execute('''INSERT INTO version_b_rc2.outbox(command_id,tenant_id,run_id,payload,status)
                      VALUES(%s,%s,%s,%s::jsonb,'PENDING')''',
                      (command_id,i.tenant,body.run_id,json.dumps({'action':'VALIDATE_APPROVED_MRP','actor':i.actor})))
                conn.execute('''INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
                  VALUES(%s,%s,%s,%s,%s::jsonb)''',
                  (i.tenant,i.actor,body.decision,str(command_id),json.dumps({'run_id':body.run_id,'reason':body.reason,'version':version+1})))
        return {'command_id':str(command_id),'status':'ACCEPTED',
                'execution_status':'PENDING' if body.decision=='APPROVED' else 'NOT_EXECUTED',
                'external_execution':False}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='DECISION_PERSISTENCE_UNAVAILABLE')

@router.get('/commands/{command_id}')
def command(command_id:uuid.UUID,i:Identity=Depends(identity)):
    try:
        with pg() as conn:return _command(conn,i,command_id)
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='COMMAND_READ_UNAVAILABLE')

@router.post('/worker/dispatch')
def worker_dispatch(i:Identity=Depends(identity),limit:int=Query(default=10,ge=1,le=50)):
    require(i,{'operator','admin'})
    try:
        processed=process_batch(pg,owner='RC2-OP-'+i.actor,tenant=i.tenant,limit=limit)
        return {'processed':processed,'external_execution':False,'execution_type':'INTERNAL_VALIDATION_ONLY'}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='WORKER_UNAVAILABLE')

@router.post('/reconciliation',status_code=201)
def reconcile(body:Reconcile,i:Identity=Depends(identity)):
    require(i,{'planner','approver','admin'})
    try:
        with pg() as conn:
            with conn.transaction():
                check_run(conn,i,body.run_id)
                run=read_run(conn,body.run_id)  # B side MUST come from persisted PG16, not user JSON.
                snap=conn.execute('''SELECT payload,input_hash FROM version_b_rc2.run_inputs
                  WHERE tenant_id=%s AND run_id=%s''',(i.tenant,body.run_id)).fetchone()
                if not snap:raise HTTPException(409,detail='SNAPSHOT_EVIDENCE_MISSING')
                if fingerprint(body.a_snapshot)!=snap[1] or fingerprint(snap[0])!=snap[1] or body.a_result.get('input_hash')!=snap[1]:
                    result={'status':'SNAPSHOT_MISMATCH','pass':False,'items':[],
                            'explanation':'RC8 and PG16 input snapshot must have identical canonical hashes; client-reported results are untrusted.'}
                else:
                    from decimal import Decimal
                    lines=run['lines']
                    b={'summary':{k:str(sum(Decimal(x[k]) for x in lines)) for k in ('gross','net','planned')}}
                    b['summary']['peg_count']=len(run['pegs'])
                    result=numeric_diff(body.a_result,b,body.mappings,same_snapshot=True)
                    result['status']='CLIENT_ATTESTED_'+result['status']
                    result['explanation']='Same input hash verified; Version A values were supplied by the browser, not independently recomputed on server.'
                result.update({'a_snapshot_hash':fingerprint(body.a_snapshot),'b_snapshot_hash':snap[1],
                               'b_run_id':body.run_id,'a_result_untrusted':True,'source':'postgresql'})
                digest=fingerprint({'run_id':body.run_id,'a_snapshot':body.a_snapshot,
                                    'a_result':body.a_result,'mappings':body.mappings})
                previous=conn.execute('''SELECT run_id,payload FROM version_b_rc2.reconciliation
                  WHERE tenant_id=%s AND idempotency_key=%s''', (i.tenant,body.idempotency_key)).fetchone()
                if previous:
                    if previous[0]!=body.run_id or previous[1].get('request_hash')!=digest:
                        raise HTTPException(409,detail='IDEMPOTENCY_CONFLICT')
                    return {'tenant':i.tenant,**previous[1]}
                result['request_hash']=digest
                conn.execute('''INSERT INTO version_b_rc2.reconciliation
                  (tenant_id,run_id,actor_id,idempotency_key,payload) VALUES(%s,%s,%s,%s,%s::jsonb)''',
                  (i.tenant,body.run_id,i.actor,body.idempotency_key,json.dumps(result)))
        return {'tenant':i.tenant,**result}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='RECONCILIATION_UNAVAILABLE')

@router.post('/mcp/tools/call')
def mcp_call(body:McpCall,i:Identity=Depends(identity)):
    """Authenticated allowlisted local MCP-style facade; never starts an external tool."""
    require(i,{'viewer','planner','approver','operator','admin'})
    try:
        if body.tool=='mrp.get_run':
            if set(body.arguments)!={'run_id'} or not isinstance(body.arguments['run_id'],str):
                raise HTTPException(422,detail='INVALID_TOOL_ARGUMENTS')
            data=get_run(body.arguments['run_id'],i)
        elif body.tool=='workflow.get_command':
            if set(body.arguments)!={'command_id'}:raise HTTPException(422,detail='INVALID_TOOL_ARGUMENTS')
            try: cid=uuid.UUID(body.arguments['command_id'])
            except (ValueError,TypeError,AttributeError):raise HTTPException(422,detail='INVALID_COMMAND_ID')
            with pg() as conn:data=_command(conn,i,cid)
        else:
            if set(body.arguments)!={'idempotency_key'}:raise HTTPException(422,detail='INVALID_TOOL_ARGUMENTS')
            with pg() as conn:
                row=conn.execute('''SELECT payload FROM version_b_rc2.reconciliation
                   WHERE tenant_id=%s AND idempotency_key=%s''',(i.tenant,body.arguments['idempotency_key'])).fetchone()
            if not row:raise HTTPException(404,detail='RECONCILIATION_NOT_FOUND')
            data=row[0]
        return {'tool':body.tool,'result':data,'read_only':True,'external_effect':'NONE'}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='MCP_TOOL_UNAVAILABLE')

# RC3 additions are intentionally additive. RC2/G2 API behavior is preserved.
class VerifiedReconcile(BaseModel):
    run_id: str = Field(min_length=1,max_length=128)
    idempotency_key: str = Field(min_length=8,max_length=128)
    reference_id: Literal['RC8_SEED_MULTI_ORDER_V1']='RC8_SEED_MULTI_ORDER_V1'

@router.post('/reconciliation/verified',status_code=201)
def verified_reconcile(body: VerifiedReconcile,i:Identity=Depends(identity)):
    """Compare pinned, native JS RC8 witness to real PG16 persisted plan.

    No caller-provided A results. Never claim arbitrary snapshots comparable.
    """
    require(i,{'planner','approver','admin'})
    from g3.core import verified_comparison, load_reference, InvalidReference, IncompatibleSnapshot
    try:
        with pg() as conn:
            with conn.transaction():
                check_run(conn,i,body.run_id)
                row=conn.execute('''SELECT payload,input_hash FROM version_b_rc2.run_inputs
                    WHERE tenant_id=%s AND run_id=%s''',(i.tenant,body.run_id)).fetchone()
                if row is None:raise HTTPException(409,detail='SNAPSHOT_EVIDENCE_MISSING')
                run=read_run(conn,body.run_id)
                if row[1]!=run['input_hash'] or fingerprint(row[0])!=row[1]:
                    raise HTTPException(409,detail='PERSISTED_SNAPSHOT_FENCE_INVALID')
                try:result=verified_comparison(row[0],run,load_reference())
                except IncompatibleSnapshot:raise HTTPException(409,detail='RC8_REFERENCE_SNAPSHOT_NOT_COMPARABLE')
                except InvalidReference:raise HTTPException(503,detail='RC8_REFERENCE_INTEGRITY_FAILED')
                digest=fingerprint({'type':'VERIFIED_RC8_REFERENCE','run_id':body.run_id,
                    'reference_id':body.reference_id,'snapshot':result['a_input_hash']})
                old=conn.execute('''SELECT run_id,payload FROM version_b_rc2.reconciliation
                    WHERE tenant_id=%s AND idempotency_key=%s''',
                    (i.tenant,body.idempotency_key)).fetchone()
                if old:
                    if old[0]!=body.run_id or old[1].get('request_hash')!=digest:
                        raise HTTPException(409,detail='IDEMPOTENCY_CONFLICT')
                    return {'tenant':i.tenant,**old[1],'idempotent_replay':True}
                result.update({'request_hash':digest,'run_id':body.run_id,
                               'source':'PERSISTED_POSTGRESQL_AND_FROZEN_RC8_JS_WITNESS',
                               'a_result_untrusted':False,'verified_reference':True})
                conn.execute('''INSERT INTO version_b_rc2.reconciliation
                    (tenant_id,run_id,actor_id,idempotency_key,payload)
                    VALUES(%s,%s,%s,%s,%s::jsonb)''',
                    (i.tenant,body.run_id,i.actor,body.idempotency_key,json.dumps(result)))
                conn.execute('''INSERT INTO version_b_rc2.audit
                    (tenant_id,actor_id,action,ref_id,details)
                    VALUES(%s,%s,'RC3_VERIFIED_RECONCILIATION',%s,%s::jsonb)''',
                    (i.tenant,i.actor,body.run_id,json.dumps({
                        'run_id':body.run_id,'status':result['status'],
                        'reference_id':body.reference_id,'difference_count':len(result['differences'])})))
        return {'tenant':i.tenant,**result}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='VERIFIED_RECONCILIATION_UNAVAILABLE')

@router.post('/mcp/rpc')
def mcp_rpc(message:dict,i:Identity=Depends(identity)):
    """Authenticated JSON-RPC HTTP test adapter; stdio server is canonical MCP transport."""
    require(i,{'viewer','planner','approver','operator','admin'})
    from g3.mcp import rpc_response,invoke
    def dispatch(name,args,request_id):
        with pg() as conn:return invoke(conn,i,name,args,request_id)
    result=rpc_response(message,dispatch)
    if result is None:
        from fastapi.responses import Response
        return Response(status_code=202)
    return result
