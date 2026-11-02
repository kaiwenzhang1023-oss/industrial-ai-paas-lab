from app.mcp_v15.security import Identity, TOOLS, authorize, tool_enabled

def test_tools_disabled():
    assert len(TOOLS)==5
    assert not any(TOOLS.values())
    assert not tool_enabled("nonexistent")

def test_fail_closed_empty_identity():
    assert authorize(None, Identity("", "p"), "read", "T", "r") is False
