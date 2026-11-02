# M1 baseline review — 2026-10-29

## Evidence

- Independent Python golden-case suite: **19 passed** (`backend/tests/test_golden.py`).
- Expected single-order values: ST 40, RT 15, BR 0, HS 20, SC 30, CW 20, RC 10, SH 0.
- Simulated BUY planned receipt amount: CNY 8,700.
- Python implementation handles MOQ by rounding `max(net, MOQ)` to lot multiple. The prior workbook formula `MAX(MOQ,CEILING(net,lot))` needs alignment for non-multiple MOQ cases; golden input does not expose this difference.

## Sign-off disposition

- **Golden single-order calculation baseline: technical verification PASSED**.
- **M1 full acceptance: CONDITIONAL / NOT FINALLY SIGNED**. Reasons: no cross-contract schema review, no implemented workflow/approval/idempotency or multi-order allocation tests; user approval/signatory not recorded.
- **M2-01 engineering bootstrap: STARTED**, with no claim of completed full M2-01 scope.

## Release gates still open

1. Align Excel MOQ/lot formula and recheck independent boundary tests.
2. Implement daily time-phased, multi-order allocation and shared inventory controls.
3. Versioned ERP/WMS/MES schemas, database persistence, seed loaders, and integration contracts.
4. Workflow state machine, approval authorization, PR idempotency and reconciliation tests.
5. User sign-off on frozen contract baseline.

## Interpretation

The golden fixture is a fixed illustrative single-order case. Passing its tests does not validate production manufacturing MRP or platform-wide acceptance.
