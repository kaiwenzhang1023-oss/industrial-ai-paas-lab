# M4 V0.2 — End-to-End Industrial AI Business Demonstration

**Baseline:** frozen M4 V0.1.1. This is a full project package, not a patch. Python 3.14.x, PostgreSQL 16, Windows PowerShell.

## Delivered

- MRP run detail (`GET /api/v1/workbench/mrp/{run_id}/details`): persisted integrated M2 `result_json.mrp_lines`, order pegging, normalized allocation, supply ledger, BOM parent-child edges, immutable result hash and snapshot. The M2 integrated engine does **not** populate the older `platform.material_requirements` table; the UI intentionally reads the correct immutable integrated payload. No browser-side MRP computation.
- Agent: human-readable BUY recommendation rows, quantities, reasons, risk disclaimer, and expandable raw JSON. `offline-contract-v1` is **not an online LLM**. No ERP purchase requests, no automatic approvals.
- Workflow: state timeline; **create and advance now force-refresh while the action lock is held** (fixes V0.1.1 stale UI). Version fencing and all existing backend transitions preserved.
- Outbox: summary by real persisted status, attempts, last error, delivered time; PENDING is **not** DELIVERED. Web server **does not** automatically run the worker (doing so would auto-advance newly created workflows).
- Demo setup PowerShell empty-result handling fixed using `SELECT CASE WHEN EXISTS ... THEN 1 ELSE 0 END`.

## Windows execution

Extract the whole ZIP into a **new directory**. In `m2_pg16_gate`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\run_pg16_gate.ps1
```

Expected **26 PostgreSQL integration tests / 161 full regression tests**, zero failures and zero skipped in the PostgreSQL gate. This gate recreates **only** `industrial_lab_test`; do not store valuable data there.

**Existing M4 V0.1.1 demo database:** If the existing `industrial_lab_demo` is running in the same Docker Compose project, it may be reused by the new version, without rerunning migrations or reseeding. For a fresh database only, execute `./setup_workbench_demo.ps1` (PowerShell ` .\setup_workbench_demo.ps1 `) once. Avoid running setup again on an already migrated demo DB; historical migrations have not all been certified idempotent.

```powershell
.\start_workbench.ps1
```

Open `http://127.0.0.1:8000/workbench/`. If Windows reports WinError 10048, **an older Uvicorn process already owns port 8000**. Stop that specific process before launching this version. Refresh the browser with Ctrl+F5 to clear old static JS/CSS.

## Demo acceptance walkthrough

1. Open MRP page and click **查看计算详情** on the completed `WFMRP-*` run. Inspect real material gross/net/planned quantities, order allocations, BOM lineage and supply sources. MRP is a **global all-confirmed-orders** plan, not one-order purchasing.
2. Open Agent and click **查看明细**. Verify readable BUY rows and expandable raw JSON, MRP link, WAITING_REVIEW.
3. Open Workflow and Audit. Check the five-state timeline and four versioned audit transitions. Inspect Outbox statuses and tool call audit.
4. For a new confirmed order workflow, create and advance once. Confirm the UI updates without a separate refresh click.
5. Worker delivery verification is **separate and optional**: the existing `app.workflow.scheduler` worker may be explicitly started on a disposable demonstration database, but it can automatically advance eligible workflows. Do **not** start it on the already manually verified business flow unless that effect is intended. The dashboard is an accurate observer, not a fake delivery simulator.

## Acceptance limits

Local non-PostgreSQL suite is executed during build. The Windows Docker/PostgreSQL gate and browser verification must still be run by the user; the package is **not** signed off merely because the ZIP was created. No production ERP integration or online LLM is claimed.
