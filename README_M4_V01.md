# M4 V0.1 — Industrial AI Business Workbench

## Status

**Release candidate; NOT signed off on Windows/PostgreSQL 16.**

Baseline: M3-02 V0.3, 152 full regression and 24 PostgreSQL integration tests confirmed by the user. This release adds 3 unit tests and 1 PostgreSQL integration test. **Expected gate: 156 full / 25 PostgreSQL integration.** Only non-integration tests have been executed in the packaging environment: **126 passed, 5 skipped, 25 deselected**. The 5 skips are historical tests in non-PG mode; they are not acceptable in the full PG gate.

## Delivered

- A responsive Chinese-language industrial business workbench at `http://127.0.0.1:8000/workbench/`.
- Six sections: overview, sales orders, effective BOM and inventory, MRP runs, Agent drafts, workflow and audit.
- PostgreSQL-backed snapshot endpoint; no silent JSON fallback.
- Explicit workflow creation for confirmed orders; version-fenced demo step actions for START, operator-acknowledged validation, durable MRP calculation, and Agent draft generation.
- Workflow history, Outbox and tool audit read views. No ERP purchase write, no auto approval, no real LLM, no production authentication.
- Existing M2/M3 endpoint contracts left unchanged; M4 routes are added under `/api/v1/workbench`.

## Windows PowerShell — clean isolated demo setup

Open PowerShell **in `m2_pg16_gate`**:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\run_pg16_gate.ps1
# After the 25/156 gate succeeds:
.\setup_workbench_demo.ps1
.\start_workbench.ps1
```

Open `http://127.0.0.1:8000/workbench/` in your browser. `start_workbench.ps1` binds only to localhost and uses the dedicated `industrial_lab_demo` DB. `setup_workbench_demo.ps1` creates that database only if missing; it does not drop the demo DB. It applies the historical migrations and seeds sample orders, materials, inventory and effective BOM. Do not point `DATABASE_URL` to an important database. Repeated setup on a preexisting DB has not been verified for all historical migrations; initialize once on a fresh demo DB.

To see test logs from **either** `m2_pg16_gate` or `m2_pg16_gate/backend`:

```powershell
$root = if (Test-Path '.\pg16_integration.log') { '.' } elseif (Test-Path '..\pg16_integration.log') { '..' } else { throw 'No PG gate logs found' }
Get-Content (Join-Path $root 'pg16_integration.log') -Tail 15
Get-Content (Join-Path $root 'pg16_full_regression.log') -Tail 15
```

**Important:** `run_pg16_gate.ps1` drops and recreates only `industrial_lab_test`. Do not store important data in that database. The demo DB `industrial_lab_demo` is separate from the test DB.

## Scope limits / M4 V0.2 backlog

- UI shows a flat effective BOM line list, not a collapsible multilevel BOM tree.
- Agent is a deterministic offline contract model; no LLM/MCP protocol server.
- Operator validation is an explicit demo action, not a real external ERP verification.
- No approve/reject UI or purchase request writing. `WAITING_REVIEW` is terminal for this M4 V0.1 demo.
- Demo has no authentication/authorization. Do not expose it to the public internet. Production deployment requires auth, tenant isolation, rate limits, audit and secret management.
- Workbench lists are capped at 30–300 records per query; pagination is future work.
- For public demo, M4 V0.2 should add safe reset/seed and controlled review action without ERP write.

## Contracts

- M2 MRP `mrp_lines` has no `kind` field; Agent derives BUY/MAKE from `mock_erp.materials`.
- `WORKFLOW_CREATED` and `START` generate distinct Outbox events; duplicate START must not create an extra event.
- Agent draft, successful tool audit and workflow event commit atomically.
- M2 integrated MRP covers all confirmed orders; purchase quantity is not attributed to one order without pegging evidence.
