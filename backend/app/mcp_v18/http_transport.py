"""Identity-bound, loopback-only MCP HTTP transport for isolated local use.

This server is deliberately not mounted in the public FastAPI application.
Authentication is injected by trusted host code. Each MCP session is bound to
its authenticated tenant/principal/scopes; every request and DELETE is checked
against that binding. Default business-tool execution remains disabled.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import secrets
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

from app.mcp_v17.transport import HardenedProtocolServer
from .auth import AuthenticationError, VerifiedIdentity

MAX_BODY = 1024 * 1024
SUPPORTED = "2024-11-05"
DEFAULT_SESSION_TTL = 1800


@dataclass
class SessionRecord:
    protocol: HardenedProtocolServer
    identity: VerifiedIdentity
    created_at: float
    last_seen: float


class MCPHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, invoke, token=None, *, enabled=False,
                 identity_resolver=None, bridge=None, allowed_tools=(),
                 session_ttl_seconds=DEFAULT_SESSION_TTL, clock=time.monotonic):
        if not isinstance(address, tuple) or len(address) < 2 or address[0] != "127.0.0.1":
            raise ValueError("LOOPBACK_ONLY")
        if identity_resolver is not None and not callable(identity_resolver):
            raise TypeError("IDENTITY_RESOLVER_REQUIRED")
        if identity_resolver is None and (not isinstance(token, str) or len(token) < 32):
            raise ValueError("TOKEN_REQUIRED")
        if bridge is None and not callable(invoke):
            raise TypeError("INVOKE_REQUIRED")
        if bridge is not None and not callable(getattr(bridge, "call", None)):
            raise TypeError("SECURE_BRIDGE_REQUIRED")
        if type(session_ttl_seconds) not in (int, float) or not 1 <= session_ttl_seconds <= 86400:
            raise ValueError("INVALID_SESSION_TTL")
        self.token = token
        self.identity_resolver = identity_resolver
        self.invoke = invoke
        self.bridge = bridge
        self.allowed_tools = frozenset(allowed_tools)
        self.enabled = bool(enabled)
        self.session_ttl_seconds = float(session_ttl_seconds)
        self.clock = clock
        self.sessions: dict[str, SessionRecord] = {}
        self.lock = threading.RLock()
        super().__init__(address, Handler)

    def authenticate_request(self, headers):
        authorization = headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("UNAUTHORIZED")
        presented = authorization[7:]
        if not presented:
            raise AuthenticationError("UNAUTHORIZED")
        if self.identity_resolver is not None:
            identity = self.identity_resolver(presented)
            if not isinstance(identity, VerifiedIdentity):
                raise AuthenticationError("UNAUTHORIZED")
            return identity
        if not secrets.compare_digest(presented, self.token):
            raise AuthenticationError("UNAUTHORIZED")
        # Compatibility identity for the legacy single-principal local test host.
        # It has no scopes and cannot invoke any bridge-protected business tool.
        return VerifiedIdentity("local", "legacy-static-token", frozenset())

    def prune_sessions(self):
        now = self.clock()
        expired = [sid for sid, rec in self.sessions.items()
                   if now - rec.last_seen >= self.session_ttl_seconds]
        for sid in expired:
            self.sessions.pop(sid, None)

    def invoke_for_identity(self, identity, tool, arguments, request_key):
        if not self.enabled:
            raise PermissionError("BUSINESS_TOOLS_DISABLED")
        if self.bridge is not None:
            return self.bridge.call(identity, request_key, tool, arguments)
        if tool not in self.allowed_tools or f"tool:{tool}" not in identity.scopes:
            raise PermissionError("TOOL_SCOPE_DENIED")
        # Identity-aware callback contract is explicit and only used with injected auth.
        if self.identity_resolver is None:
            raise PermissionError("TRUSTED_IDENTITY_RESOLVER_REQUIRED")
        return self.invoke(identity, tool, arguments, request_key)


class Handler(BaseHTTPRequestHandler):
    server_version = "IndustrialMCP/1.8-C4.3"
    sys_version = ""

    def log_message(self, *args):
        # Never log Authorization, tokens, Session IDs or request bodies.
        pass

    def reply(self, status, payload=None, *, session=None):
        raw = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if session:
            self.send_header("Mcp-Session-Id", session)
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def safe_origin(self):
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        if origin in ("http://127.0.0.1", "http://localhost"):
            return True
        for prefix in ("http://127.0.0.1:", "http://localhost:"):
            if origin.startswith(prefix) and origin[len(prefix):].isdigit():
                port = int(origin[len(prefix):])
                return 1 <= port <= 65535
        return False

    def _identity(self):
        try:
            return self.server.authenticate_request(self.headers)
        except Exception:
            # Provider failures are indistinguishable from invalid credentials.
            return None

    def do_GET(self):
        if urlsplit(self.path).path == "/health":
            return self.reply(200, {"service": "mcp-v18-local", "tools_enabled": self.server.enabled})
        return self.reply(404, {"error": "not_found"})

    def do_POST(self):
        if urlsplit(self.path).path != "/mcp":
            return self.reply(404, {"error": "not_found"})
        if not self.safe_origin():
            return self.reply(403, {"error": "origin_denied"})
        identity = self._identity()
        if identity is None:
            return self.reply(401, {"error": "unauthorized"})
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self.reply(415, {"error": "unsupported_media_type"})
        accepted = {part.split(";")[0].strip().lower() for part in self.headers.get("Accept", "application/json").split(",")}
        if "application/json" not in accepted and "*/*" not in accepted:
            return self.reply(406, {"error": "not_acceptable"})
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            return self.reply(400, {"error": "invalid_length"})
        if size < 0:
            return self.reply(411, {"error": "content_length_required"})
        if size > MAX_BODY:
            return self.reply(413, {"error": "invalid_size"})
        try:
            message = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError):
            return self.reply(400, {"jsonrpc": "2.0", "id": None,
                                    "error": {"code": -32700, "message": "Parse error"}})
        if not isinstance(message, dict):
            return self.reply(400, {"error": "invalid_request"})
        method = message.get("method")
        sid = self.headers.get("Mcp-Session-Id")
        with self.server.lock:
            self.server.prune_sessions()
            if method == "initialize":
                if sid:
                    return self.reply(400, {"error": "initialize_with_session_denied"})
                if len(self.server.sessions) >= 64:
                    return self.reply(503, {"error": "session_limit"})
                # Bind the authenticated identity into the protocol's invocation closure.
                def bound_invoke(tool, arguments, request_key):
                    return self.server.invoke_for_identity(identity, tool, arguments, request_key)
                protocol = HardenedProtocolServer(bound_invoke, enabled=self.server.enabled)
                result = protocol.handle(message)
                if not isinstance(result, dict) or "result" not in result:
                    return self.reply(400, result)
                session_id = secrets.token_urlsafe(32)
                now = self.server.clock()
                self.server.sessions[session_id] = SessionRecord(protocol, identity, now, now)
                return self.reply(200, result, session=session_id)
            if not sid or sid not in self.server.sessions:
                return self.reply(404, {"error": "unknown_session"})
            record = self.server.sessions[sid]
            if record.identity.binding != identity.binding:
                return self.reply(403, {"error": "session_identity_mismatch"})
            if self.headers.get("MCP-Protocol-Version") not in (None, SUPPORTED):
                return self.reply(400, {"error": "unsupported_protocol_version"})
            record.last_seen = self.server.clock()
            result = record.protocol.handle(message)
            return self.reply(202 if result is None else 200, result, session=sid)

    def do_DELETE(self):
        if urlsplit(self.path).path != "/mcp":
            return self.reply(404, {"error": "not_found"})
        if not self.safe_origin():
            return self.reply(403, {"error": "origin_denied"})
        identity = self._identity()
        if identity is None:
            return self.reply(401, {"error": "unauthorized"})
        sid = self.headers.get("Mcp-Session-Id")
        with self.server.lock:
            self.server.prune_sessions()
            record = self.server.sessions.get(sid) if sid else None
            if record is None:
                return self.reply(404, {"error": "unknown_session"})
            if record.identity.binding != identity.binding:
                return self.reply(403, {"error": "session_identity_mismatch"})
            self.server.sessions.pop(sid, None)
        return self.reply(204)
