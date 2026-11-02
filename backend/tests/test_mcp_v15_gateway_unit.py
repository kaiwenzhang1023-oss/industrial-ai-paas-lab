import pytest
from app.mcp_v15.gateway import Registry, Gateway, TOOL_NAMES
from app.mcp_v15.security import Identity

def test_all_five_disabled_and_unknown_denied():
    r=Registry()
    assert len(r.list_tools())==5
    assert set(x.name for x in r.list_tools())==set(TOOL_NAMES)
    assert all(not x.enabled for x in r.list_tools())
    assert not r.enabled('unregistered')

def test_no_untrusted_identity_or_unknown_tool():
    g=Gateway()
    with pytest.raises(ValueError): g.submit(None,None,'mrp.get_run',{},'MRP','r')
    with pytest.raises(ValueError): g.submit(None,Identity('t','p'),'other',{},'MRP','r')
