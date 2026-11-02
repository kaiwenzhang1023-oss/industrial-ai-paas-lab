"""V1.8 opt-in MCP transport, identity isolation and recovery safeguards."""
from .auth import AuthenticationError, TokenRegistry, VerifiedIdentity

__all__ = ["AuthenticationError", "TokenRegistry", "VerifiedIdentity"]
