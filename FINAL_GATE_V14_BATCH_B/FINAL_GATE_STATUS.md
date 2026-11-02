# V1.4 Batch B — Final gate evidence (2026-10-31)

**Decision: HOLD — NOT SIGNED OFF.**

## Verified in current runtime
- Source: supplied `M1-03_M1-04_RC_Candidate_Full.zip`.
- Python 3.13.5: `python -m pytest -q tests/mapping tests/test_srm_v14_batch_a.py tests/test_integrated_m2.py tests/test_mes_v13_batch_a.py tests/test_mes_v13_batch_b_contract.py tests/test_mes_v13_batch_c_gate.py tests/test_workflow_unit.py tests/test_workflow_v03_unit.py tests/test_workflow_worker_unit.py`
- Result: **84 passed, 2 skipped** (the two PG16 mapping tests).
- No changes to existing source or migration files; this package only adds final-gate instructions and a script.

## Blocking gates
1. Python 3.14 Windows not tested in this environment.
2. Isolated PG16 test DB `industrial_lab_v14_test` not connected; migration 016 not applied.
3. Existing completed MRP BUY source required by integration test; test currently skips without it. **Any skip is an unpassed gate.**
4. Verify actual `mapping_v14_readonly` privileges using `has_table_privilege` and an effective read-only identity, not only migration text.
5. SRM/MRP/MES/Workflow dedicated PG16 regressions must run with each test DB and their established test prerequisites; not yet executed here.
6. Validate no SRM PR writes by comparing before/after counts and row hashes under isolated PG16 test.

## Safe signoff sequence
- Back up `industrial_lab_v14_test` and confirm its DB identity. Review and explicitly approve applying `database/016_v14_mapping_batch_b.sql` to test DB only. Do not apply to production.
- Configure Python 3.14 and psycopg, set `TEST_DATABASE_URL` to isolated test DB, unset `DATABASE_URL`.
- Ensure a valid existing completed MRP run with BUY plans is available; do not silently seed data in the gate.
- Run `RUN_FINAL_GATE.ps1`, inspect output and **zero skips** for PG16 mapping test.
- Execute dedicated PG16 regression suites in their existing isolated test DBs, with recorded pass/fail evidence.
- Confirm read-only privileges and no business writes with DB queries. Attach SQL results and test logs.
- Only after all critical gates PASS, issue final RC signoff.

**No claims of completed PG16 or final RC signoff are made.**
