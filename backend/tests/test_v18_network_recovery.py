import json
import threading
import urllib.error
import urllib.request
import pytest
from app.mcp_v18.http_transport import MCPHTTPServer
from app.mcp_v18.recovery import decide

@pytest.fixture
def server():
    calls=[]
    srv=MCPHTTPServer(('127.0.0.1',0),lambda *args:calls.append(args) or {'status':'COMPLETED'},'x'*40)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    yield srv,calls
    srv.shutdown();srv.server_close();thread.join(timeout=2)

def send(s,msg=None,*,session=None,token='x'*40,origin=None,method='POST'):
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'}
    if session: headers['Mcp-Session-Id']=session
    if origin: headers['Origin']=origin
    data=json.dumps(msg).encode() if msg is not None else None
    request=urllib.request.Request(f'http://127.0.0.1:{s.server_port}/mcp',data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,timeout=3) as response:
            raw=response.read()
            return response.status,dict(response.headers),json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw=exc.read()
        return exc.code,dict(exc.headers),json.loads(raw) if raw else None

def init(s):
    status,headers,result=send(s,{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}})
    assert status==200 and 'result' in result
    return headers['Mcp-Session-Id']

def test_loopback_and_token():
    with pytest.raises(ValueError,match='LOOPBACK_ONLY'):
        MCPHTTPServer(('0.0.0.0',0),lambda *args:None,'x'*40)
    with pytest.raises(ValueError,match='TOKEN_REQUIRED'):
        MCPHTTPServer(('127.0.0.1',0),lambda *args:None,'short')

def test_origin_auth_and_no_session(server):
    s,calls=server
    msg={'jsonrpc':'2.0','id':1,'method':'initialize','params':{}}
    assert send(s,msg,origin='https://evil.example')[0]==403
    assert send(s,msg,token='wrong')[0]==401
    assert send(s,{'jsonrpc':'2.0','id':2,'method':'tools/list'})[0]==404
    assert not calls

def test_session_handshake_and_tool_default_deny(server):
    s,calls=server
    sid=init(s)
    assert send(s,{'jsonrpc':'2.0','method':'notifications/initialized'},session=sid)[0]==202
    code,_,result=send(s,{'jsonrpc':'2.0','id':2,'method':'tools/list'},session=sid)
    assert code==200 and result['result']['tools']
    code,_,result=send(s,{'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'mrp.get_run','arguments':{'run_id':'R'}}},session=sid)
    assert code==200 and result['error']['code']==-32003 and not calls
    assert send(s,session=sid,method='DELETE')[0]==204
    assert send(s,{'jsonrpc':'2.0','id':4,'method':'ping'},session=sid)[0]==404

def test_session_isolation(server):
    s,_=server
    a=init(s);b=init(s)
    assert a!=b
    assert send(s,{'jsonrpc':'2.0','id':2,'method':'ping'},session=a)[2]['error']['code']==-32000
    send(s,{'jsonrpc':'2.0','method':'notifications/initialized'},session=a)
    assert 'result' in send(s,{'jsonrpc':'2.0','id':3,'method':'ping'},session=a)[2]
    assert send(s,{'jsonrpc':'2.0','id':4,'method':'ping'},session=b)[2]['error']['code']==-32000

def test_recovery_fail_closed():
    assert decide('DONE',10,persisted_result=True).action=='RETURN_CACHED'
    assert decide('DONE',10).action=='MANUAL_REVIEW'
    assert decide('IN_PROGRESS',20).action=='WAIT'
    assert decide('IN_PROGRESS',400,idempotent=True).action=='MANUAL_REVIEW'
    assert decide('FAILED',400,idempotent=True).action=='MANUAL_REVIEW'
    assert decide('UNKNOWN',400).action=='MANUAL_REVIEW'
    assert decide('DONE',-1,persisted_result=True).action=='MANUAL_REVIEW'
