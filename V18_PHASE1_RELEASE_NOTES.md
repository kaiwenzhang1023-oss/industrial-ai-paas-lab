# V1.8 Phase 1 — development candidate (NOT Final)

Baseline: V1.7 Final RC, frozen. V1.7 local acceptance: 74 passed (user Windows).

## Added
- `app/mcp_v18/http_transport.py`: separate loopback-only, bearer-authenticated MCP JSON-RPC HTTP server with per-session initialization, session deletion, explicit Origin filtering, 1 MiB request bound, default disabled business tools. Does not mount to public app.
- `app/mcp_v18/recovery.py`: conservative durable-result triage; ambiguous requests are NEVER automatically replayed, even if operation is nominally idempotent.
- `RUN_ACCEPTANCE_V18.cmd`: one command, offline selected gates, no Neon secrets.

## NOT done / NOT certified
- Production-grade MCP Streamable HTTP, SSE, OAuth, persistent/multi-worker sessions, production network deployment.
- Crash-safe automated replay/compensation; PG16 live integration and Workbench browser UX.
- No Neon or Render modifications. Production NO-GO.

## Next phase
Implement persistent session/audit storage, secure transport lifecycle, durable idempotency protocol and recovery worker with explicit proof of safe replay, then integration gates and Workbench browser tests. Keep release disabled until certified.
