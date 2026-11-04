# V1.9 Version B Cloud Preview RC2

## Major changes
- Added first-class Version B Enterprise Workflow navigation workspace in the existing Workbench; historic static scenario tabs stay untouched.
- Preserved RC1 service-only authenticated enterprise routes, 2h non-persistent visitor bearer sessions and per-visitor unique tenants.
- Browser readiness `/ready` (Neon PG16 schema) is checked before creating a visitor session; if unavailable it fails closed.
- All enterprise API requests use same-origin token with a 30s deadline and explicit errors.
- Cloud RC2 /ready now verifies the database major version is PostgreSQL 16.
- No external ERP/MES/SRM writes.

## Acceptance / release
- This RC2 package is an independent cumulative release, not a patch to the old RC4 Frozen bundle.
- `RUN_PUSH_V19B_RC2.ps1` uses git fast-forward only and the dedicated `v19-version-b-preview` branch.
- Render existing service has autoDeploy=off: after source push, deploy the new commit manually using Render dashboard or connected Render tool.
- NEVER update Render DATABASE_URL or PREVIEW_SESSION_SECRET through commits.
- Run localhost tests in `tests/test_preview_rc2.py`, `tests/browser_rc2.py`; publicly verify /health,/ready,session,tenant isolation, MRP, approval, worker, receipts and audit.
- No claims of cloud acceptance until remote endpoints checked.
