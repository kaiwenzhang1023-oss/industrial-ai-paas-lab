"""Trusted in-process opaque-token authentication for the isolated MCP host.

Tokens are provisioned by trusted host code, never by MCP request payloads.
Only SHA-256 token digests are retained. This is an in-memory reference
provider; production deployments should inject an enterprise identity resolver.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import threading
import time
from typing import Callable


class AuthenticationError(PermissionError):
    """Authentication failed; deliberately carries no credential detail."""


@dataclass(frozen=True)
class VerifiedIdentity:
    tenant: str
    principal: str
    scopes: frozenset[str]

    def __post_init__(self) -> None:
        if (not isinstance(self.tenant, str) or not self.tenant or len(self.tenant) > 128
                or not isinstance(self.principal, str) or not self.principal or len(self.principal) > 128
                or not isinstance(self.scopes, frozenset)
                or any(not isinstance(s, str) or not s or len(s) > 128 for s in self.scopes)):
            raise ValueError("VERIFIED_IDENTITY_REQUIRED")

    @property
    def binding(self) -> tuple[str, str, tuple[str, ...]]:
        return self.tenant, self.principal, tuple(sorted(self.scopes))


@dataclass(frozen=True)
class _TokenRecord:
    identity: VerifiedIdentity
    expires_at: float | None


class TokenRegistry:
    """Explicitly provisioned opaque tokens -> trusted identities.

    The registry is local to one process and is not a user/token management API.
    Tokens can be revoked by trusted host code. A token must contain at least
    32 characters. Expiry is checked on every request, including existing
    session requests.
    """
    def __init__(self, *, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._records: dict[str, _TokenRecord] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def register(self, token: str, identity: VerifiedIdentity, *, expires_at: float | None = None) -> None:
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("TOKEN_REQUIRED")
        if not isinstance(identity, VerifiedIdentity):
            raise TypeError("VERIFIED_IDENTITY_REQUIRED")
        if expires_at is not None and (type(expires_at) not in (int, float) or expires_at <= self._clock()):
            raise ValueError("INVALID_TOKEN_EXPIRY")
        digest = self._digest(token)
        with self._lock:
            self._records[digest] = _TokenRecord(identity, float(expires_at) if expires_at is not None else None)

    def revoke(self, token: str) -> bool:
        if not isinstance(token, str):
            return False
        digest = self._digest(token)
        with self._lock:
            return self._records.pop(digest, None) is not None

    def authenticate(self, token: str) -> VerifiedIdentity:
        if not isinstance(token, str) or not token:
            raise AuthenticationError("UNAUTHORIZED")
        candidate = self._digest(token)
        now = self._clock()
        with self._lock:
            match = None
            # Constant-time digest comparison; do not use caller-supplied identity claims.
            for stored, record in self._records.items():
                if hmac.compare_digest(candidate, stored):
                    match = record
            if match is None or (match.expires_at is not None and now >= match.expires_at):
                raise AuthenticationError("UNAUTHORIZED")
            return match.identity


IdentityResolver = Callable[[str], VerifiedIdentity]
