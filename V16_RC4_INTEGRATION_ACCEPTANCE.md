# V1.6 RC4 — Integrated acceptance candidate

## Based on
Full V1.6 RC3 source; all existing five API paths, migrations and Workbench assets retained.

## Implemented
- Added fail-closed check of actual database login attributes (LOGIN, SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, neon_superuser membership) before any live portfolio query.
- Preserved dedicated reader DSN, read-only transaction, reader role inheritance, static SQL projections, pagination bounds, and fail-closed responses.
- Added an opt-in dev-only PG18 live reader gate for all five sources and privilege boundaries. It makes no writes and requires explicit branch confirmation. The tool never prints credentials.
- Added static contract tests for route preservation and safety guards.

## NOT yet accepted / blockers
- Neon live authentication: `portfolio_v16_api_limited` has no password, so PG18 E2E remains BLOCKED.
- Actual dev branch cannot be proven from hostname alone; verify in Neon console.
- No real Neon integration, frontend browser, PG16 full regression or production deployment claimed by this package.
- Public API exposure and data minimization require explicit review before release.

## Security notes
- Do not put passwords or DSNs into repository, PowerShell history, frontend, or chat.
- Do not use `portfolio_v16_api_dev` or `neondb_owner` for public APIs.
- Do not modify Neon production / Render / GitHub main.
- A real credential is still necessary to authenticate to Postgres; it cannot be safely bypassed.

## Gate commands (isolated dev environment only)
```
cd backend
python -m pytest tests/test_v16_portfolio_contract.py tests/test_v16_rc4_security.py -q
# After secure reader credential provisioning, in isolated dev environment:
# set PORTFOLIO_READONLY_DATABASE_URL and V16_DEV_BRANCH_CONFIRMED=dev-v1-6-backend-pg18
python scripts/v16_rc4_neon_live_gate.py
```
