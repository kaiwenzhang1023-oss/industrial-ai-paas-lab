# V1.8 Phase 3 — PostgreSQL ledger + secure gateway bridge (development candidate)

## Added
- `app/mcp_v18/pg_ledger.py`: opt-in PG16/PG18 atomic claim, durable results, append-only events and conservative inspection; schema in `database/024_v18_phase3_pg_ledger_DEV_ONLY.sql`.
- `app/mcp_v18/secure_bridge.py`: explicit trusted `VerifiedIdentity`, scope allowlist, default-disabled business calls, durable deduplication, no replay of ambiguous outcomes.
- Selected offline regression and Windows one-command acceptance.

## Important limits / NO-GO
- PostgreSQL implementation is **not live-tested** in this delivery. Schema is NOT applied automatically. No DB credentials included.
- SecureBridge is **not wired to HTTP transport or real business adapters**. Host must verify identity independently and pass a trusted identity object; an arbitrary Bearer token is not an identity proof.
- Current HTTP transport is still local development-only and NOT a certified MCP Streamable HTTP implementation, OAuth authorization server, or internet-exposed service.
- No crash replay, no distributed exactly-once guarantee, no browser E2E. Production remains NO-GO.
- No existing PG16/Neon/Render database or deployment is touched.
