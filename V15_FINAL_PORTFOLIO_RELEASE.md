# Industrial AI PaaS Lab — V1.5 Final Portfolio Release

**Purpose:** personal portfolio and teaching demonstration, not production certification.

## Architecture and evidence boundaries

- **MRP / WMS / MES / SRM / Mapping:** persisted PostgreSQL business data and business adapters.
- **Workflow / Inbox / Outbox:** state transitions, deduplication and event delivery; not automatically connected to V1.5 MCP Gateway in this release.
- **Agent:** separate orchestration/governance implementation; no claim of an autonomous Workflow → Agent → MCP production execution chain.
- **MCP:** trusted in-process `FullGateway` with HMAC identity, resource authorization, separate runtime/business connections, business read-only transactions, durable audit, and default-deny release switch. The stdio protocol entry is separate.
- **Two test databases:** `industrial_lab_v15_test` (MCP runtime/security) and `industrial_lab_v14_test` (business). No cross-database atomicity guarantee.

## Existing test evidence (reported by operator)

- V1.2: 23 passed; V1.3 MES: 4 passed twice; V1.4 SRM: 6 passed.
- V1.5 MCP integrated gate (five files): operator reported PASS.
- V1.5 remaining three files: 98 passed, 0 skipped.
- These are separate executions, not a single complete official release-gate execution.

## Portfolio release changes

1. `020_v15_request_ledger_test.sql`: guarded policy creation; existing policy must match expected role, permissive ALL, USING true, WITH CHECK true or migration fails closed. No DROP or table recreation.
2. `test_v15_portfolio_migration_contract.py`: static SQL contract test.
3. `test_v15_portfolio_authorized_e2e_pg16.py`: **opt-in** real authorized gateway-to-adapter PG16 E2E for five tools plus a denial. No mocks; requires persisted records and authorization fixture, cleaned after test. Durable append-only audit remains as evidence.

## Operator validation — DO NOT RUN against production

Use **Python 3.14.6**, PG16 container `m2_pg16_gate-postgres-1`, and confirm both database names. The existing 019/020 migration conditions have been reported as satisfied; do not rerun migrations simply to validate this package.

From project root, set `M1_TEST_DATABASE_URL` and `V15_BUSINESS_DATABASE_URL` to the two isolated test databases, and `PYTHONPATH` to `backend`. Do not print database passwords. Then run:

```powershell
py -3.14 -m pytest -q backend/tests/test_v15_portfolio_migration_contract.py
$env:V15_PORTFOLIO_E2E='1'
py -3.14 -m pytest -v -s backend/tests/test_v15_portfolio_authorized_e2e_pg16.py
if ($LASTEXITCODE -ne 0) { throw 'PORTFOLIO E2E NOT CERTIFIED' }
Remove-Item Env:V15_PORTFOLIO_E2E -ErrorAction SilentlyContinue
```

**Before running the real E2E**, ensure all five source queries return persisted records, including SRM requisitions and MES work orders. Missing records cause an explicit failure, never a skip. Business adapters are called through `FullGateway` with actual authorization; results are non-null and terminal state/audit checked. No claim of E2E PASS is made until this runs successfully on the operator's PG16 instance.

## Release decision

**Candidate pending operator PG16 E2E evidence.** No production readiness, real autonomous Agent→MCP chain, or real authorized E2E is claimed in advance. Preserve previous passed test evidence and avoid rerunning unrelated suites.
