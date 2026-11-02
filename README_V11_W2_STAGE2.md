# Industrial AI PaaS Lab V1.1 — W2 Stage 2

## Scope
- Adds optional `order_scope: OrderScope` to `read_integrated_sources` and `run_integrated`.
- Explicit selected-orders are filtered **at SQL read time**, not after MRP computation.
- Missing or unconfirmed selected orders fail closed.
- Explicit scope and sorted effective order IDs are included in `source_versions['v11_order_scope']`, and hence the input fingerprint and persisted JSONB source versions.
- Existing global MRP callers remain unchanged.
- No migration or deployment performed. No new public write route registered.

## Limitations / gates
1. **Only legacy single-line `mock_erp.sales_orders` is executable**. `from_v11_rows` multi-line adapter is not yet wired to the planner; do not claim multi-line execution.
2. No live Neon branch integration test; transaction locks, real DB constraint behavior, and pegging persistence remain unverified for this change.
3. No new API POST route: requires authenticated operator, read-only protection, rate limits, and audit gates before exposure.
4. No schema migration performed. Current explicit scope metadata is embedded in existing `integrated_mrp_payloads.source_versions` JSONB; a normalized `run_order_scope` table can be introduced later after branch migration.
5. Global-mode results continue to use V1.0 hashing semantics when `order_scope` is omitted. Passing an explicit global scope changes the fingerprint intentionally.
6. No idempotency key has been added to the run creation path; repeated runs can create distinct run IDs. A subsequent stage must implement idempotency if required.

## Test
From `backend/`: `PYTHONPATH=. pytest -q -m 'not integration'`
Observed: 149 passed, 5 skipped, 27 deselected.

## Next steps
- Create isolated Neon branch, verify schema and apply migration only if needed.
- Test selected scope under REPEATABLE READ, including missing/unconfirmed orders, hashes, pegging, and rollback.
- Add authenticated endpoint with strict read-only mode and audit after live tests.
- Implement true multi-line order model and allocation lineage separately.
