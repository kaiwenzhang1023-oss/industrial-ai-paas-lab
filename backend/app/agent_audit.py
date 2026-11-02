"""Append-only PostgreSQL governance events; never persist raw tool inputs/results."""
from __future__ import annotations
from app.agent import canonical_hash
from app.agent_policy import POLICY_VERSION

ALLOWED_OUTCOMES = frozenset({'ALLOWED','DENIED','ERROR'})

def record_tool_decision(conn, *, workflow_id, principal, tool, outcome, reason, args=None, result=None, trace_id=''):
    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError('AUDIT_OUTCOME_INVALID')
    if conn.info.transaction_status.name != 'IDLE':
        raise RuntimeError('AUDIT_REQUIRES_IDLE_CONNECTION')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO platform.agent_tool_audit
                (workflow_id,trace_id,principal,tool_name,policy_version,outcome,reason_code,args_hash,result_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (workflow_id,trace_id,principal,tool,POLICY_VERSION,outcome,reason,
                 canonical_hash(args) if args is not None else None,
                 canonical_hash(result) if result is not None else None))
