"""M1-03: isolated PostgreSQL execution ledger; never writes SRM/MRP/MES/Workflow.

Caller supplies a psycopg connection and a trusted, already validated MRP snapshot.
Do not use this as an authentication or source-attestation boundary.
"""
from collections.abc import Mapping
from .contracts import B01_MAPPING_ID, B01_VERSION, PUBLISHED
from .engine import preview_b01
from .fingerprints import sha256
from .errors import MappingFailure
import json
from .fingerprints import canonical

def _jsonb(value):
    from psycopg.types.json import Jsonb
    return Jsonb(value)


def _ensure_version(cur):
    rules = [{k: v for k, v in rule.items()} for rule in PUBLISHED[B01_VERSION]]
    rules_hash = sha256(rules)
    cur.execute("""INSERT INTO mapping_v14.mapping_versions
        (mapping_id,mapping_version,status,rules_hash)
        VALUES (%s,%s,'PUBLISHED',%s) ON CONFLICT DO NOTHING""",
        (B01_MAPPING_ID, B01_VERSION, rules_hash))
    cur.execute("""SELECT status,rules_hash FROM mapping_v14.mapping_versions
        WHERE mapping_id=%s AND mapping_version=%s""",(B01_MAPPING_ID,B01_VERSION))
    if cur.fetchone() != ('PUBLISHED',rules_hash):
        raise MappingFailure('MAPPING_VERSION_NOT_PUBLISHED','mapping_version','Frozen rules mismatch')


def _existing(cur, execution_id, request_hash):
    cur.execute("""SELECT request_hash,response_json FROM mapping_v14.execution_runs
        WHERE execution_id=%s""",(execution_id,))
    found = cur.fetchone()
    if found is None: return None
    if found[0] != request_hash:
        raise MappingFailure('EXECUTION_IDEMPOTENCY_CONFLICT','execution_id',
                             'Execution ID already used for different input')
    return found[1]


def execute_preview(conn, execution_id, request):
    """Durable idempotent execution. Entire mapping_v14 transaction is atomic.

    Requires a transaction-idle connection; request must be JSON-serializable.
    Advisory transaction lock serializes concurrent attempts with the same key.
    """
    if not isinstance(execution_id,str) or not execution_id.strip():
        raise MappingFailure('REQUIRED_FIELD_MISSING','execution_id','Nonempty execution ID required')
    if not isinstance(request,Mapping):
        raise MappingFailure('SOURCE_SCHEMA_INVALID','request','Expected request object')
    request = json.loads(canonical(dict(request)))
    request_hash = sha256(request)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (execution_id,))
            existing = _existing(cur,execution_id,request_hash)
            if existing is not None: return {'response':existing,'idempotent':True}
            _ensure_version(cur)
            response = preview_b01(request)
            cur.execute("""INSERT INTO mapping_v14.execution_runs
                (execution_id,mapping_id,mapping_version,request_hash,request_json,response_json,result_hash,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (execution_id,B01_MAPPING_ID,B01_VERSION,request_hash,_jsonb(request),
                 _jsonb(response),response['mapping_result_hash'],response['status']))
            for i,err in enumerate(response['errors']):
                cur.execute("""INSERT INTO mapping_v14.execution_errors
                    (execution_id,error_index,error_json) VALUES (%s,%s,%s)""",
                    (execution_id,i,_jsonb(err)))
            cur.execute("""INSERT INTO mapping_v14.audit_events(execution_id,action,payload)
                VALUES (%s,'EXECUTE',%s)""",
                (execution_id,_jsonb({'request_hash':request_hash,
                    'result_hash':response['mapping_result_hash'],'status':response['status']})))
    return {'response':response,'idempotent':False}


def replay_preview(conn, execution_id):
    """Read immutable stored request and recompute; reject drift; audit replay only."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(execution_id,))
            cur.execute("""SELECT request_hash,request_json,response_json FROM mapping_v14.execution_runs
                WHERE execution_id=%s""",(execution_id,))
            row=cur.fetchone()
            if row is None: raise MappingFailure('REQUIRED_FIELD_MISSING','execution_id','Unknown execution')
            request_hash, request, recorded = row
            if sha256(request) != request_hash:
                raise MappingFailure('SOURCE_FINGERPRINT_MISMATCH','request_json','Stored request corrupted')
            current = preview_b01(request)
            if sha256(current) != sha256(recorded):
                raise MappingFailure('SOURCE_FINGERPRINT_MISMATCH','response_json','Historical replay drift')
            cur.execute("""INSERT INTO mapping_v14.audit_events(execution_id,action,payload)
                VALUES (%s,'REPLAY',%s)""",
                (execution_id,_jsonb({'request_hash':request_hash,
                    'result_hash':current['mapping_result_hash']})))
    return {'response':current,'replay_match':True}


def list_public_executions(conn,limit=100):
    if not isinstance(limit,int) or not 1<=limit<=100: raise ValueError('INVALID_LIMIT')
    with conn.cursor() as cur:
        cur.execute("""SELECT execution_id,mapping_id,mapping_version,status,result_hash,created_at
            FROM mapping_v14.public_executions ORDER BY created_at DESC,execution_id LIMIT %s""",(limit,))
        return [dict(zip(('execution_id','mapping_id','mapping_version','status','result_hash','created_at'),row))
                for row in cur.fetchall()]
