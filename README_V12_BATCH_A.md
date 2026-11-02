# V1.2 Batch A — WMS/MRP planning-only stock provenance

## Completed
- Verified Neon WMS inventory contract from user-provided read-only query results: 9 materials, 9 rows, WH-A, total available 505; zero invalid quantities, missing ERP materials, duplicate keys.
- Retains existing deterministic MRP calculation and original `platform.mrp_supply_sources` normalized schema.
- Adds `app/wms/provenance.py` to attribute STOCK demand allocations to warehouse/lot balance rows in deterministic warehouse/lot order, with quantity conservation and fail-closed on insufficient source stock.
- Persists `wms_stock_attribution` and `wms_stock_attribution_contract` inside **new** `platform.integrated_mrp_payloads.result_json`; existing historic results are untouched. This is *simulated planning attribution*, **not WMS reservation, actual picking, physical inventory movement or proof of warehouse feasibility**.
- Adds `v12_inventory_balance_hash` to new run `source_versions` / input hash, including row quantities, snapshot and version; preserves source-row version metadata.
- Seven new offline tests for multiwarehouse/multilot, deterministic ordering, reserved/blocked, shortages, conservation, duplicates and negative available.

## Boundaries / risks
- Current Neon Free plan prevents creation of child branch from frozen V1.1 branch. **No database migrations or database write tests have been run.** Do not run new MRP POST against the frozen V1.1 branch or production.
- The new provenance is stored in JSONB for new runs, not a separate relational provenance table. If later required for complex queries, design an additive migration only after isolated branch approval.
- Current test fixture is single warehouse WH-A with empty lot IDs and zero reserved/blocked; multiwarehouse/multilot validation is offline-only.
- Existing MRP `STOCK` normalized source remains PLANNER and is not mislabeled WMS; the separate provenance field carries the planning attribution.
- Existing W3 UI is unchanged; Workbench stock-provenance visualization belongs to Batch B.
- New runs intentionally have new input/result hashes because provenance and balance-content fingerprint are now part of the immutable evidence; old hashes remain unchanged.

## Windows offline acceptance
From `m2_pg16_gate/backend`:
```
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -e ".[test]"
.\.venv314\Scripts\python.exe -m pytest -q -m "not integration"
```
Expected in this build environment: 175 passed, 5 skipped, 31 deselected. Windows must be checked separately.

## Next
- Obtain a separate Neon isolated write-test environment (new project if branch quota prevents new branch); do not touch frozen V1.1 branch.
- Verify integrated MRP end-to-end, hash integrity and planning-only lot evidence against isolated test fixtures.
- Batch B: WMS inventory and stock attribution in Workbench, browser validation and final version freeze.
