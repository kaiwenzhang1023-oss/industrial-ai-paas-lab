import io
import json
import pytest
from app.mcp_v17.transport import HardenedProtocolServer, serve


def msg(method, ident=1, params=None):
    return {'jsonrpc':'2.0', 'id':ident, 'method':method, 'params':params or {}}


def ready(enabled=False):
    calls=[]
    s=HardenedProtocolServer(lambda n,a,k: (calls.append((n,a,k)) or {'status':'COMPLETED'}), enabled=enabled)
    assert 'result' in s.handle(msg('initialize',params={'protocolVersion':'2024-11-05'}))
    assert s.handle({'jsonrpc':'2.0','method':'notifications/initialized'}) is None
    return s,calls


def test_closed_by_default():
    s,calls=ready()
    result=s.handle(msg('tools/call',params={'name':'mrp.get_run','arguments':{'run_id':'R'}}))
    assert result['error']['code']==-32003 and not calls

@pytest.mark.parametrize('args',[{}, {'run_id':3}, {'run_id':'R','extra':'x'}, {'run_id':''}, {'run_id':'R','limit':1}])
def test_invalid_arguments_never_reach_adapter(args):
    s,calls=ready(True)
    result=s.handle(msg('tools/call',params={'name':'mrp.get_run','arguments':args}))
    assert result['error']['code']==-32602 and not calls


def test_valid_dispatch_and_idempotency_key():
    s,calls=ready(True)
    result=s.handle(msg('tools/call',ident='abc',params={'name':'mrp.get_run','arguments':{'run_id':'R'}}))
    assert result['result']['isError'] is False
    assert calls[0][2].endswith(':abc')


def test_initialize_required_and_duplicate_rejected():
    s=HardenedProtocolServer(lambda *a: {},enabled=False)
    assert s.handle(msg('tools/list'))['error']['code']==-32000
    assert s.handle({'jsonrpc':'2.0','method':'notifications/initialized'}) is None
    assert s.handle(msg('tools/list'))['error']['code']==-32000
    assert 'result' in s.handle(msg('initialize'))
    assert s.handle(msg('initialize'))['error']['code']==-32600


def test_protocol_stdout_only_json():
    s,_=ready()
    out=io.StringIO()
    serve(io.StringIO(json.dumps(msg('tools/list'))+'\n'),out,s)
    parsed=json.loads(out.getvalue())
    assert len(parsed['result']['tools'])==5
