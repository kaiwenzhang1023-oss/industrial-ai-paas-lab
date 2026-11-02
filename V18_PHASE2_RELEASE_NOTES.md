# V1.8 Phase 2 — durable local ledger development candidate

- Adds opt-in `app.mcp_v18.durable_ledger.DurableLedger` (SQLite, Python standard library).
- Atomic `BEGIN IMMEDIATE` idempotency claims scoped by tenant/principal/key, canonical tool/arguments SHA-256 fingerprints, conflict rejection, cached durable result and append-only application-level audit events.
- After process restart an unfinished request is **never automatically re-executed**; inspect returns WAIT or MANUAL_REVIEW. A durable DONE result can be returned without re-execution.
- The ledger is **not connected to MCP HTTP dispatch by default**. Integration requires explicit authorization and trusted host ownership; do not enable production business tools.
- SQLite is local single-host development persistence, **not PostgreSQL 16/18**, distributed transaction coordination, exactly-once side effects, tamper-proof audit or a recovery worker. A crash after business execution but before result commit remains ambiguous and requires manual reconciliation.
- No migration, credentials, Neon, Render or production changes.
- Windows selected offline gate: `RUN_ACCEPTANCE_V18_PHASE2.cmd`. No Neon credentials. Production NO-GO.
