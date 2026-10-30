# Industrial AI PaaS Lab V1.0 — release candidate (deployment-ready)

**Scope:** fictional EM-100 MTO educational lab. PostgreSQL-backed data, offline deterministic Agent (`offline-contract-v1`), no external ERP writes, no automatic approval. This package does **not** mean a public URL has already been deployed.

## Fixed V1 blockers

1. **Empty attribution panel:** The M2 integrated MRP run atomically persists `platform.mrp_demand_allocations`, `platform.mrp_supply_sources`, and `platform.mrp_plan_child_edges`, but not the legacy `platform.requirement_pegs` table. V0.2 displayed the legacy table in the top attribution panel, creating an empty view despite normalized allocation rows existing. V1.0 instead aggregates real allocation rows by material, root order, need date, and supply kind (`STOCK`, `RECEIPT`, `PLAN`). The figures represent *allocated supply quantities*, not order gross demand. No synthetic per-order figures are created. Legacy `pegs` remains available in the API for compatibility.
2. **Outbox:** `dispatch_receipts.cmd` runs an **explicit** one-shot PostgreSQL local receipt sink, not the old workflow-advancing scheduler. The worker claims messages with leases, writes an idempotent receipt to `platform.outbox_delivery_receipts`, and marks the outbox message `DELIVERED`. It never advances workflow state, approves advice, or writes ERP. `DELIVERED` means **delivered to the local PostgreSQL receipt sink only**, not delivered to an external broker. Failure and retries are managed by the existing lease/retry engine.

## Windows (no PowerShell execution-policy change for starting or dispatching)

From `m2_pg16_gate`, after the PG16 gate has created `.venv314` and after demo database migration 012:

- `start_local.cmd` — runs localhost workbench with local write operations enabled.
- `dispatch_receipts.cmd` — explicit one-shot receipt processing, safe to re-run. Requires `012_outbox_receipts.sql` in demo DB.

To apply only the **new** migration to an existing demo DB (never rerun all migrations):

```cmd
 docker compose cp database/012_outbox_receipts.sql postgres:/tmp/012_outbox_receipts.sql
 docker compose exec -T postgres psql -U lab -d industrial_lab_demo -v ON_ERROR_STOP=1 -f /tmp/012_outbox_receipts.sql
```

`run_pg16_gate.ps1` still manages the disposable `industrial_lab_test` database and expects **27 PostgreSQL integration tests and 166 full tests**. It does not delete the demo database. Only run it after approving the test DB reset.

## Render deployment blueprint

1. Push the **contents of `m2_pg16_gate/`** to a GitHub repository (do not upload secrets or `.venv314`).
2. In your Render account, create a Blueprint from `render.yaml`. This provisions a Docker web service and managed PostgreSQL. The blueprint may incur charges; confirm the plan and pricing before approval.
3. **Explicit one-time initialization**, in a trusted Render shell/job with `DATABASE_URL` configured:

   ```bash
   cd /app
   CONFIRM_CLOUD_BOOTSTRAP=yes python -m scripts.cloud_bootstrap
   ```

   Bootstrap applies the same ordered migrations as the PG16 gate, seeds **synthetic** orders, creates a single WAITING_REVIEW demo workflow and MRP run, then processes Outbox events to the local receipt sink. It does not approve anything or call ERP.
4. Open `https://<your-render-service>.onrender.com/workbench/`. **The public service is intentionally read-only** (`DEMO_WRITE_ENABLED=0`), so visitors can inspect results without modifying shared data. To support public interactive workflow creation later, separate per-session databases or authenticated, rate-limited tenants are needed; never expose an unrestricted write API.
5. Verify `/api/v1/workbench/snapshot`, `/api/v1/workbench/mrp/<run_id>/details`, and `/api/v1/workbench/outbox/summary`. Verify receipt count and no workflow changes after receipt dispatch.

**Deployment status:** No Render account credentials or authorized deployment session available in this environment. The cloud URL and live PostgreSQL gate must be verified after user-authorized deployment. Do not claim public deployment is complete yet.
