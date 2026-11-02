"""MCP 2024-11-05 JSON-RPC stdio transport for a trusted local host.

One JSON object per line on stdin/stdout. Stdout is protocol-only. Never accept a
caller-supplied token, database URL or release switch from tool arguments.
"""
import json
import os
import sys
import time
import uuid
from .full_gateway import FullGateway, SPECS, Rejected
from .idempotency import invoke_once, RequestConflict

PROTOCOL='2024-11-05'
SCHEMAS={
 'mrp.get_run': {'run_id':{'type':'string','minLength':1,'maxLength':128}},
 'wms.get_inventory': {'material_id':{'type':'string','minLength':1,'maxLength':128},'warehouse_id':{'type':'string','minLength':1,'maxLength':128}},
 'mes.get_work_order': {'work_order_id':{'type':'string','minLength':1,'maxLength':128}},
 'srm.list_requisitions': {'run_id':{'type':'string','minLength':1,'maxLength':128},'limit':{'type':'integer','minimum':1,'maximum':100}},
 'mapping.preview_b01': {'run_id':{'type':'string','minLength':1,'maxLength':128}},
}

def tools_list():
    return [{'name':name,'description':'Authorized read-only industrial '+name,
      'inputSchema':{'type':'object','properties':props,
        'required':[SPECS[name][1]],'additionalProperties':False}}
        for name,props in SCHEMAS.items()]

def error(code,message,ident=None):
    return {'jsonrpc':'2.0','id':ident,'error':{'code':code,'message':message}}

class ProtocolServer:
    def __init__(self,invoke,enabled=False):
        self.invoke=invoke
        self.enabled=bool(enabled)
        self.initialized=False
        self.session_id=uuid.uuid4().hex
    def handle(self,message):
        if not isinstance(message,dict) or message.get('jsonrpc')!='2.0': return error(-32600,'Invalid Request')
        ident=message.get('id')
        method=message.get('method')
        if not isinstance(method,str): return error(-32600,'Invalid Request',ident)
        # Notifications have no id and MUST NOT produce JSON-RPC responses.
        if 'id' not in message:
            if method=='notifications/initialized': self.initialized=True
            return None
        if type(ident) not in (str,int): return error(-32600,'Invalid Request',None)
        params=message.get('params',{})
        if not isinstance(params,dict): return error(-32602,'Invalid params',ident)
        if method=='initialize':
            requested=params.get('protocolVersion')
            if requested not in (None,PROTOCOL): return error(-32602,'Unsupported protocol version',ident)
            return {'jsonrpc':'2.0','id':ident,'result':{'protocolVersion':PROTOCOL,
                'capabilities':{'tools':{'listChanged':False}},
                'serverInfo':{'name':'industrial-ai-paas-lab','version':'1.5.0'}}}
        if not self.initialized: return error(-32000,'Initialize handshake required',ident)
        if method=='ping': return {'jsonrpc':'2.0','id':ident,'result':{}}
        if method=='tools/list': return {'jsonrpc':'2.0','id':ident,'result':{'tools':tools_list()}}
        if method=='tools/call':
            name=params.get('name'); args=params.get('arguments',{})
            if name not in SPECS: return error(-32602,'Unknown tool',ident)
            if not isinstance(args,dict): return error(-32602,'Arguments must be object',ident)
            if not self.enabled: return error(-32003,'Release gate disabled',ident)
            try:
                # MCP request IDs are scoped to the authenticated host identity by ledger.
                response=self.invoke(name,args,self.session_id+":"+str(ident))
                return {'jsonrpc':'2.0','id':ident,'result':{'content':[
                    {'type':'text','text':json.dumps(response,ensure_ascii=False,default=str)}],
                    'isError':response.get('status')!='COMPLETED'}}
            except (Rejected,RequestConflict,ValueError) as exc:
                return error(-32602,str(exc),ident)
            except Exception:
                # Never print credentials, SQL details or exception traces to MCP stdout.
                return error(-32603,'Internal tool failure; consult server audit',ident)
        return error(-32601,'Method not found',ident)

def serve(stdin,stdout,server,max_bytes=1048576):
    for line in stdin:
        if len(line.encode('utf8'))>max_bytes:
            stdout.write(json.dumps(error(-32600,'Message too large'))+'\n'); stdout.flush(); continue
        try: response=server.handle(json.loads(line))
        except (ValueError,UnicodeError): response=error(-32700,'Parse error')
        if response is not None:
            stdout.write(json.dumps(response,ensure_ascii=False,default=str,separators=(',',':'))+'\n')
            stdout.flush()

def main():
    import psycopg
    # Explicit test-only gate; never enable from client parameters.
    enabled=os.getenv('V15_TEST_MCP_ENABLE')=='I_ACKNOWLEDGE_TEST_ONLY'
    secret=os.environ['V15_MCP_HMAC_SECRET']
    token=os.environ['V15_MCP_HOST_TOKEN']
    if len(secret)<32: raise RuntimeError('MCP_SECRET_TOO_SHORT')
    runtime_dsn=os.environ['M1_TEST_DATABASE_URL']; business_dsn=os.environ['V15_BUSINESS_DATABASE_URL']
    def invoke(name,args,request_id):
        with psycopg.connect(runtime_dsn,autocommit=True) as runtime,psycopg.connect(business_dsn,autocommit=True) as business:
            if runtime.execute('SELECT current_database()').fetchone()[0]!='industrial_lab_v15_test': raise RuntimeError('SECURITY_DB_MISMATCH')
            if business.execute('SELECT current_database()').fetchone()[0]!='industrial_lab_v14_test': raise RuntimeError('BUSINESS_DB_MISMATCH')
            gateway=FullGateway(secret,release_enabled=enabled)
            return invoke_once(runtime,business,gateway,token,name,args,request_id)
    serve(sys.stdin,sys.stdout,ProtocolServer(invoke,enabled=enabled))

if __name__=='__main__': main()
