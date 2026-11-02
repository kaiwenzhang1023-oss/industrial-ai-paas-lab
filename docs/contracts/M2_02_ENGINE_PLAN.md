# M2-02 | Manufacturing MRP engine deepening — implementation contract draft

## Goal
Time-phased multi-order MRP with explicit source provenance, deterministic allocation, valid BOM version selection and auditable planned-order pegging.

## Implementation sequence

1. **M2-02-01 snapshot fence**: consistent read transaction; source record versions and mapping/rule versions in run header; immutable input fixture.
2. **M2-02-02 effective BOM**: select released BOM per parent and effective need date, reject overlap, missing BOM, cycle and invalid units; apply correct component need date.
3. **M2-02-03 supply ledger**: distinguish stock, eligible firm receipts, planned receipts, reservations and blocked quantities; prevent double allocation across orders.
4. **M2-02-04 lot / MOQ pegging**: separate customer gross demand from rounded planned lot surplus, carry surplus to later time buckets, propagate MAKE full planned quantity into component demand.
5. **M2-02-05 tests and API**: snapshot/hash reproducibility, date/priority/ID ordering, same-day competition, late receipts, multi-version BOM, stock changes, negative release date risks and recovery.

## Release gates
- Independent golden expected outputs for SO-2026-001 and SO-2026-002.
- Conservation: for every peg `gross = stock + firm_receipts + planned`, with nonnegative components; daily aggregate reconciles to order pegs.
- No reuse of inventory/receipts across orders; lot surplus persists in projected inventory.
- Per-order BOM effective version selected by dated requirements; deterministic results for identical input.
- PostgreSQL integration tests executed against an actual isolated DB, not skipped.

Do not mark these features implemented until their code and executable tests exist.
