# Industrial AI PaaS Lab V1.7 — integrated development candidate

## Source baseline
Exact V1.6 RC5 consolidated full-source archive supplied in conversation; original frozen archive unchanged.

## Added
- `app.mcp_v17.transport.HardenedProtocolServer`: local MCP stdio facade with handshake sequencing, duplicate initialization rejection, fail-closed release, strict tool argument validation before gateway invocation, no public HTTP endpoint.
- `tests/test_v17_transport.py`: deterministic protocol/security regression.
- `ACCEPT_V17.ps1`: one-command selected offline contract suite and sanitized JSON report; opt-in `-LiveNeon` requires explicit isolated dev branch confirmation and reader DSN.

## Boundaries and release decision
- V1.5 audited MCP FullGateway, adapter authorization, idempotency and persistence are reused, not replaced.
- Network HTTP MCP, production authentication, crash recovery, browser Workbench, full PG16 regression and real database E2E are **NOT certified by this offline gate**.
- No database migration, Neon/Render production change or public MCP exposure.
- This is a development candidate, NOT a production release.
- V1.6 RC5 already passed user-run PG16/Neon acceptance; V1.7 needs new Windows host acceptance for affected behavior.

## Windows one-command verification
Run from unpacked project root: `powershell -NoProfile -ExecutionPolicy Bypass -File .\ACCEPT_V17.ps1`
Optional separate dev-only Neon read gate: `... -LiveNeon` after securely configuring the dedicated reader DSN.
