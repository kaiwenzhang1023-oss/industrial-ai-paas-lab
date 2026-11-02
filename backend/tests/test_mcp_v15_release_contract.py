"""44 deterministic golden contract cases; real PG16 E2E is a separate mandatory gate."""
import io
import json
import pytest
from app.mcp_v15.stdio_server import ProtocolServer,tools_list,serve
from app.mcp_v15.full_gateway import validate,Rejected,verify_token,issue_test_token
from app.mcp_v15.idempotency import _hash,RequestConflict

TOOLS=['mrp.get_run','wms.get_inventory','mes.get_work_order','srm.list_requisitions','mapping.preview_b01']
VALID=[{'run_id':'EM-100'},{'material_id':'MAT-1'},{'work_order_id':'WO-1'}, {'run_id':'EM-100','limit':5},{'run_id':'EM-100'}]

def session(enabled=False):
 s=ProtocolServer(lambda name,args,key:{'status':'COMPLETED','result':{'tool':name}},enabled)
 s.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}})
 s.handle({'jsonrpc':'2.0','method':'notifications/initialized'})
 return s

@pytest.mark.parametrize('tool,args',list(zip(TOOLS,VALID)))
def test_golden_01_05_valid_schema(tool,args): assert validate(tool,args)

@pytest.mark.parametrize('tool,args',[(t,{}) for t in TOOLS])
def test_golden_06_10_missing_resource(tool,args):
 with pytest.raises(Rejected): validate(tool,args)

@pytest.mark.parametrize('tool,args',[(t,dict(a,extra='unsafe')) for t,a in zip(TOOLS,VALID)])
def test_golden_11_15_extra_arg_rejected(tool,args):
 with pytest.raises(Rejected): validate(tool,args)

@pytest.mark.parametrize('tool,args',[(t,{list(a)[0]:123}) for t,a in zip(TOOLS,VALID)])
def test_golden_16_20_nonstring_id(tool,args):
 with pytest.raises(Rejected): validate(tool,args)

@pytest.mark.parametrize('tool,args',list(zip(TOOLS,VALID)))
def test_golden_21_25_release_disabled(tool,args):
 res=session().handle({'jsonrpc':'2.0','id':42,'method':'tools/call','params':{'name':tool,'arguments':args}})
 assert res['error']['code']==-32003

@pytest.mark.parametrize('tool,args',list(zip(TOOLS,VALID)))
def test_golden_26_30_protocol_dispatch(tool,args):
 res=session(True).handle({'jsonrpc':'2.0','id':42,'method':'tools/call','params':{'name':tool,'arguments':args}})
 assert res['result']['isError'] is False

@pytest.mark.parametrize('method,code', [('unknown',-32601),('tools/call',-32602),('tools/list',None),('ping',None)])
def test_golden_31_34_protocol_methods(method,code):
 res=session().handle({'jsonrpc':'2.0','id':42,'method':method})
 assert ('error' in res and res['error']['code']==code) if code else 'result' in res

@pytest.mark.parametrize('case',range(10))
def test_golden_35_44_protocol_safety(case):
 s=session()
 secret='a'*40
 token=issue_test_token(secret,'tenant','principal',9999999999)
 if case==0: assert len(tools_list())==5
 if case==1: assert s.handle({'jsonrpc':'2.0','method':'notifications/initialized'}) is None
 if case==2: assert s.handle({'jsonrpc':'2.0','id':2,'method':'tools/list'})['result']['tools']
 if case==3: assert s.handle({'jsonrpc':'2.0','id':2,'method':'initialize','params':{'protocolVersion':'bad'}})['error']['code']==-32602
 if case==4: assert s.handle({'jsonrpc':'1.0','id':2,'method':'ping'})['error']['code']==-32600
 if case==5: assert s.handle({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'bad'}})['error']['code']==-32602
 if case==6: assert verify_token(secret,token).tenant=='tenant'
 if case==7:
  with pytest.raises(Rejected): verify_token(secret,token+'bad')
 if case==8: assert _hash('t','p','x',{'a':1})!=_hash('t','p','x',{'a':2})
 if case==9:
  out=io.StringIO(); serve(io.StringIO('{invalid\n'),out,s)
  assert json.loads(out.getvalue())['error']['code']==-32700
