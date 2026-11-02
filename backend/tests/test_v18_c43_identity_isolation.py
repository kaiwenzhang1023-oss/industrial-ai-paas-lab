"""C4.3 identity binding, session isolation and call-boundary regression."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from app.mcp_v18.auth import AuthenticationError, TokenRegistry, VerifiedIdentity
from app.mcp_v18.durable_ledger import DurableLedger
from app.mcp_v18.http_transport import MCPHTTPServer
from app.mcp_v18.secure_bridge import SecureBridge


def _send(server, token, payload=None, *, session=None, method="POST", origin=None):
    headers = {"Authorization": "Bearer " + token,
               "Content-Type": "application/json", "Accept": "application/json"}
    if session:
        headers["Mcp-Session-Id"] = session
    if origin:
        headers["Origin"] = origin
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/mcp", data=data,
        headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            raw = response.read()
            return response.status, dict(response.headers), json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, dict(exc.headers), json.loads(raw) if raw else None


def _init(server, token):
    status, headers, payload = _send(server, token, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"}})
    assert status == 200 and "result" in payload
    return headers["Mcp-Session-Id"]


@pytest.fixture
def identities_server(tmp_path):
    registry = TokenRegistry()
    token_a = "A" * 48
    token_b = "B" * 48
    identity_a = VerifiedIdentity("tenant-a", "principal-a", frozenset({"tool:mrp.get_run"}))
    identity_b = VerifiedIdentity("tenant-b", "principal-b", frozenset())
    registry.register(token_a, identity_a)
    registry.register(token_b, identity_b)
    calls = []
    bridge = SecureBridge(
        DurableLedger(tmp_path / "mcp-ledger.sqlite"),
        lambda identity, tool, args: calls.append((identity.tenant, identity.principal, tool, args)) or {"status": "COMPLETED"},
        allowed_tools={"mrp.get_run"}, enabled=True)
    server = MCPHTTPServer(("127.0.0.1", 0), None, identity_resolver=registry.authenticate,
                           bridge=bridge, enabled=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, registry, token_a, token_b, identity_a, identity_b, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_verified_identity_is_immutable_and_validated():
    identity = VerifiedIdentity("tenant", "principal", frozenset({"tool:read"}))
    assert identity.binding == ("tenant", "principal", ("tool:read",))
    with pytest.raises(ValueError):
        VerifiedIdentity("", "principal", frozenset())
    with pytest.raises(ValueError):
        VerifiedIdentity("tenant", "principal", {"tool:read"})


def test_token_registry_expiry_and_revocation():
    now = [100.0]
    registry = TokenRegistry(clock=lambda: now[0])
    identity = VerifiedIdentity("t", "p", frozenset())
    registry.register("T" * 40, identity, expires_at=110)
    assert registry.authenticate("T" * 40) == identity
    now[0] = 110
    with pytest.raises(AuthenticationError):
        registry.authenticate("T" * 40)
    registry.register("R" * 40, identity)
    assert registry.revoke("R" * 40) is True
    with pytest.raises(AuthenticationError):
        registry.authenticate("R" * 40)


def test_cross_tenant_session_reuse_is_denied_and_owner_continues(identities_server):
    server, _, token_a, token_b, _, _, calls = identities_server
    sid_a = _init(server, token_a)
    status, _, payload = _send(server, token_b,
        {"jsonrpc": "2.0", "id": 2, "method": "ping"}, session=sid_a)
    assert status == 403
    assert payload["error"] == "session_identity_mismatch"
    status, _, payload = _send(server, token_a,
        {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=sid_a)
    assert status == 202
    status, _, payload = _send(server, token_a,
        {"jsonrpc": "2.0", "id": 3, "method": "ping"}, session=sid_a)
    assert status == 200 and "result" in payload
    assert calls == []


def test_session_delete_requires_same_identity(identities_server):
    server, _, token_a, token_b, *_ = identities_server
    sid = _init(server, token_a)
    assert _send(server, token_b, session=sid, method="DELETE")[0] == 403
    assert sid in server.sessions
    assert _send(server, token_a, session=sid, method="DELETE")[0] == 204
    assert sid not in server.sessions


def test_revoked_token_cannot_continue_existing_session(identities_server):
    server, registry, token_a, _, *_ = identities_server
    sid = _init(server, token_a)
    assert registry.revoke(token_a)
    status, _, payload = _send(server, token_a,
        {"jsonrpc": "2.0", "id": 2, "method": "ping"}, session=sid)
    assert status == 401
    assert payload["error"] == "unauthorized"


def test_bridge_scope_allowlist_and_identity_boundary(identities_server):
    server, _, token_a, token_b, _, _, calls = identities_server
    sid_b = _init(server, token_b)
    _send(server, token_b, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=sid_b)
    status, _, payload = _send(server, token_b, {
        "jsonrpc": "2.0", "id": 9, "method": "tools/call",
        "params": {"name": "mrp.get_run", "arguments": {"run_id": "EM-100"}}}, session=sid_b)
    assert status == 200
    assert "error" in payload
    assert calls == []


def test_authorized_call_is_bound_to_verified_identity(identities_server):
    server, _, token_a, _, identity_a, _, calls = identities_server
    sid = _init(server, token_a)
    _send(server, token_a, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=sid)
    status, _, payload = _send(server, token_a, {
        "jsonrpc": "2.0", "id": 12, "method": "tools/call",
        "params": {"name": "mrp.get_run", "arguments": {"run_id": "EM-100"}}}, session=sid)
    assert status == 200 and "result" in payload
    assert calls == [(identity_a.tenant, identity_a.principal, "mrp.get_run", {"run_id": "EM-100"})]


def test_no_live_mcp_http_route_is_mounted_in_public_fastapi_app():
    from app.main import app
    # Use the effective OpenAPI route map rather than only app.routes:
    # FastAPI 0.1xx can defer included routers in _IncludedRouter wrappers.
    paths = set(app.openapi().get("paths", {}))
    assert "/api/v1/portfolio/mcp/tools" in paths
    assert "/mcp" not in paths
    assert not any(path.startswith("/mcp/") for path in paths)


def test_scope_change_cannot_reuse_existing_session(tmp_path):
    registry = TokenRegistry()
    full = "F" * 48
    reduced = "R" * 48
    registry.register(full, VerifiedIdentity("tenant", "principal", frozenset({"tool:mrp.get_run"})))
    registry.register(reduced, VerifiedIdentity("tenant", "principal", frozenset()))
    server = MCPHTTPServer(("127.0.0.1", 0), lambda *_: {"status": "COMPLETED"},
                           identity_resolver=registry.authenticate)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sid = _init(server, full)
        status, _, payload = _send(server, reduced,
            {"jsonrpc": "2.0", "id": 2, "method": "ping"}, session=sid)
        assert status == 403 and payload["error"] == "session_identity_mismatch"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_expired_session_is_pruned(tmp_path):
    now = [10.0]
    registry = TokenRegistry(clock=lambda: now[0])
    token = "E" * 48
    registry.register(token, VerifiedIdentity("tenant", "principal", frozenset()))
    server = MCPHTTPServer(("127.0.0.1", 0), lambda *_: None,
                           identity_resolver=registry.authenticate,
                           session_ttl_seconds=5, clock=lambda: now[0])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sid = _init(server, token)
        now[0] = 15.0
        status, _, payload = _send(server, token,
            {"jsonrpc": "2.0", "id": 2, "method": "ping"}, session=sid)
        assert status == 404 and payload["error"] == "unknown_session"
        assert sid not in server.sessions
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_client_supplied_identity_fields_do_not_grant_access(identities_server):
    server, _, token_b, _, _, _, calls = identities_server
    sid = _init(server, token_b)
    _send(server, token_b, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session=sid)
    status, _, payload = _send(server, token_b, {
        "jsonrpc": "2.0", "id": 17, "method": "tools/call",
        "params": {"name": "mrp.get_run", "arguments": {
            "run_id": "EM-100", "tenant": "tenant-a", "principal": "principal-a",
            "scopes": ["tool:mrp.get_run"]}}}, session=sid)
    assert status == 200 and "error" in payload
    assert calls == []
