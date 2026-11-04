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
