"""Opt-in authenticated gateway bridge with explicit read-only allowlist.

Identity MUST come from a trusted identity resolver, never request JSON or a
bare Bearer token. Business adapter remains disabled unless explicitly enabled.
"""
from .auth import VerifiedIdentity
from .durable_ledger import LedgerConflict


class SecureBridge:
    def __init__(self, ledger, invoke, *, allowed_tools=(), enabled=False):
        if not callable(invoke):
            raise TypeError("invoke must be callable")
        self.ledger = ledger
        self.invoke = invoke
        self.allowed_tools = frozenset(allowed_tools)
        self.enabled = bool(enabled)

    def call(self, identity, key, tool, arguments):
        if not isinstance(identity, VerifiedIdentity):
            raise PermissionError("VERIFIED_IDENTITY_REQUIRED")
        if not self.enabled:
            raise PermissionError("BUSINESS_TOOLS_DISABLED")
        if tool not in self.allowed_tools or f"tool:{tool}" not in identity.scopes:
            raise PermissionError("TOOL_SCOPE_DENIED")
        if not isinstance(key, str) or not (1 <= len(key) <= 256):
            raise ValueError("INVALID_IDEMPOTENCY_KEY")
        if not isinstance(arguments, dict):
            raise ValueError("ARGUMENTS_NOT_OBJECT")
        claim = self.ledger.claim(identity.tenant, identity.principal, key, tool, arguments)
        if claim["action"] == "RETURN_CACHED":
            return claim["result"]
        if claim["action"] != "EXECUTE_ONCE":
            raise RuntimeError("UNCERTAIN_RESULT_NO_REPLAY")
        # Any exception leaves the durable claim IN_PROGRESS; human review required.
        result = self.invoke(identity, tool, arguments)
        self.ledger.complete(identity.tenant, identity.principal, key, tool, arguments, result)
        return result
