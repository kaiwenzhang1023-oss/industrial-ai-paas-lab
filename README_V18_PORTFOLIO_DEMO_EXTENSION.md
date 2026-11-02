# V1.8 Portfolio Demo Extension — isolated candidate

**Status: local candidate, not deployed.** This ZIP is a derivative of the user-provided `project.zip`; it does not replace the frozen Render commit `8ff838b`.

## What changes
- New `GET /api/v1/portfolio-demo/mrp/golden` returns an in-memory, deterministic EM-100 single-order educational MRP calculation; it performs no DB reads/writes and needs no operator key.
- New `GET /api/v1/portfolio-demo/capabilities` indicates whether isolated operator execution is configured, without exposing the secret.
- Public Workbench MRP view presents the golden example and hides the operator execution form in read-only environments. Isolated writable instances retain the existing operator form and original `X-Operator-Key` verification.
- The demonstration includes BOM edges, net requirements, lead times, planned quantities, single-order demand association, procurement suggestions and SHA-256 snapshot fingerprint.

## Accuracy / scope
- The golden example uses the existing `app.domain.mrp.calculate` and `MATERIALS/BOM`, not the integrated multi-order persisted MRP engine. It is NOT live inventory, actual ERP/WMS data, `platform.requirement_pegs`, persisted `platform.mrp_demand_allocations`, or a database MRP Run.
- Procurement amount covers materials with defined unit prices in the golden model only.
- Existing V1.8 public write prohibition and operator-key validation are unchanged.
- V1.6 Portfolio independent reader remains NOT_CONFIGURED.

## Tests executed in preparation
`PYTHONPATH=. python -m pytest -q tests/test_v18_portfolio_demo_extension.py tests/test_golden.py`: 23 passed.
`node --check backend/app/web/app.js`: passed.
`python -m compileall` on new module and main: passed.
No cloud deployment, browser E2E or full PostgreSQL regression has been performed here. Do not mark extension Final Freeze until complete gates pass.

## Safe next steps
1. Compare this candidate with frozen source and review the diff. Deploy to a NEW isolated preview service/branch only after approval, not the frozen service.
2. Run full existing PostgreSQL and G05/G06 browser gates on the candidate; verify 9 tabs, MRP demo, operator form hidden publicly, 403 on writes, and original operator flow in separate writable test environment.
3. Preserve existing Render Free service, Neon preview branch and all secrets.
