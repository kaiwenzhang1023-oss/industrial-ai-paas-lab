# V1.8 C4.4 — MCP Request Ledger Security Repair

## Baseline

Built from the exact `V1.8_C4.3_Compatibility_Repaired_Full_Source` archive. The original archive is retained separately and was not modified. Historical migrations 017–020 are preserved byte-for-byte; C4.4 is a forward-only migration.

## Changes

- Added `025_v15_request_ledger_security_api_TEST_ONLY.sql`. It is restricted to `industrial_lab_v15_test`.
- Removed the runtime role's direct SELECT/INSERT/UPDATE access to `mcp_v15.request_ledger` and removed only the exact broad policy created by migration 020. Unexpected policy definitions fail closed for manual review.
- Added a dedicated `NOLOGIN NOBYPASSRLS` function-owner role. Narrow `SECURITY DEFINER` functions provide claim, finish, and operator-only stale inspection.
- Updated the active V1.5 stdio idempotency path to call those functions rather than directly reading/writing the ledger table.
- Updated V1.7 recovery inspection to use the operator-only database function rather than direct table scans.
- Added static contract tests and a PG16 SQL acceptance gate.

## Preserved

- Original source tree and all unrelated M1–M4 / V1.8 modules.
- Historical migrations 017–020 and V1.8 development-only migration 024.
- SQLite V1.8 DurableLedger and optional PostgresLedger implementation; these are separate V1.8 secure-bridge persistence adapters, not silently merged into the legacy stdio transport.

## Current verification

- Focused static/offline regression: **71 passed, 1 skipped** (Python 3.13.5 build sandbox).
- PG16 live integration: **NOT RUN in this build sandbox**; Docker and psql are unavailable here. Run `RUN_C44_PG16_GATE.ps1` on the isolated Windows PG16 environment.
- Python 3.14 runtime and Docker image rebuild: **NOT RUN** here.

## Signoff

C4.4 static/offline checks: PASS. PG16 live gate: PENDING. Production: NO-GO until the isolated PG16 gate, Python 3.14 gate, and fresh Docker build/runtime checks pass.
