# C4.3 Compatibility Repair — Full Source Notes

## Scope

This is a complete-source rebuild based on the supplied `Industrial_AI_PaaS_Lab_V1.8_C4.3_MCP_Isolation_Full_Source.zip`. Existing M1–M4 business source and the C4.3 identity/session/call-boundary implementation are retained.

## Changes

1. **FastAPI route contract discovery**
   - Updated the Portfolio MCP route regression to inspect `app.openapi()["paths"]` rather than only top-level `app.routes`.
   - Updated the Workbench route regression in the same way.
   - Updated the Docker runtime smoke check to validate Portfolio MCP and Workbench Snapshot against the effective OpenAPI route map.
   - Reason: FastAPI 0.1xx can represent included routers using deferred `_IncludedRouter` objects. A shallow `app.routes` set can omit valid nested routes. OpenAPI expands the effective HTTP route contract.

2. **SQLite durable-ledger startup concurrency**
   - Moved WAL mode configuration to ledger initialization rather than issuing `PRAGMA journal_mode=WAL` on every connection.
   - Added bounded retry for transient SQLite `locked`/`busy` errors while concurrent workers initialize the same ledger.
   - No ledger schema, identity key, idempotency semantics, call state machine, or replay policy was changed.

## Verification performed in this build environment

- Python runtime: **3.13.5** (not the required project runtime 3.14).
- FastAPI in this build environment: **0.128.2** (the user's Windows diagnostic reported 0.162.0).
- Focused C4.3/MCP tests: **70 passed**.
- Broad offline suite: **396 passed, 12 skipped, 6 deselected**.
- The previously flaky `test_atomic_claim_concurrent` was repeated five additional times: **5/5 passed**.
- The focused identity + Workbench route subset: **13 passed**.
- `PG16 live`, fresh Docker build/runtime, Python 3.14 Windows execution and browser E2E were not run in this build environment.

## Important interpretation

- The two routes are present in the supplied source's effective route tree. The user's recursive diagnostic found both.
- The Portfolio MCP evidence endpoint returned HTTP 200 and `live_invocation_enabled: false` in the user's local test.
- The Workbench Snapshot endpoint returned HTTP 503 with `WORKBENCH_DATABASE_UNAVAILABLE` when no database credentials were configured. This is a truthful unavailable-database response, not proof of a missing route and not a passing live database test.
- No mock Snapshot data was introduced.
- No public `/mcp` route was added or enabled.

## Release status

This package is a **C4.3 compatibility-repaired full-source candidate**, not a production-approved release. Complete signoff remains blocked on Python 3.14 focused/broad gates, isolated PostgreSQL 16 integration, fresh Docker security/runtime verification, and browser E2E if required by the release plan.


The Docker gate uses a distinct `c43-repaired` image tag and container name. The earlier failed `industrial-ai-paas-v18-c43` diagnostic container is preserved and is not overwritten.
