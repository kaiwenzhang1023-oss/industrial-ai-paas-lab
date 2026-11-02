# M3-02 V0.3 — Agent execution closure and atomic audit

## Baseline and frozen contracts
Based on signed V0.2 (151 full regression tests, 23 PG integration tests). No modifications to M2 persisted `mrp_lines` schema, material master `make_buy`, workflow event names, Outbox event counts or procurement human-review requirement. No new database migration needed.

## Implementation
- `generate_and_persist` now performs actual persisted MRP and ERP material master reads **inside** the `mrp.read` ToolGateway adapter, not before it. Audit hashes reflect the actual returned fact object.
- Workflow row is locked before tool execution; a single PostgreSQL outer transaction includes tool audit, Agent Draft, workflow state transition, inbox, workflow audit, and outbox.
- `dispatch_in_transaction` uses a nested psycopg transaction/savepoint; it never commits the outer transaction.
- Failed transition rolls back the whole success path; there is no orphan Draft or success audit. Test `test_agent_atomic_v03.py` injects a failure at dispatch and checks rollback, then retries.
- No external LLM or standard MCP wire protocol; deterministic offline contract model remains. No ERP purchase request write.

## Known limitations
- Failed attempts inside the transaction roll back their tool audit too; durable failure/denial audit with a separate reliable event channel is **not** included in this release.
- Database lock is held during deterministic model execution. Do not inject a network/slow model in this transaction without designing a lease/fencing and staged execution protocol.
- Global MRP result must not be misrepresented as per-order pegging.

## Windows test procedure
Open PowerShell **inside `m2_pg16_gate`** and run `Set-ExecutionPolicy -Scope Process Bypass -Force; .\\run_pg16_gate.ps1`.
The script recreates **industrial_lab_test**. Logs are written into `m2_pg16_gate` (not `backend`). To read logs from `backend`, use `Get-Content ..\\pg16_integration.log -Tail 15` and `Get-Content ..\\pg16_full_regression.log -Tail 15`.

## Signoff gate
Previously 151 full / 23 PG integration; V0.3 adds one PG integration test. Expected **152 full / 24 integration** if all tests are collected and nothing else changes. This is an expectation, not a claim of execution. Signoff requires Windows Python 3.14 + PostgreSQL 16 logs, no skips, no failures, and confirmed collection counts.
