# V1.6 Backend RC1 — not for deployment

Based on V1.5 E2E Fix archive. Additive backend APIs in `backend/app/portfolio_v16/api.py`; no frontend changes, no Neon writes. Existing MES/SRM routes preserved.

## Implemented
- GET `/api/v1/portfolio/capabilities`, `/architecture`, `/mcp/tools`, `/acceptance` (metadata only)
- GET `/mes/work-orders`, `/srm/requisitions`, `/srm/exceptions`, `/mapping/versions`, `/mapping/executions` under `/api/v1/portfolio` (hardcoded projected columns, limit 1–100, read-only transaction, 3s statement timeout)
- All live reads require `PORTFOLIO_READONLY_DATABASE_URL` (separate least-privilege role). Without it, fail closed 503. Never use Neon owner DSN as this variable.
- MCP real invoke is NOT exposed. MCP evidence replay is not yet implemented.

## Not implemented / blocked
- Neon PG18 staging migration verification and real DB integration tests (requires isolated Neon branch and credentials)
- Production reader role grants, row/tenant scoping, approved demo dataset, runtime MCP production hardening
- Work-order detail, cursor pagination, real acceptance evidence ingest, front-end integration

## Tests
From `backend` with required packages: `python -m pytest tests/test_v16_portfolio_contract.py -q`. No previous regression tests need to be rerun now. After PG18 staging gates pass, execute focused integration and regression once.

## Important
Do not push main, change Render settings, execute staging SQL against production, or expose `PORTFOLIO_READONLY_DATABASE_URL` in browser. All staging SQL files are **review candidates**, not approved migrations.
