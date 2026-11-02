# M2 Integration V0.2 — mandatory live PostgreSQL gate

## Status (2026-10-29)
- Python tests: 98 passed, 11 skipped (all skipped tests require PostgreSQL).
- Live PostgreSQL: **NOT EXECUTED**. No server or Docker executable in the current environment; installation attempt timed out.
- M2-01 and M2-02 full-chain signoff: **BLOCKED**.

## Changes
1. `database/007_normalized_pegging.sql`: normalized run-scoped supply sources, demand allocations, plan-child edges; FK and capacity constraints.
2. `app/db/integrated.py`: maps per-run engine receipt IDs to original ERP supply-order IDs, preserves them in JSONB and normalized rows; inserts all rows within same transaction as run and result.
3. `tests/test_pg_contract_v02.py`: live readback counts/conservation, atomic rollback fault injection, two-connection lock timeout, stable source identity across runs.

## Limitations
- ERP mock supply table has a single `supply_id` primary key; it serves as both source document and line identifier in this teaching fixture. Production integrations must carry distinct `source_document_id` and `source_line_id` (plus source_system/tenant) from upstream.
- WMS opening stock remains aggregated by material. Its identity is a planning snapshot pool, not warehouse/lot-level reservation.
- Relational tables preserve plan genealogy, but there is no automated SQL/JSONB cross-check on every read yet; current live test checks row counts and supply conservation.
- The source-table SHARE locks are conservative and can block writers. This is not a production concurrency strategy.
- Schema migrations in `docker-entrypoint-initdb.d` only run for a **new** PostgreSQL data volume. Apply 007 manually to an existing database.

## Execute (isolated DB only)
1. Provision PostgreSQL 16 and create `industrial_lab_test` with user `lab`.
2. Apply `database/schema.sql`, `database/003_v03.sql`, `database/004_snapshot_fence.sql`, `database/006_m2_integration.sql`, `database/007_normalized_pegging.sql` in order. (Do not also run legacy 005 unless explicitly reconciling its definitions.)
3. `cd backend && pip install -e '.[test]'`.
4. `export TEST_DATABASE_URL='postgresql://lab:<password>@localhost:5432/industrial_lab_test'`.
5. `python -m pytest -q -m integration` and `python -m pytest -q`.
6. Signoff requires **zero skipped, zero failed** for PostgreSQL integration tests and a manual review of source identities, rollback evidence and concurrency behavior.

## Known outstanding engineering issues
- Receipt identity must eventually be sourced from explicit immutable ERP document/line IDs, not inferred from `supply_id` equality.
- Need stronger SQL-level demand conservation constraints (aggregate checks require triggers or transactional validation).
- Need failure-injection tests for source snapshot changes during real integrated MRP, not only isolated lock checks.
