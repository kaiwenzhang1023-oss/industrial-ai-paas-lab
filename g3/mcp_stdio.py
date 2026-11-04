"""MCP 2024-11-05 JSON-RPC stdio transport, explicit host-bound identity.

Run with PYTHONPATH=backend;. and VERSION_B_RC3_MCP_TOKEN set by a trusted host.
Strictly no auth material is accepted in MCP tool arguments. Stdout protocol only.
"""
import json
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backend'))
from fastapi import HTTPException
from app.db.repository import connect
from enterprise_workbench.rc2 import identity
from g3.mcp import rpc_response,invoke

def serve(infile,outfile):
    token=os.environ.get('VERSION_B_RC3_MCP_TOKEN','')
    try:
        if not token:raise ValueError('HOST_IDENTITY_UNCONFIGURED')
        host=identity('Bearer '+token)
    except (HTTPException,ValueError):
        # Safe stderr message; never echo the token or identity config.
        sys.stderr.write('MCP_HOST_AUTH_UNAVAILABLE\n')
        return 2
    initialized=False
    for line in infile:
        if len(line.encode('utf-8'))>1048576:
            response={'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Message too large'}}
        else:
            try:
                message=json.loads(line)
                if isinstance(message,dict) and message.get('method')=='notifications/initialized' and 'id' not in message:
                    initialized=True;response=None
                elif isinstance(message,dict) and message.get('method') not in ('initialize',) and not initialized:
                    response={'jsonrpc':'2.0','id':message.get('id'),'error':{'code':-32000,'message':'Initialize handshake required'}}
                else:
                    def do_invoke(name,args,rid):
                        with connect() as conn:return invoke(conn,host,name,args,rid)
                    response=rpc_response(message,do_invoke)
            except (UnicodeError,ValueError):
                response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}
        if response is not None:
            outfile.write(json.dumps(response,ensure_ascii=False,separators=(',',':'))+'\n')
            outfile.flush()
    return 0

if __name__=='__main__':raise SystemExit(serve(sys.stdin,sys.stdout))
