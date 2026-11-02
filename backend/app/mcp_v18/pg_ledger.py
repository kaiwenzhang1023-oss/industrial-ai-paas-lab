"""Opt-in PostgreSQL idempotency control ledger. Never auto-replays uncertain effects.

Requires a separately provisioned database/schema and restricted role. This module
never applies migrations or connects to Neon/production automatically.
"""
import json
import time
from .durable_ledger import DurableLedger, LedgerConflict

DDL = """
CREATE TABLE IF NOT EXISTS mcp_v18_calls (
 tenant text NOT NULL, principal text NOT NULL, request_key text NOT NULL,
 fingerprint text NOT NULL, state text NOT NULL CHECK (state IN ('IN_PROGRESS','DONE')),
 result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant,principal,request_key));
CREATE TABLE IF NOT EXISTS mcp_v18_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant text NOT NULL, principal text NOT NULL, request_key text NOT NULL,
 event text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now());
"""

class PostgresLedger:
    """Caller owns psycopg connection factory; operations commit atomically."""
    def __init__(self, connection_factory):
        if not callable(connection_factory): raise TypeError('connection_factory required')
        self.connect=connection_factory

    @staticmethod
    def _validate(tenant,principal,key,tool):
        if not all(isinstance(x,str) and x and len(x)<=256 for x in (tenant,principal,key,tool)):
            raise ValueError('INVALID_IDENTITY_OR_KEY')

    def claim(self,tenant,principal,key,tool,arguments):
        self._validate(tenant,principal,key,tool)
        digest=DurableLedger.fingerprint(tool,arguments)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO mcp_v18_calls(tenant,principal,request_key,fingerprint,state)
                    VALUES (%s,%s,%s,%s,'IN_PROGRESS') ON CONFLICT DO NOTHING
                    RETURNING fingerprint""",(tenant,principal,key,digest))
                inserted=cur.fetchone() is not None
                if inserted:
                    action='EXECUTE_ONCE'; result=None
                else:
                    cur.execute("""SELECT fingerprint,state,result FROM mcp_v18_calls
                        WHERE tenant=%s AND principal=%s AND request_key=%s FOR UPDATE""",(tenant,principal,key))
                    row=cur.fetchone()
                    if row is None: raise RuntimeError('MISSING_CLAIM')
                    if row[0]!=digest:
                        cur.execute("""INSERT INTO mcp_v18_events(tenant,principal,request_key,event)
                            VALUES (%s,%s,%s,'CONFLICT_DENIED')""",(tenant,principal,key))
                        action='CONFLICT_DENIED'; result=None
                    else:
                        action='RETURN_CACHED' if row[1]=='DONE' and row[2] is not None else 'DO_NOT_REPLAY'
                        result=row[2] if action=='RETURN_CACHED' else None
                if action!='CONFLICT_DENIED':
                    cur.execute("""INSERT INTO mcp_v18_events(tenant,principal,request_key,event)
                        VALUES (%s,%s,%s,%s)""",(tenant,principal,key,'CLAIMED' if inserted else action))
        if action=='CONFLICT_DENIED': raise LedgerConflict('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD')
        return {'action':action,'result':result}

    def complete(self,tenant,principal,key,tool,arguments,result):
        self._validate(tenant,principal,key,tool)
        digest=DurableLedger.fingerprint(tool,arguments)
        payload=json.dumps(result,sort_keys=True,allow_nan=False)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT fingerprint,state,result FROM mcp_v18_calls
                    WHERE tenant=%s AND principal=%s AND request_key=%s FOR UPDATE""",(tenant,principal,key))
                row=cur.fetchone()
                if row is None or row[0]!=digest: raise LedgerConflict('MISSING_OR_MISMATCHED_CLAIM')
                if row[1]=='DONE':
                    if row[2]!=result: raise LedgerConflict('RESULT_MISMATCH')
                    return
                if row[1]!='IN_PROGRESS': raise LedgerConflict('INVALID_STATE')
                cur.execute("""UPDATE mcp_v18_calls SET state='DONE',result=%s::jsonb,updated_at=now()
                    WHERE tenant=%s AND principal=%s AND request_key=%s""",(payload,tenant,principal,key))
                cur.execute("""INSERT INTO mcp_v18_events(tenant,principal,request_key,event)
                    VALUES (%s,%s,%s,'RESULT_COMMITTED')""",(tenant,principal,key))

    def inspect(self,tenant,principal,key,*,timeout=300):
        from .recovery import decide
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT state,result,EXTRACT(EPOCH FROM (now()-updated_at))
                    FROM mcp_v18_calls WHERE tenant=%s AND principal=%s AND request_key=%s""",(tenant,principal,key))
                row=cur.fetchone()
        if row is None: return {'action':'NOT_FOUND'}
        d=decide(row[0],max(0,float(row[2])),timeout=timeout,persisted_result=row[1] is not None)
        return {'action':d.action,'reason':d.reason}
