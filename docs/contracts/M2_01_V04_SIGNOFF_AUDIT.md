# M2-01 V0.4 database integration signoff audit (2026-10-29)

## Decision: NOT SIGNED OFF (environmental + contractual blockers)

- Python tests can execute locally; PostgreSQL-backed tests cannot run without an actual server and `TEST_DATABASE_URL`.
- A test marked SKIPPED is not a passing integration test. Static schema/API contract tests are not substitutes.
- Source system schemas and JSON-backed mock endpoints are currently in the same FastAPI application; this is logical isolation, not separate service deployment.

## Contract findings / fixes required

1. **Snapshot consistency**: `load_snapshot()` executes several reads without an explicit repeatable-read transaction; orders, stock, supply and BOM can represent different points in time. Freeze one consistent snapshot and record source versions.
2. **BOM effective date**: the current BOM query selects using global `as_of`, not each order's material need date. Multiple released versions may duplicate lines. Define per-parent effective selection and overlap rejection.
3. **Inventory reservation**: `reserved + blocked <= on_hand` is enforced in the schema; validate that the two concepts are disjoint in every source adapter.
4. **Receipt eligibility**: current query filters `arrival_date >= as_of`, which omits earlier unconsumed receipts unless represented in opening stock. Define a cutover reconciliation rule.
5. **Atomic seed and run**: source snapshot read and run write are separate transactions. The persisted input hash describes data read, but does not guarantee source data remained unchanged until write.
6. **Pegging**: planning allocation is not WMS physical reservation; separate planned lot surplus from customer gross demand, and verify material/date balance identities.
7. **Error taxonomy**: broad exception handlers return 503 for domain/data errors; differentiate validation, conflict, missing schema and unavailable DB.
8. **Test isolation**: real integration tests currently mutate source tables; use a disposable database, migrations, and deterministic cleanup.

## Required PostgreSQL signoff evidence

- PostgreSQL instance/version and migration execution log.
- Seed twice, verify source counts and unchanged versions for unchanged input.
- Read back all order/BOM/stock/supply records and compare with fixture.
- Run MRP twice, compare input hashes, daily lines and pegging, and verify atomic persistence.
- Inject a write failure and verify no partial run remains.
- Concurrent source update test verifies snapshot policy; multiple BOM version test verifies effective selection.
- Attach pytest output with zero skips for mandatory DB tests.

Until these gates pass, M2-01 is *conditionally accepted for further development*, not finally signed off.
