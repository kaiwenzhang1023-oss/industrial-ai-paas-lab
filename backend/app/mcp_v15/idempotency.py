"""Persistent request ledger through narrow SECURITY DEFINER database APIs.

The runtime role has EXECUTE only; it never receives direct table DML rights.
A stale/ambiguous call is UNKNOWN and is never automatically re-executed.
"""
import hashlib
import json

class RequestConflict(ValueError): pass


def _hash(tenant, principal, tool, args):
    raw=json.dumps([tenant,principal,tool,args],sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def claim(conn, tenant, principal, request_id, tool, args):
    """Return ('NEW', None), ('DONE', response), or ('IN_PROGRESS', None)."""
    if not isinstance(request_id,str) or not 1<=len(request_id)<=128:
        raise RequestConflict('INVALID_REQUEST_ID')
    digest=_hash(tenant,principal,tool,args)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute('SET LOCAL ROLE mcp_v15_runtime_test')
                cur.execute('SELECT action,response_json FROM mcp_v15.ledger_claim(%s,%s,%s,%s,%s)',
                            (tenant,principal,request_id,tool,digest))
                row=cur.fetchone()
                if row is None: raise RuntimeError('LEDGER_CLAIM_EMPTY')
                return row[0],row[1]
    except Exception as exc:
        if getattr(exc,'sqlstate',None)=='23505' and 'REQUEST_ID_CONFLICT' in str(exc):
            raise RequestConflict('REQUEST_ID_CONFLICT') from None
        raise


def finish(conn,tenant,principal,request_id,tool,args,response):
    """Persist response before releasing it to the MCP client; failures fail closed."""
    payload=json.dumps(response,ensure_ascii=False,allow_nan=False,default=str)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE mcp_v15_runtime_test')
            cur.execute('SELECT mcp_v15.ledger_finish(%s,%s,%s,%s,%s,%s::jsonb)',
                        (tenant,principal,request_id,tool,_hash(tenant,principal,tool,args),payload))
            if cur.fetchone()[0] is not True: raise RuntimeError('LEDGER_FINISH_FAILED')


def invoke_once(runtime,business,gateway,token,tool,args,request_id):
    from .full_gateway import verify_token
    identity=verify_token(gateway._secret,token,gateway._clock())
    state,cached=claim(runtime,identity.tenant,identity.principal,request_id,tool,args)
    if state=='DONE': return cached
    if state in ('IN_PROGRESS','UNKNOWN'): return {'status':'UNKNOWN','error_code':'REQUEST_ALREADY_IN_PROGRESS' if state=='IN_PROGRESS' else 'REQUEST_OUTCOME_UNKNOWN'}
    # If execution succeeds but finish fails, retry is UNKNOWN, never a second execution.
    response=gateway.invoke(runtime,business,token,tool,args)
    finish(runtime,identity.tenant,identity.principal,request_id,tool,args,response)
    return response
