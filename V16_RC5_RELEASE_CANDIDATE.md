# V1.6 RC5 — Consolidated Release Candidate (offline build)

## Basis
Complete RC4 source, with existing MES/SRM/Mapping five API endpoints, Workbench, MRP/WMS/Workflow/Agent/MCP code and migrations retained. No production environment modified.

## RC5 changes
- Fail-closed dedicated login name and Neon hostname validation **before** database connection; disallow owner or alternate login DSNs.
- Verify actual PostgreSQL session/current user equals `portfolio_v16_api_limited`; preserve read-only transaction and privileged role checks.
- Capability endpoint does not claim a source configured for an obviously wrong DSN.
- PG18 live gate additionally denies CREATE on MES/SRM/Mapping schemas; checks all five sources and Mapping base table / MES write denial.
- Added RC5 contract tests and single PowerShell selected-gate runner.

## Mandatory blockers / release status
- **NOT production approved**: dedicated Neon login still has no password as last reported; real PG18 login and five live queries not run.
- Cannot automate privileged credential creation without an authenticated admin secret or a supported Neon management integration. No hardcoded or shared passwords, no bypass via `neondb_owner` or `portfolio_v16_api_dev`.
- Full PG16 regression, browser E2E, rollback rehearsal and production branch migration not executed in this environment.
- Prior `neondb_owner` credential was exposed in chat; rotate it before release, after checking dependencies.

## Local commands
`powershell -ExecutionPolicy Bypass -File .\RUN_V16_RC5_GATE.ps1`

For live dev branch only, securely provision the reader credential, set `PORTFOLIO_READONLY_DATABASE_URL` and `V16_DEV_BRANCH_CONFIRMED=dev-v1-6-backend-pg18`, then run with `-LiveNeon`.

**Do not** use production URL for testing. Never upload secrets or env files. Review exposed fields before public release.

## Tests performed in packaging environment
- Targeted contract and security suite: **9 passed**.
- Attempted complete `python -m pytest -q --disable-warnings --maxfail=1`: **BLOCKED at collection** by missing `psycopg` in packaging Python environment (`ModuleNotFoundError`). No claim of full regression.
