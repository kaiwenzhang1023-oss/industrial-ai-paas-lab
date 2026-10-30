# M3-01 V0.3 — Worker scheduler, M2 runner, reliability gate

## Delivered
- Polling Worker CLI: `python -m app.workflow.scheduler --as-of 2026-11-20 --interval 1`.
- PostgreSQL outbox claim/finish reuse from V0.2.1; no external broker or ERP write.
- Creating a workflow now inserts an initial `WORKFLOW_CREATED` Inbox event and corresponding Outbox event in the same transaction; no schema migration needed.
- Each state-change notification advances at most one state. Current persisted workflow version fences stale notifications.
- `CALCULATING` invokes M2 `run_integrated` (real DB-driven versioned BOM, supply allocation and pegging) and requires persisted `COMPLETED` result.
- Stable MRP run ID derived from workflow ID and planning date allows replay after a crash; existing run is validated through `read_integrated_run` including result hash.
- CLI supports graceful SIGINT/SIGTERM stop, interval, owner and bounded cycles.

## Limitations and known risks
- M2 integrated runner calculates **all confirmed orders**, not only the workflow's order; membership is verified. Order-scoped MRP is a later requirement.
- At-least-once, not exactly-once. No distributed broker or external ERP side effects.
- If multiple workers run the same MRP simultaneously, one may hit a unique-key race; retry on the next poll, with no duplicate committed run.
- No lease heartbeat for processing exceeding lease duration. **Do not run with a large MRP dataset until heartbeat or lease extension is implemented.**
- Source changes after a completed deterministic run are not automatically recomputed; replan requires a new workflow or explicit new planning generation.
- `GENERATING_ADVICE` remains blocked until M3-02 Agent Harness is implemented.
- The current M2 snapshot may have non-workflow orders and must not be treated as an order-exclusive recommendation.

## Mandatory real PostgreSQL 16 acceptance
- Full regression and integration marker both exit 0 with 0 skips.
- Two independent DB connections race to claim messages; no message is claimed twice in the same lease.
- Expired lease can be reclaimed; old worker cannot acknowledge.
- Retry backoff is enforced; max attempts reaches DEAD and DEAD cannot be reclaimed.
- MRP run persisted; repeated runner invocation returns same run ID and hash-valid payload.
- Replayed stale notifications do not advance the state.
- Review full logs and sign off only after all tests actually ran against PostgreSQL 16.

## Windows quickstart
1. Unzip to a new folder.
2. Open PowerShell **in the ZIP root** and run `Set-ExecutionPolicy -Scope Process Bypass` then `.\run_pg16_gate.ps1`.
3. The gate rebuilds the **disposable** `industrial_lab_test` DB; never run against business data.
4. After gate passes, run a worker against a separately prepared demo DB. Set `DATABASE_URL` first. Example:
   `$env:DATABASE_URL='postgresql://lab:local_demo_only@localhost:5432/industrial_lab'`
   `cd .\m2_pg16_gate\backend`
   `.\.venv314\Scripts\python.exe -m app.workflow.scheduler --as-of 2026-11-20`
5. The worker does not seed the demo DB or create a workflow automatically. These must be done explicitly via API or setup.
