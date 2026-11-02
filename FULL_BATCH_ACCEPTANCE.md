# V1.5 MCP Integration Full Batch — candidate / release disabled

## Source basis
Exact predecessor: `Industrial_AI_PaaS_Lab_V1.5_M1-01_Final_M1-02_Integrated_Full_Candidate.zip`. No changes to V1.4 frozen business modules or 017/018 migration.

## Implemented
- Five **real, read-only** adapters: MRP persisted integrated run + fingerprint, WMS inventory summary, MES persisted work-order, SRM requisitions scoped by MRP run, Mapping B01 preview based on persisted MRP and ERP material snapshot.
- HMAC-SHA256 authenticated tenant/principal token; signed expiry, strict argument allowlist; no caller-supplied identity fields.
- PG16 runtime role `mcp_v15_runtime_test` for authorization and CAS audit; separate trusted read-only business transaction.
- RECEIVED → DENIED, or RECEIVED → AUTHORIZED → RUNNING → COMPLETED/FAILED/TIMED_OUT. Errors do not expose database exceptions. Timeout uses PostgreSQL `statement_timeout` plus elapsed deadline check.
- All tools **disabled by default** (`FullGateway(..., release_enabled=False)`). Explicit opt-in is for isolated test harnesses, not a production release toggle.
- One-shot PowerShell runner automatically recovers Docker PG16 test DSN and reuses Python **3.14.6** venv. No 017/018 rerun, no pip install.

## Important limitations / release blockers
1. **NOT a network MCP transport**: in-process orchestrator only. No stdio/HTTP MCP JSON-RPC handshake or discovery exposed to agents.
2. The trusted host still controls the database owner connection. Dedicated least-privileged business reader role and true service account identity boundary require production hardening.
3. The security DB functions `runtime_receive` and `runtime_advance` accept caller parameters; HMAC checks happen in the trusted Python host, not inside PostgreSQL. Do not expose the DB runtime role to untrusted clients.
4. Timeouts cannot cancel external services (there are none here); no durable idempotent retry or crash recovery worker implemented. An interrupted call can remain RUNNING; this is **not** final M1-04 reliability acceptance.
5. PG16 test coverage includes real adapter queries when corresponding business rows exist, but does not prove **five authorized success paths** without real seeded resources and grants. This remains a hard release blocker.
6. Golden Cases count from project plan is not certified here. 47 new parameterized security/contract unit checks are **not** a substitute for 44 domain golden cases.
7. Docker PG16 execution is performed on the user's Windows host; this build environment cannot claim the Docker gate passed.

## Execution
Unzip as sibling of `Industrial_AI_PaaS_Lab_V1.5_M1-01_Full_Source_Candidate`. From new folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_V15_FULL_GATE.ps1
```

If your existing venv is elsewhere, add `-PythonPath "D:\...\.venv314\Scripts\python.exe"`.

## Release decision
**CANDIDATE / NO-GO** until PG16 results, five authorized real-data E2E cases, recovery, and network MCP transport are complete. Do not enable the five business tools in deployment.

## Compatibility correction (2026-10-31)
The first Full Batch candidate failed pytest collection on the existing Windows
Python 3.14.6 environment because importing `app.wms.adapter` required the
optional `pydantic` package. The MCP WMS read-only adapter now queries the
existing `mock_wms.inventory_balances` table directly, preserving the inventory
summary fields and JSON-compatible output without importing Pydantic. The
original WMS models/adapter remain untouched. A fresh-process import test blocks
Pydantic deliberately to prevent recurrence. No pip, migration, or venv changes.
This correction is not a claim of Windows Docker PG16 acceptance.
