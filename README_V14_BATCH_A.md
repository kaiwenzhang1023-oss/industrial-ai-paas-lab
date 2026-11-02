# Industrial AI PaaS Lab — V1.4 Batch A (SRM)

Source: V1.3 RC2 ZIP copied, **not modified in place**. M0 contract: `Industrial_AI_PaaS_Lab_V1.4_M0_Source_Audited_Contract.md` at package root.

## Scope
- PostgreSQL `srm_v14` schema: suppliers, supplier-items, MRP BUY purchase requisitions, purchase orders/lines, confirmations with delivery schedules, delivery changes (reserved), delay exceptions, audit.
- Source-hash-verified `read_integrated_run()` adapter; BUY-only, no MRP recomputation or upstream writeback.
- HTTP `/api/v1/srm/*`, protected by existing operator dependency and global PUBLIC_READ_ONLY middleware.
- Decimal quantities, source identity fence, stable PR IDs, replay consistency, optimistic PO revisions, transactional rollback.
- **Not Batch A:** Mapping Center implementation, supplier portal, WMS receipt, delivery-change workflow, Workbench SRM UI, production-grade concurrency certification.

## Windows / PowerShell
Start in `m2_pg16_gate` after starting local PostgreSQL 16. Use the existing V1.3 database initialization instructions on a **new** database named `industrial_lab_v14_test`. Apply `database/schema.sql` and numbered schema migrations `003`–`013`, then `database/015_v14_srm_batch_a.sql`. `014_v11_stage3_readonly_checks.sql` is a check script, **not** a schema migration. Do not execute the gate against V1.3 or cloud DB.

### DB connection (copy into each new PowerShell session)
```powershell
$raw = docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' m2_pg16_gate-postgres-1 | Where-Object { $_ -like 'POSTGRES_PASSWORD=*' } | Select-Object -First 1
if (-not $raw) { throw 'Missing Docker POSTGRES_PASSWORD' }
$pw = [uri]::EscapeDataString($raw.Substring(18))
$env:TEST_DATABASE_URL = "postgresql://lab:${pw}@127.0.0.1:5432/industrial_lab_v14_test"
$env:DATABASE_URL = $env:TEST_DATABASE_URL
Remove-Variable raw,pw
```
Verify DB name before executing any migrations or tests. You must initialize source tables and persist a **real integrated MRP run** to exercise the adapter; do not insert fake `plan_lots` into an unrelated MRP result.

### Tests
```powershell
cd .\backend
py -3.14 -m pytest tests/test_srm_v14_batch_a.py -q
py -3.14 -m pytest tests/test_srm_v14_pg16.py -q -rs
```
A skipped integration test **is not a pass**. For HTTP mutation set `DEMO_WRITE_ENABLED=1` only on isolated local environment; never on public deployments. Use `PUBLIC_READ_ONLY=1` for the public read-only test.

## Security and boundaries
The original V1.3 RC2 archive is unchanged. This ZIP includes a complete derived working tree. No production DB migrations were executed in this build environment. The PG16 gate requires execution on the user's Docker PG16 and real persisted MRP run.
