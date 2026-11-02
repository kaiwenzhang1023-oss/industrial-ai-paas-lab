# V1.5 M1-01 Final + M1-02 Gateway Foundation — integrated candidate

## Delivery scope
- Full source tree, not patch. Frozen V1.4 modules retained.
- Existing 017 migration untouched. New 018 creates NOLOGIN test roles, revokes PUBLIC, exposes narrow SECURITY DEFINER wrappers, enables RLS with no low-role policies.
- New MCP gateway/registry has five explicit disabled tool specifications, trusted-identity interface, deterministic JSON argument hash, and atomic RECEIVED→DENIED audit. No business execution.
- PG16 tests exercise direct DML denial, legacy function denial, role-specific grants, RLS enabled, business schema write denial, deny-only gateway and rollback.
- Previous PG16 5+4 tests included in integrated runner. No new Python installation or V1.4 migration.

## Critical boundary
This is **not** production-grade HTTP JWT validation, full MCP SDK transport, timeout worker or business adapter integration. Those require separate implementation and tests; do not infer otherwise. The 018 SECURITY DEFINER wrappers must be called only after trusted identity validation by the gateway/launcher. The database runtime role is not a safe public client credential.

## Run
In new extracted directory, preserve previously configured M1_TEST_DATABASE_URL (Docker test DB only):
`powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_V15_M1_01_M1_02_INTEGRATED_GATE.ps1`

If existing venv is elsewhere, pass `-PythonPath 'D:\...\.venv314\Scripts\python.exe'`.

Do not use a production DB. Script checks PG16 and test DB. 018 is additive and re-runnable; does not touch 017 or frozen V1.4. Tests intentionally roll back new records; previous committed CAS evidence remains.

## Acceptance
Code syntax checks in build environment are not a substitute for user Docker PG16 results. All five business tools stay disabled. Record exact pytest output before signing off.
