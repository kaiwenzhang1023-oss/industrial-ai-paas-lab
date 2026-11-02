# V1.8 C4.3 — MCP Identity Binding, Session Isolation & Call Boundaries

## Status

C4.3 implementation candidate. Offline regression is recorded separately in `C43_ACCEPTANCE_REPORT.md`. This is not a production security certification.

## Scope

- Preserve V1.8 M1–M4, MRP, Workflow, PG16 ledger, portfolio and Workbench behavior.
- Add trusted identity resolution for the isolated MCP HTTP host.
- Bind every MCP session to `(tenant, principal, scopes)`.
- Re-authenticate every POST and DELETE, including requests on an existing session.
- Enforce expiry/revocation at the token resolver and session TTL at the transport.
- Route tool calls through `SecureBridge`, which enforces enabled state, tool allowlist, `tool:<name>` scope and tenant/principal-scoped durable idempotency.
- Keep live MCP transport out of the public FastAPI application.

## Trust model

1. `TokenRegistry` is a local reference provider. Trusted host code provisions and revokes opaque tokens. Only SHA-256 digests are retained. It exposes no HTTP token-management endpoint.
2. `identity_resolver(token)` is the injection seam for an enterprise OAuth/OIDC/resource-server adapter. The resolver must validate issuer, audience, signature, expiry, revocation and required claims before returning `VerifiedIdentity`.
3. Client-supplied JSON fields such as `tenant`, `principal`, `scopes`, or `identity` are never trusted for authorization.
4. `VerifiedIdentity` is immutable and validated. Session identity binding includes the complete scope set; a token resolving to a different tenant, principal or scope set cannot use or delete the session.
5. Session IDs are random bearer capabilities, not substitutes for authentication. Every request still requires a currently valid token.
6. The default business-tool gate remains disabled. An enabled host must inject a `SecureBridge` with an explicit read-only tool allowlist and a trusted business adapter.

## Session lifecycle

- `initialize` creates a new protocol instance and a cryptographically random session ID.
- A session is stored with its verified identity, creation time and last-seen time.
- A request with a mismatched identity receives HTTP 403 and cannot advance or invoke the session.
- Expired sessions are pruned and return HTTP 404.
- `DELETE` requires both a valid current token and an exact identity match.
- Session storage is process-local. Multi-worker deployments require sticky routing or a separately designed shared session store; this implementation must not be treated as horizontally shared state.

## Call boundary

`MCPHTTPServer -> HardenedProtocolServer -> SecureBridge -> DurableLedger -> trusted read-only adapter`.

The bridge checks identity type, enabled switch, allowlist and scope before claiming idempotency state. The ledger key is `(tenant, principal, request_key)`. An ambiguous `IN_PROGRESS` call is never automatically replayed. No public FastAPI route mounts this transport; `/api/v1/portfolio/mcp/tools` remains evidence-only metadata.

## Runtime security

The Dockerfile now uses Python 3.14 slim and defaults to UID/GID `10001:10001`. Runtime orchestration must additionally enforce read-only root filesystem, dropped Linux capabilities, `no-new-privileges`, PID/memory/CPU limits, a bounded writable tmpfs, and an explicit network policy. Dockerfile `USER` alone is not the runtime sandbox.

## Compatibility

- Existing constructor `MCPHTTPServer(('127.0.0.1', port), invoke, token)` remains available for legacy local tests. Its fixed local identity has no scopes and cannot invoke a bridge-protected tool.
- New secure usage injects `identity_resolver` and `bridge`; no identity is accepted from request JSON.
- Existing M1–M4 routes, schemas, SQL migrations and business contracts are not changed by C4.3.

## Known limitations / not certified

- `TokenRegistry` is process-memory reference infrastructure, not an OAuth/OIDC implementation.
- No enterprise issuer/audience/JWKS integration is included.
- No distributed session store or multi-worker session replication is included.
- No production business adapter is enabled by this package.
- PG16 live integration, full external MCP conformance, browser E2E and production penetration testing must be run in the user's isolated environment before signoff.
