"""Version B tenant-isolated MCP tool handlers; read-only domain, durable audit.

MCP stdio transport is implemented in mcp_stdio.py. The HTTP RPC facade and
stdio share this allowlist and enforce the authenticated host identity.
"""
from __future__ import annotations
import hashlib
import json
import uuid
from dataclasses import dataclass
from fastapi import HTTPException
from app.db.repository import read_run

PROTOCOL='2024-11-05'
SCHEMAS={
 'mrp.get_run':{'run_id':{'type':'string','minLength':1,'maxLength':128}},
 'workflow.get_command':{'command_id':{'type':'string','format':'uuid'}},
 'reconciliation.get':{'idempotency_key':{'type':'string','minLength':8,'maxLength':128}},
}

def tools_list():
    return [{'name':name,'description':'Version B tenant-scoped read-only '+name,
             'inputSchema':{'type':'object','properties':props,
                            'required':list(props),'additionalProperties':False}}
            for name,props in SCHEMAS.items()]

def _args(tool,args):
    if tool not in SCHEMAS:raise HTTPException(422,detail='MCP_TOOL_NOT_ALLOWLISTED')
    if not isinstance(args,dict) or set(args)!=set(SCHEMAS[tool]):
        raise HTTPException(422,detail='MCP_INVALID_ARGUMENTS')
    for key in SCHEMAS[tool]:
        val=args[key]
        if not isinstance(val,str) or not val or len(val)>128 or len(val)<(8 if key=='idempotency_key' else 1):
            raise HTTPException(422,detail='MCP_INVALID_ARGUMENTS')
    if tool=='workflow.get_command':
        try: uuid.UUID(args['command_id'])
        except ValueError: raise HTTPException(422,detail='MCP_INVALID_COMMAND_ID')


def invoke(conn, identity, tool, args, request_id=''):
    _args(tool,args)
    tenant=identity.tenant
    if tool=='mrp.get_run':
        run_id=args['run_id']
        if conn.execute('''SELECT 1 FROM version_b_rc2.run_tenants
                   WHERE tenant_id=%s AND run_id=%s''',(tenant,run_id)).fetchone() is None:
            raise HTTPException(404,detail='RUN_NOT_FOUND')
        data=read_run(conn,run_id)
    elif tool=='workflow.get_command':
        from enterprise_workbench.rc2 import _command
        data=_command(conn,identity,uuid.UUID(args['command_id']))
    else:
        row=conn.execute('''SELECT payload FROM version_b_rc2.reconciliation
                           WHERE tenant_id=%s AND idempotency_key=%s''',
                         (tenant,args['idempotency_key'])).fetchone()
        if not row:raise HTTPException(404,detail='RECONCILIATION_NOT_FOUND')
        data=row[0]
    # Audit only allowed, successful local data reads. No raw args, tokens or DSNs.
    h=hashlib.sha256(json.dumps(args,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    conn.execute('''INSERT INTO version_b_rc2.mcp_call_audit
         (tenant_id,actor_id,tool_name,arguments_sha256,request_id,outcome)
         VALUES(%s,%s,%s,%s,%s,'READ_SUCCESS')''',
         (tenant,identity.actor,tool,h,str(request_id)[:128]))
    return {'tool':tool,'result':data,'read_only':True,'external_effect':'NONE',
            'tenant':tenant,'audit':'PERSISTED_POSTGRESQL'}


def rpc_response(message, invoke_fn):
    """Shared MCP JSON-RPC request parser; returns None for notifications."""
    def err(id,code,reason):return {'jsonrpc':'2.0','id':id,'error':{'code':code,'message':reason}}
    if not isinstance(message,dict) or message.get('jsonrpc')!='2.0':
        return err(None,-32600,'Invalid Request')
    ident=message.get('id')
    method=message.get('method')
    if not isinstance(method,str):return err(ident,-32600,'Invalid Request')
    if 'id' not in message:return None
    if type(ident) not in (int,str):return err(None,-32600,'Invalid Request')
    params=message.get('params',{})
    if not isinstance(params,dict):return err(ident,-32602,'Invalid params')
    if method=='initialize':
        if params.get('protocolVersion',PROTOCOL)!=PROTOCOL:return err(ident,-32602,'Unsupported protocol version')
        return {'jsonrpc':'2.0','id':ident,'result':{'protocolVersion':PROTOCOL,
                'capabilities':{'tools':{'listChanged':False}},
                'serverInfo':{'name':'industrial-version-b-rc3','version':'0.3.0'}}}
    if method=='ping':result={}
    elif method=='tools/list':result={'tools':tools_list()}
    elif method=='tools/call':
        name=params.get('name');args=params.get('arguments',{})
        if name not in SCHEMAS:return err(ident,-32602,'Unknown tool')
        try:
            payload=invoke_fn(name,args,str(ident))
        except HTTPException as exc:
            return err(ident,(-32004 if exc.status_code==404 else -32603 if exc.status_code>=500 else -32602),
                       ('Tool backend unavailable' if exc.status_code>=500 else str(exc.detail)))
        except Exception:
            return err(ident,-32603,'Tool backend unavailable')
        result={'content':[{'type':'text','text':json.dumps(payload,ensure_ascii=False,default=str)}],
                'isError':False}
    else:return err(ident,-32601,'Method not found')
    return {'jsonrpc':'2.0','id':ident,'result':result}
