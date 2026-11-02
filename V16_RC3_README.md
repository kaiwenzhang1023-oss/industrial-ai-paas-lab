# V1.6 RC3 — Reader Security Gate (development candidate)

## Changes
- Full RC2 source retained; five real read-only APIs and Workbench v16 remain.
- Added Neon dev-only `portfolio_v16_reader NOLOGIN` least-privilege group: MES 1 table, SRM 2 tables, Mapping 2 approved views via `mapping_v14_readonly`.
- API now rejects owner `session_user` even after SET ROLE, requires read-only transaction and membership in `portfolio_v16_reader`.
- Does NOT put secrets in repository or frontend, does NOT change production, Render or GitHub.

## Operator steps
1. In Neon UI choose `dev-v1-6-backend-pg18`, verify database `industrial_lab_demo`. Branch identity is NOT verifiable from SQL database name alone.
2. Review and execute `01_DEV_READER_GRANTS.sql` ONCE. If already exists, inspect, do not blindly rerun.
3. Create an independent LOGIN role using Neon dev branch Roles UI; never paste password into chat or source.
4. Replace placeholder in `02_BIND_NEON_LOGIN_TEMPLATE.sql` with login role name, execute only on dev branch.
5. Run `03_DEV_READER_VERIFY.sql` and actual-login `04_ACTUAL_LOGIN_CHECK.sql`. Expected read true for five sources; base read, write and CREATE false.
6. Set `PORTFOLIO_READONLY_DATABASE_URL` only in a SEPARATE LOCAL/ISOLATED BACKEND process. Must use DEV branch host and new reader LOGIN. Do NOT set Render production variables.
7. Smoke test GET `/api/v1/portfolio/{mes/work-orders,srm/requisitions,srm/exceptions,mapping/versions,mapping/executions}` and `/workbench/v16.html`. Empty data is valid; never seed production for testing.
8. After live API evidence, perform PG18 integration + MCP authorization and full legacy regression before release.

## Blockers
- Neon dev connection and actual login are not available to this build environment: NO live PG18 E2E claimed.
- View definition/columns inspected in SQL source; full data exposure and effective permissions still need actual-login test.
- Backend route is intentionally public read-only; authorization and data sensitivity need a separate review before internet exposure.
- No migrations 021–023 are rerun; they were already applied in dev.
