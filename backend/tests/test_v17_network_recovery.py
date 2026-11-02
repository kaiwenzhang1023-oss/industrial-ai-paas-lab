import json, threading, urllib.request, urllib.error
import pytest
from app.mcp_v17.http_transport import LocalMCPHTTP
from app.mcp_v17.recovery import classify

@pytest.fixture
def server():
    calls=[]
    s=LocalMCPHTTP(('127.0.0.1',0),lambda *args:calls.append(args) or {'status':'COMPLETED'},'a'*40,enabled=False)
    thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
    yield s,calls
    s.shutdown();s.server_close();thread.join(timeout=2)

def req(s,method='POST',path='/mcp',payload=None,token='a'*40):
    data=json.dumps(payload).encode() if payload is not None else None
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
    return urllib.request.Request('http://127.0.0.1:'+str(s.server_port)+path,data=data,headers=headers,method=method)

def test_local_only():
    with pytest.raises(ValueError,match='LOOPBACK_ONLY'):
        LocalMCPHTTP(('0.0.0.0',0),lambda *x:None,'a'*40)

def test_auth_before_protocol(server):
    s,calls=server
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req(s,token='wrong',payload={'method':'initialize'}))
    assert err.value.code==401 and not calls

def test_disabled_tool_and_handshake(server):
    s,calls=server
    def send(msg):
        with urllib.request.urlopen(req(s,payload=msg)) as res: return json.load(res)
    assert 'result' in send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
    with urllib.request.urlopen(req(s,payload={'jsonrpc':'2.0','method':'notifications/initialized'})) as res: assert res.status==202
    result=send({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'mrp.get_run','arguments':{'run_id':'R'}}})
    assert result['error']['code']==-32003 and not calls

def test_recovery_never_replays():
    assert classify('DONE',400).action=='RETURN_CACHED'
    assert classify('IN_PROGRESS',10).action=='WAIT'
    assert classify('IN_PROGRESS',400).action=='MANUAL_REVIEW'
    assert classify('FAILED',400).action=='MANUAL_REVIEW'
