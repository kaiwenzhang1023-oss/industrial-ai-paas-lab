"""Version B RC4 additive enterprise G4 boundaries.

All run data is taken from PostgreSQL, never a browser-supplied 'B result'.
What-if is a detached in-memory copy; dynamic A/B requires native JS execution.
"""
from __future__ import annotations
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from .rc2 import Identity, identity, require, pg, check_run, fingerprint, _workflow, _command
from app.db.repository import read_run
from g4.core import Change, PolicyRejected, what_if, dynamic_comparison
from g3.core import InvalidReference, IncompatibleSnapshot, snapshot_hash
from .rc35_planning import analyze

router = APIRouter(prefix='/api/v1/version-b/enterprise', tags=['Version B RC4 G4'])


class WhatIfRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    kind: Literal['stock', 'receipt', 'due']
    target: str = Field(min_length=1, max_length=128)
    quantity: str | None = Field(default=None, max_length=80)
    date: str | None = Field(default=None, max_length=32)


class DynamicRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128)


def _persisted_snapshot(conn, who, run_id):
    check_run(conn, who, run_id)
    record = conn.execute('''SELECT payload,input_hash FROM version_b_rc2.run_inputs
          WHERE tenant_id=%s AND run_id=%s''', (who.tenant, run_id)).fetchone()
    if record is None:
        raise HTTPException(409, detail='SNAPSHOT_EVIDENCE_MISSING')
    persisted = read_run(conn, run_id)
    if record[1] != persisted['input_hash'] or fingerprint(record[0]) != record[1]:
        raise HTTPException(409, detail='PERSISTED_SNAPSHOT_FENCE_INVALID')
    return record[0], persisted


@router.post('/what-if')
def simulate_what_if(body: WhatIfRequest, who: Identity = Depends(identity)):
    require(who, {'planner', 'admin'})
    try:
        with pg() as conn:
            snapshot, run = _persisted_snapshot(conn, who, body.run_id)
        result = what_if(snapshot, Change(body.kind, body.target, body.quantity, body.date))
        if snapshot_hash(snapshot) != result['baseline_snapshot_sha256']:
            raise HTTPException(409, detail='WHAT_IF_SOURCE_DRIFT')
        result.update({'tenant': who.tenant, 'run_id': body.run_id,
                       'original_run_input_hash': run['input_hash'],
                       'workflow_unchanged': True})
        return result
    except HTTPException:
        raise
    except PolicyRejected as exc:
        raise HTTPException(422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(503, detail='WHAT_IF_UNAVAILABLE') from None


@router.post('/reconciliation/dynamic', status_code=201)
def dynamic_reconcile(body: DynamicRequest, who: Identity = Depends(identity)):
    require(who, {'planner', 'approver', 'admin'})
    try:
        with pg() as conn:
            with conn.transaction():
                snapshot, persisted = _persisted_snapshot(conn, who, body.run_id)
                result = dynamic_comparison(snapshot, persisted)
                digest = fingerprint({'type':'DYNAMIC_NATIVE_A_VS_POSTGRES_B',
                        'run_id': body.run_id, 'input_hash': persisted['input_hash']})
                previous = conn.execute('''SELECT run_id,payload FROM version_b_rc2.reconciliation
                  WHERE tenant_id=%s AND idempotency_key=%s''',
                  (who.tenant, body.idempotency_key)).fetchone()
                if previous:
                    if previous[0] != body.run_id or previous[1].get('request_hash') != digest:
                        raise HTTPException(409, detail='IDEMPOTENCY_CONFLICT')
                    return {'tenant': who.tenant, **previous[1], 'idempotent_replay': True}
                result.update({'run_id': body.run_id, 'request_hash': digest,
                               'source': 'NATIVE_A_RC8_DYNAMIC_AND_B_PG16',
                               'verified_dynamic': True})
                conn.execute('''INSERT INTO version_b_rc2.reconciliation
                    (tenant_id,run_id,actor_id,idempotency_key,payload)
                    VALUES(%s,%s,%s,%s,%s::jsonb)''',
                    (who.tenant,body.run_id,who.actor,body.idempotency_key,json.dumps(result)))
                conn.execute('''INSERT INTO version_b_rc2.audit
                    (tenant_id,actor_id,action,ref_id,details)
                    VALUES(%s,%s,'RC4_DYNAMIC_NATIVE_A_B',%s,%s::jsonb)''',
                    (who.tenant,who.actor,body.run_id,json.dumps({
                        'run_id':body.run_id,'status':result['status'],
                        'difference_count':len(result['differences']),
                        'snapshot_hash':result['a_input_hash']})))
        return {'tenant': who.tenant, **result}
    except HTTPException:
        raise
    except IncompatibleSnapshot:
        raise HTTPException(409, detail='NATIVE_A_POLICY_NOT_COMPARABLE') from None
    except InvalidReference:
        raise HTTPException(503, detail='FROZEN_RC8_REFERENCE_INTEGRITY_FAILURE') from None
    except RuntimeError:
        raise HTTPException(503, detail='NATIVE_A_RUNTIME_UNAVAILABLE') from None
    except Exception:
        raise HTTPException(503, detail='DYNAMIC_RECONCILIATION_UNAVAILABLE') from None


@router.get('/review/overview/{run_id}')
def review_overview(run_id: str, who: Identity = Depends(identity)):
    require(who, {'viewer', 'planner', 'approver', 'operator', 'admin'})
    try:
        with pg() as conn:
            snapshot, persisted = _persisted_snapshot(conn, who, run_id)
            state, version = _workflow(conn,who,run_id)
            rec = conn.execute('''SELECT decision,command_id,actor_id,reason,created_at
                FROM version_b_rc2.decisions WHERE tenant_id=%s AND run_id=%s
                ORDER BY created_at DESC LIMIT 1''',(who.tenant,run_id)).fetchone()
            command = _command(conn,who,rec[1]) if rec else None
            audits = conn.execute('''SELECT action,actor_id,ref_id,created_at FROM version_b_rc2.audit
                 WHERE tenant_id=%s AND details->>'run_id'=%s ORDER BY id DESC LIMIT 30''',
                (who.tenant,run_id)).fetchall()
        return {'run_id': run_id, 'tenant':who.tenant,'source':'PERSISTED_POSTGRESQL',
                'snapshot_hash':persisted['input_hash'], 'workflow':{'state':state,'version':version},
                'plan':{'line_count':len(persisted['lines']),
                        'peg_count':len(persisted['pegs'])},
                'decision':({'type':rec[0],'actor':rec[2], 'reason':rec[3],
                    'at':rec[4].isoformat()} if rec else None),
                'command':command,'events':[{'action':a,'actor':b,'reference':c,
                    'at':t.isoformat()} for a,b,c,t in audits],
                'external_execution':False}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503,detail='REVIEW_OVERVIEW_UNAVAILABLE') from None


# RC3.5: tenant-fenced, server-paginated audit history. No client-supplied tenant
# may expand the authorized scope. Stable ID cursor avoids offset duplication.
@router.get('/audit/history')
def audit_history(
    run_id: str | None = Query(default=None, max_length=128),
    action: str | None = Query(default=None, max_length=100),
    actor: str | None = Query(default=None, max_length=128),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    who: Identity = Depends(identity),
):
    require(who, {'viewer', 'planner', 'approver', 'operator', 'admin'})
    try:
        with pg() as conn:
            if run_id:
                check_run(conn, who, run_id)
            conditions = ['tenant_id=%s']
            params = [who.tenant]
            if run_id:
                conditions.append("details->>'run_id'=%s")
                params.append(run_id)
            if action:
                conditions.append('action=%s')
                params.append(action)
            if actor:
                conditions.append('actor_id=%s')
                params.append(actor)
            if before_id is not None:
                conditions.append('id<%s')
                params.append(before_id)
            params.append(limit + 1)
            rows = conn.execute(
                'SELECT id,action,actor_id,ref_id,details,created_at '
                'FROM version_b_rc2.audit WHERE ' + ' AND '.join(conditions) +
                ' ORDER BY id DESC LIMIT %s', tuple(params)
            ).fetchall()
        more = len(rows) > limit
        page = rows[:limit]
        return {
            'tenant': who.tenant, 'source': 'PERSISTED_POSTGRESQL',
            'scope': 'AUTHORIZED_TENANT_ONLY', 'limit': limit,
            'events': [{'id': r[0], 'action': r[1], 'actor': r[2],
                        'reference': r[3], 'run_id': r[4].get('run_id'),
                        'at': r[5].isoformat()} for r in page],
            'next_before_id': page[-1][0] if more and page else None,
            'has_more': more,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, detail='AUDIT_HISTORY_UNAVAILABLE') from None


@router.get('/planning/time-buckets/{run_id}')
def time_buckets(run_id: str, granularity: Literal['day','week']='week',
                 who: Identity = Depends(identity)):
    """Read-only planning evidence; the MRP plan is not a confirmed shortage."""
    require(who, {'viewer','planner','approver','operator','admin'})
    try:
        with pg() as conn:
            snapshot, persisted = _persisted_snapshot(conn, who, run_id)
        result = analyze(snapshot, persisted['lines'], granularity)
        return {'tenant':who.tenant,'run_id':run_id,'source':'PERSISTED_POSTGRESQL',
                'snapshot_hash':persisted['input_hash'], **result}
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409,detail='PLANNING_EVIDENCE_INCONSISTENT') from None
    except Exception:
        raise HTTPException(503,detail='TIME_BUCKET_QUERY_UNAVAILABLE') from None


# RC3.5: proposed changes are separate from official MRP runs. Only an approver
# may submit one, and the worker still performs internal validation only.
class ProposalSave(BaseModel):
    expected_candidate_hash: str = Field(min_length=64,max_length=64)
    run_id: str = Field(min_length=1,max_length=128)
    kind: Literal['stock','receipt','due']
    target: str = Field(min_length=1,max_length=128)
    quantity: str | None = Field(default=None,max_length=80)
    date: str | None = Field(default=None,max_length=32)
    idempotency_key: str = Field(min_length=8,max_length=128)

class ProposalAction(BaseModel):
    idempotency_key: str = Field(min_length=8,max_length=128)
    reason: str = Field(min_length=3,max_length=1000)
    decision: Literal['APPROVED','REJECTED'] | None = None


def _proposal(conn, who, proposal_id, lock=False):
    sql='''SELECT proposal_id,run_id,actor_id,request_hash,input_hash,candidate_hash,
       change_request,simulation_result,status,command_id
       FROM version_b_rc2.proposals WHERE tenant_id=%s AND proposal_id=%s'''
    if lock:sql+=' FOR UPDATE'
    row=conn.execute(sql,(who.tenant,proposal_id)).fetchone()
    if row is None:raise HTTPException(404,detail='PROPOSAL_NOT_FOUND')
    return dict(zip(('proposal_id','run_id','actor_id','request_hash','input_hash',
                     'candidate_hash','change','result','status','command_id'),row))

@router.post('/proposals',status_code=201)
def save_proposal(body:ProposalSave,who:Identity=Depends(identity)):
    require(who,{'planner','admin'})
    from uuid import uuid4
    request_hash=fingerprint(body.model_dump(exclude={'idempotency_key'}))
    try:
        with pg() as conn:
            with conn.transaction():
                existing=conn.execute('''SELECT proposal_id,request_hash FROM version_b_rc2.proposals
                   WHERE tenant_id=%s AND idempotency_key=%s''',(who.tenant,body.idempotency_key)).fetchone()
                if existing:
                    if existing[1]!=request_hash:raise HTTPException(409,detail='IDEMPOTENCY_CONFLICT')
                    return {'proposal_id':str(existing[0]),'idempotent_replay':True,'source':'PERSISTED_POSTGRESQL'}
                snapshot,run=_persisted_snapshot(conn,who,body.run_id)
                state,_=_workflow(conn,who,body.run_id,lock=True)
                if state!='WAITING_REVIEW':raise HTTPException(409,detail='PLAN_NOT_REVIEWABLE')
                result=what_if(snapshot,Change(body.kind,body.target,body.quantity,body.date))
                if snapshot_hash(snapshot)!=result['baseline_snapshot_sha256']:
                    raise HTTPException(409,detail='SNAPSHOT_CHANGED')
                candidate_hash=result['candidate_snapshot_sha256']
                if candidate_hash!=body.expected_candidate_hash:
                    raise HTTPException(409,detail='CANDIDATE_PREVIEW_CHANGED_RECALCULATE')
                proposal_id=uuid4()
                conn.execute('''INSERT INTO version_b_rc2.proposals
                  (proposal_id,tenant_id,run_id,actor_id,idempotency_key,request_hash,
                   input_hash,candidate_hash,change_request,simulation_result)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)''',
                  (proposal_id,who.tenant,body.run_id,who.actor,body.idempotency_key,
                   request_hash,run['input_hash'],candidate_hash,
                   json.dumps(body.model_dump(exclude={'idempotency_key','expected_candidate_hash'})),json.dumps(result)))
                conn.execute('''INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
                  VALUES(%s,%s,'PROPOSAL_SAVED',%s,%s::jsonb)''',
                  (who.tenant,who.actor,str(proposal_id),json.dumps({'run_id':body.run_id,'candidate_hash':candidate_hash})))
        return {'proposal_id':str(proposal_id),'status':'DRAFT','run_id':body.run_id,
                'candidate_hash':candidate_hash,'source':'PERSISTED_POSTGRESQL',
                'external_execution':False}
    except HTTPException:raise
    except PolicyRejected as exc:raise HTTPException(422,detail=str(exc)) from None
    except Exception:
        raise HTTPException(503,detail='PROPOSAL_SAVE_UNAVAILABLE') from None

@router.get('/proposals/{proposal_id}')
def get_proposal(proposal_id:__import__('uuid').UUID,who:Identity=Depends(identity)):
    require(who,{'viewer','planner','approver','operator','admin'})
    try:
        with pg() as conn:
            row=_proposal(conn,who,proposal_id)
        return {'proposal_id':str(row['proposal_id']),'run_id':row['run_id'],
                'status':row['status'],'candidate_hash':row['candidate_hash'],
                'change':row['change'],'result':row['result'],
                'command_id':str(row['command_id']) if row['command_id'] else None,
                'source':'PERSISTED_POSTGRESQL'}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='PROPOSAL_READ_UNAVAILABLE') from None

@router.post('/proposals/{proposal_id}/cancel')
def cancel_proposal(proposal_id:__import__('uuid').UUID,body:ProposalAction,
                    who:Identity=Depends(identity)):
    require(who,{'planner','admin'})
    try:
        with pg() as conn:
            with conn.transaction():
                row=_proposal(conn,who,proposal_id,lock=True)
                if row['actor_id']!=who.actor and who.role!='admin':
                    raise HTTPException(403,detail='NOT_PROPOSAL_OWNER')
                if row['status']=='CANCELLED':return {'status':'CANCELLED','idempotent_replay':True}
                if row['status']!='DRAFT':raise HTTPException(409,detail='CANNOT_CANCEL_SUBMITTED_PROPOSAL')
                conn.execute('''UPDATE version_b_rc2.proposals SET status='CANCELLED',updated_at=now()
                   WHERE tenant_id=%s AND proposal_id=%s''',(who.tenant,proposal_id))
                conn.execute('''INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
                   VALUES(%s,%s,'PROPOSAL_CANCELLED',%s,%s::jsonb)''',
                   (who.tenant,who.actor,str(proposal_id),json.dumps({'run_id':row['run_id'],'reason':body.reason})))
        return {'status':'CANCELLED','external_execution':False}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='PROPOSAL_CANCEL_UNAVAILABLE') from None

@router.post('/proposals/{proposal_id}/review',status_code=202)
def review_proposal(proposal_id:__import__('uuid').UUID,body:ProposalAction,
                    who:Identity=Depends(identity)):
    require(who,{'approver','admin'})
    if body.decision is None:raise HTTPException(422,detail='DECISION_REQUIRED')
    from uuid import uuid4
    try:
        with pg() as conn:
            with conn.transaction():
                row=_proposal(conn,who,proposal_id,lock=True)
                if row['status']!='DRAFT':
                    prior=conn.execute('''SELECT decision,reason,command_id FROM version_b_rc2.decisions
                      WHERE tenant_id=%s AND run_id=%s AND idempotency_key=%s''',
                      (who.tenant,row['run_id'],body.idempotency_key)).fetchone()
                    if prior and prior[0]==body.decision and prior[1]==body.reason and row['status']==body.decision:
                        return {'status':row['status'],'command_id':str(prior[2]),'idempotent_replay':True,'external_execution':False}
                    raise HTTPException(409,detail='PROPOSAL_ALREADY_REVIEWED')
                state,version=_workflow(conn,who,row['run_id'],lock=True)
                if state!='WAITING_REVIEW':raise HTTPException(409,detail='PLAN_NOT_REVIEWABLE')
                snapshot,run=_persisted_snapshot(conn,who,row['run_id'])
                if run['input_hash']!=row['input_hash']:
                    raise HTTPException(409,detail='PROPOSAL_BASELINE_CHANGED')
                change=row['change']
                verified=what_if(snapshot,Change(change['kind'],change['target'],change.get('quantity'),change.get('date')))
                if verified['candidate_snapshot_sha256']!=row['candidate_hash']:
                    raise HTTPException(409,detail='PROPOSAL_RECOMPUTE_MISMATCH')
                command_id=uuid4()
                conn.execute('''INSERT INTO version_b_rc2.decisions
                   (tenant_id,run_id,actor_id,idempotency_key,decision,reason,command_id)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                   (who.tenant,row['run_id'],who.actor,body.idempotency_key,body.decision,body.reason,command_id))
                new='APPROVED_QUEUED' if body.decision=='APPROVED' else 'REJECTED'
                conn.execute('''UPDATE version_b_rc2.workflow_states SET status=%s,
                   version=version+1,updated_at=now() WHERE tenant_id=%s AND run_id=%s''',
                   (new,who.tenant,row['run_id']))
                if body.decision=='APPROVED':
                    conn.execute('''INSERT INTO version_b_rc2.outbox(command_id,tenant_id,run_id,payload,status)
                       VALUES(%s,%s,%s,%s::jsonb,'PENDING')''',
                       (command_id,who.tenant,row['run_id'],json.dumps({'action':'VALIDATE_APPROVED_MRP',
                        'actor':who.actor,'proposal_id':str(proposal_id),'candidate_hash':row['candidate_hash'],
                        'external_execution':False})))
                conn.execute('''UPDATE version_b_rc2.proposals SET status=%s,command_id=%s,
                   updated_at=now() WHERE tenant_id=%s AND proposal_id=%s''',
                   (body.decision,command_id,who.tenant,proposal_id))
                conn.execute('''INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
                   VALUES(%s,%s,%s,%s,%s::jsonb)''',
                   (who.tenant,who.actor,'PROPOSAL_'+body.decision,str(proposal_id),json.dumps({
                    'run_id':row['run_id'],'command_id':str(command_id),'reason':body.reason,
                    'candidate_hash':row['candidate_hash']})))
        return {'status':body.decision,'command_id':str(command_id),
                'execution_status':'PENDING' if body.decision=='APPROVED' else 'NOT_EXECUTED',
                'external_execution':False,'proposal_id':str(proposal_id)}
    except HTTPException:raise
    except PolicyRejected as exc:raise HTTPException(422,detail=str(exc)) from None
    except Exception:raise HTTPException(503,detail='PROPOSAL_REVIEW_UNAVAILABLE') from None

@router.post('/proposals/{proposal_id}/compensation-request',status_code=202)
def request_compensation(proposal_id:__import__('uuid').UUID,body:ProposalAction,
                         who:Identity=Depends(identity)):
    """Record an internal compensation *request*, never pretend to reverse an external action."""
    require(who,{'approver','admin'})
    try:
        with pg() as conn:
            with conn.transaction():
                row=_proposal(conn,who,proposal_id,lock=True)
                if row['status']=='COMPENSATION_REQUESTED':
                    return {'status':'COMPENSATION_REQUESTED','idempotent_replay':True}
                if row['status']!='APPROVED' or row['command_id'] is None:
                    raise HTTPException(409,detail='PROPOSAL_NOT_APPROVED')
                command=_command(conn,who,row['command_id'])
                if command['status']!='DONE':raise HTTPException(409,detail='EXECUTION_NOT_FINISHED')
                conn.execute('''UPDATE version_b_rc2.proposals SET status='COMPENSATION_REQUESTED',
                  updated_at=now() WHERE tenant_id=%s AND proposal_id=%s''',(who.tenant,proposal_id))
                conn.execute('''INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
                  VALUES(%s,%s,'COMPENSATION_REQUESTED',%s,%s::jsonb)''',
                  (who.tenant,who.actor,str(proposal_id),json.dumps({'run_id':row['run_id'],
                   'command_id':str(row['command_id']),'reason':body.reason,'external_effect':'NONE'})))
        return {'status':'COMPENSATION_REQUESTED','effect':'AUDIT_REQUEST_ONLY',
                'external_execution':False}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='COMPENSATION_REQUEST_UNAVAILABLE') from None


@router.get('/planning/pegging-reconciliation/{run_id}')
def pegging_reconciliation(run_id:str,who:Identity=Depends(identity)):
    """Cross-check every persisted requirement line against persisted order allocations."""
    require(who,{'viewer','planner','approver','operator','admin'})
    from .rc35_pegging import reconcile
    try:
        with pg() as conn:
            snapshot,run=_persisted_snapshot(conn,who,run_id)
        result=reconcile(run['lines'],run['pegs'],snapshot)
        return {'tenant':who.tenant,'run_id':run_id,'source':'PERSISTED_POSTGRESQL',**result}
    except HTTPException:raise
    except (ValueError,KeyError,TypeError):
        raise HTTPException(409,detail='PEGGING_RECONCILIATION_INVALID') from None
    except Exception:
        raise HTTPException(503,detail='PEGGING_RECONCILIATION_UNAVAILABLE') from None


class BatchReviewRequest(BaseModel):
    proposal_ids:list[__import__('uuid').UUID]=Field(min_length=1,max_length=30)
    decision:Literal['APPROVED','REJECTED']
    reason:str=Field(min_length=3,max_length=1000)
    idempotency_key:str=Field(min_length=8,max_length=128)

@router.post('/proposals/batch-review')
def batch_review(body:BatchReviewRequest,who:Identity=Depends(identity)):
    """Explicitly non-atomic per-item decisions. Report partial success honestly.

    Each review uses its own existing transaction and row locks; failed items
    never roll back successful items or masquerade as a full batch success.
    """
    require(who,{'approver','admin'})
    if len(set(body.proposal_ids))!=len(body.proposal_ids):
        raise HTTPException(422,detail='DUPLICATE_PROPOSAL_IDS')
    outcomes=[]
    for proposal_id in body.proposal_ids:
        stable_key=fingerprint({'batch':body.idempotency_key,'proposal_id':str(proposal_id)})
        try:
            result=review_proposal(proposal_id,ProposalAction(idempotency_key=stable_key,reason=body.reason,decision=body.decision),who)
            outcomes.append({'proposal_id':str(proposal_id),'status':'SUCCESS','decision':result['status'],'command_id':result.get('command_id')})
        except HTTPException as exc:
            outcomes.append({'proposal_id':str(proposal_id),'status':'FAILED','http_status':exc.status_code,'reason':exc.detail})
    return {'batch_mode':'PER_ITEM_TRANSACTION','requested':len(outcomes),
        'succeeded':sum(x['status']=='SUCCESS' for x in outcomes),
        'failed':sum(x['status']=='FAILED' for x in outcomes), 'results':outcomes,
        'external_execution':False}

class CompensationReview(BaseModel):
    decision:Literal['CLOSED_NO_EXTERNAL_EFFECT','REJECTED']
    reason:str=Field(min_length=3,max_length=1000)

@router.post('/proposals/{proposal_id}/compensation-review')
def compensation_review(proposal_id:__import__('uuid').UUID,body:CompensationReview,
                        who:Identity=Depends(identity)):
    """Close an INTERNAL-only compensation review with immutable audit evidence.

    No inventory, purchase, production or external downstream action is undone.
    """
    require(who,{'approver','admin'})
    target='COMPENSATION_CLOSED' if body.decision=='CLOSED_NO_EXTERNAL_EFFECT' else 'COMPENSATION_REJECTED'
    try:
        with pg() as conn:
            with conn.transaction():
                row=_proposal(conn,who,proposal_id,lock=True)
                if row['status']==target:
                    return {'status':target,'idempotent_replay':True,'external_execution':False}
                if row['status']!='COMPENSATION_REQUESTED':
                    raise HTTPException(409,detail='COMPENSATION_REVIEW_NOT_PENDING')
                conn.execute('''UPDATE version_b_rc2.proposals SET status=%s,updated_at=now()
                   WHERE tenant_id=%s AND proposal_id=%s''',(target,who.tenant,proposal_id))
                conn.execute('''INSERT INTO version_b_rc2.audit(tenant_id,actor_id,action,ref_id,details)
                   VALUES(%s,%s,%s,%s,%s::jsonb)''',(who.tenant,who.actor,target,str(proposal_id),
                    json.dumps({'run_id':row['run_id'],'command_id':str(row['command_id']),
                     'reason':body.reason,'external_effect':'NONE','inventory_reversed':False})))
        return {'status':target,'effect':'INTERNAL_REVIEW_ONLY','external_execution':False,
                'inventory_reversed':False}
    except HTTPException:raise
    except Exception:raise HTTPException(503,detail='COMPENSATION_REVIEW_UNAVAILABLE') from None
