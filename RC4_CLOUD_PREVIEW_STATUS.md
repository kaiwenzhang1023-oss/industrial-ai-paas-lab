# Version B Cloud Preview RC1 — actual execution report

Date: 2026-11-04

## Neon: COMPLETE (actual connected account changes)
- New project: industrial-ai-paas-v19-version-b-preview (super-glade-55757112)
- New dedicated branch: preview (br-patient-surf-bb9nyu0h)
- PostgreSQL: 16.15 (160015)
- Dedicated database: industrial_v19b_preview
- Migrated 6 SQL files; 9 enterprise tables and 14 source tables.
- Golden fixture: 9 materials, 2 orders, 8 BOM entries and 5 receipts.
- Scoped `v19b_app_runtime` SQL read/write role created; token/password not included in this deliverable.
- Existing Neon projects/branches unchanged.

## Preview adapter: IMPLEMENTED, OFFLINE SMOKE 12/12 PASS
- Dedicated Dockerfile and ASGI entrypoint; legacy app/routes not loaded.
- Guest session HMAC, unique tenant, two hour expiry; no shared operator password.
- Routes limited to Version B API; cross-origin POST forbidden; per-session 25 write attempts and process-local global budget.
- Legacy write endpoints denied.
- Does not connect to external ERP/MES/SRM.

## Not yet verified (HOLD)
- Docker image build on Render; currently no Docker engine in analysis environment.
- GitHub preview branch availability / push (requires Git credential in user environment).
- Render service creation, env config, Neon DB connectivity from Render.
- Public browser→MRP→approval→Worker→receipt→audit E2E and cross-visitor interference.
- Resource cost/compute hours under live visitors and visitor data cleanup.

Do not claim the public cloud deployment has passed until these checks are executed.
