import pytest
from app.mcp_v15.full_gateway import SPECS,Rejected,issue_test_token,verify_token,validate,FullGateway
SECRET='this-is-a-test-only-very-long-secret-0123456789'
GOOD={'mrp.get_run':{'run_id':'R1'},'wms.get_inventory':{'material_id':'M1'},
      'mes.get_work_order':{'work_order_id':'WO1'},'srm.list_requisitions':{'run_id':'R1'},
      'mapping.preview_b01':{'run_id':'R1'}}

@pytest.mark.parametrize('tool',list(GOOD))
def test_registered_and_valid(tool):
 assert validate(tool,GOOD[tool])[1] in ('R1','M1','WO1')

@pytest.mark.parametrize('tool',list(GOOD))
def test_reject_extra_fields(tool):
 with pytest.raises(Rejected): validate(tool,{**GOOD[tool],'tenant_id':'spoof'})

@pytest.mark.parametrize('tool',list(GOOD))
def test_reject_missing_key(tool):
 with pytest.raises(Rejected): validate(tool,{})

@pytest.mark.parametrize('tool',list(GOOD))
def test_reject_empty_key(tool):
 key=next(iter(GOOD[tool]));
 with pytest.raises(Rejected): validate(tool,{key:''})

@pytest.mark.parametrize('tool',list(GOOD))
def test_reject_oversized_key(tool):
 key=next(iter(GOOD[tool]));
 with pytest.raises(Rejected): validate(tool,{key:'a'*129})

@pytest.mark.parametrize('tool',list(GOOD))
def test_reject_nonstring_key(tool):
 key=next(iter(GOOD[tool]));
 with pytest.raises(Rejected): validate(tool,{key:42})

@pytest.mark.parametrize('tool',list(GOOD))
def test_reject_nan_and_nested_injection(tool):
 key=next(iter(GOOD[tool]));
 with pytest.raises((Rejected,ValueError)): validate(tool,{key:{'sql':'DROP TABLE'}})

@pytest.mark.parametrize('limit',[0,-1,101,True,1.5,'10'])
def test_srm_limit_rejected(limit):
 with pytest.raises(Rejected): validate('srm.list_requisitions',{'run_id':'R1','limit':limit})

def test_token_valid():
 token=issue_test_token(SECRET,'t','p',200)
 assert verify_token(SECRET,token,100).principal=='p'

def test_token_expired():
 token=issue_test_token(SECRET,'t','p',200)
 with pytest.raises(Rejected): verify_token(SECRET,token,200)

def test_token_tampered():
 token=issue_test_token(SECRET,'t','p',200)
 with pytest.raises(Rejected): verify_token(SECRET,token[:-1]+'x',100)

def test_default_release_disabled():
 assert FullGateway(SECRET)._release is False

def test_short_secret_rejected():
 with pytest.raises(ValueError): FullGateway('bad')

def test_unknown_tool():
 with pytest.raises(Rejected): validate('system.execute',{'run_id':'R1'})


def test_mcp_integration_import_does_not_require_pydantic():
    # Import the adapter in a fresh interpreter with Pydantic intentionally blocked.
    import subprocess, sys, os
    script = """import builtins
orig = builtins.__import__
def block(name, *a, **kw):
    if name == 'pydantic' or name.startswith('pydantic.'):
        raise ModuleNotFoundError('blocked optional pydantic')
    return orig(name, *a, **kw)
builtins.__import__ = block
from app.mcp_v15.full_gateway import FullGateway
assert FullGateway('x'*32)._release is False
"""
    proc = subprocess.run([sys.executable, '-c', script],
                          capture_output=True, text=True, env=os.environ.copy())
    assert proc.returncode == 0, proc.stderr
