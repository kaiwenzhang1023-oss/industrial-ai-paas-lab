# C4.4 Acceptance Report

## Baseline and source preservation

- Baseline: `Industrial_AI_PaaS_Lab_V1.8_C4.3_Compatibility_Repaired_Full_Source.zip`.
- Baseline archive SHA-256 is recorded in `C44_BUILD_MANIFEST.json`.
- Original archive was copied unchanged to the delivery set; the new package is a full-source copy with only the enumerated C4.4 edits and additive files.
- Historical database migrations 017–020 and 024 are unchanged.

## Static contract review

- Runtime Python path no longer contains direct `INSERT`, `SELECT`, or `UPDATE` statements against `mcp_v15.request_ledger`.
- Runtime claim/finish use narrow database functions.
- Recovery uses an operator-only database function; no direct ledger table scan remains in the Python recovery module.
- Function owner is a dedicated `NOLOGIN NOBYPASSRLS` role; schema CREATE is revoked after function ownership transfer.
- Runtime and reader roles have no direct ledger table privileges or ledger policy.
- Existing V1.8 secure HTTP bridge, SQLite DurableLedger and optional V1.8 PostgreSQL ledger remain intact and explicitly separate from the legacy V1.5 stdio ledger path.

## Build-sandbox tests

- Python bytecode compilation: PASS (Python 3.13.5 sandbox).
- Focused MCP/static regression: **71 passed, 1 skipped**.
- Broad offline regression: **399 passed, 23 skipped**.
- Full unfiltered pytest collection was not possible because `psycopg` is not installed in this sandbox. Browser E2E also requires a local Chromium executable. These are not counted as passes.

## Live integration status

- PostgreSQL 16 migration and security/idempotency acceptance: **NOT RUN in this sandbox**; Docker CLI/daemon, psql and psycopg are unavailable.
- `RUN_C44_PG16_GATE.ps1` applies migration 025 to `industrial_lab_v15_test`, runs SQL security/idempotency acceptance, executes broad offline tests, and then runs V1.5/V1.8 live PG16 integration tests. It requires Python 3.14 and the isolated DSNs described in the script.
- Python 3.14 Docker rebuild/runtime smoke: **NOT RUN** here.

## Release decision

C4.4 static/offline checks: **PASS**.
PG16 integration: **PENDING — required before signoff**.
Production: **NO-GO** until live PG16, Python 3.14, fresh Docker build/runtime, and any external conformance gates pass.
