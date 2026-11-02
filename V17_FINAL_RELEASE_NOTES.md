# V1.7 Consolidated Full Source — final development candidate

## Delivered
- Separate loopback-only JSON-RPC HTTP MCP development endpoint (`app/mcp_v17/http_transport.py`). Opt-in server object, bearer token, 1 MiB bound, no external binding; not mounted into public app.
- Read-only request-ledger recovery inspection (`app/mcp_v17/recovery.py`); stale in-progress calls are UNKNOWN and never auto-replayed.
- Read-only Workbench showcase at `/workbench/v17.html`, using existing PostgreSQL-backed snapshot API. No fake success or new database mutations.
- Consolidated local offline gate `ACCEPT_V17.ps1` and regression tests.

## Explicit limitations
- Network transport is an isolated local development implementation, NOT full MCP Streamable HTTP compliance (no SSE/resumption/OAuth/session durability). Do not expose to public internet.
- No autonomous crash recovery worker or retry; manual review for stale requests is intentional fail-closed behavior.
- Browser and PG16 integration tests require user's Windows environment. No Neon/Render changes performed.
- Existing V1.5 release-disabled gateway and V1.6 reader security remain unchanged.
