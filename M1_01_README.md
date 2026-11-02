# V1.5 M1-01 full-source candidate (not yet PG16-verified)

Based on V1.4 Batch B Final RC. Original frozen ZIP remains untouched.

Scope: additive 017 migration, six tables, default deny, explicit grants, audit append-only trigger, atomic state+audit CAS, five tools disabled. No HTTP or stdio endpoint, no business writes.

## Windows / Docker

1. Extract this complete source ZIP into a NEW directory.
2. Existing Docker container `m2_pg16_gate-postgres-1` and isolated DB `industrial_lab_v15_test` must exist.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_M1_01_DOCKER_PG16.ps1` for PG16 preflight.
4. Explicitly run `powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_M1_01_DOCKER_PG16.ps1 -ApplyMigration` to apply additive migration ONLY to the isolated DB.
5. For Python tests: create .venv314 with `py -3.14 -m venv .venv314`, install `pytest==9.2.0 psycopg[binary]==3.3.6`, and configure `M1_TEST_DATABASE_URL` privately; then `-RunTests`.

NOTE: Docker preflight assumes `lab` is an existing Docker PostgreSQL user, as observed in M1-00. If not, adapt locally after checking container config; do not assume any password. The SQL is intentionally restricted to the exact test DB name.

## Security limitations / future gates

M1-01 is a foundation candidate, not final release: runtime DB roles, RLS, audit privileged role separation, race/concurrency, backup/rollback, and adversarial permission tests remain required before production. `is_authorized` is SECURITY INVOKER and requires SELECT on governance tables; it must not be granted to untrusted principals without a reviewed access boundary. `receive_call` and `advance_call` require trusted writer only. The test migration is not to be executed on production.

M1-00A and read-only M1-00B were passed by the user's Windows logs. No Docker PG16 instance is available in this ChatGPT container, so M1-01 PG16 results remain NOT_RUN until local evidence is returned.
