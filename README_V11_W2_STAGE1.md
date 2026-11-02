# Industrial AI PaaS Lab V1.1 — W2 Stage 1

## Scope

Additive source-only development based on the user's V1.0 Deployment Ready Full archive. No production migrations, no Render deployments, no Neon connections, and no production data changes.

### Added

- `backend/app/erp/models.py`: canonical Pydantic `SalesOrder`, `OrderLine`, `OrderScope` models. Multi-line orders supported as a domain representation.
- `backend/app/erp/adapter.py`: V1.0 single-line order conversion, future V1.1 header/line conversion, strict scope validation, and parameterized read-only legacy queries.
- `backend/app/erp/api.py`: read-only endpoints, GET `/api/v1/erp/sales-orders` and GET `/api/v1/erp/sales-orders/{order_id}`.
- `backend/tests/test_erp_v11_unit.py`: 11 new tests covering models, adapter, scope, parameterization, routing and public read-only perimeter.
- `backend/app/main.py`: append-only router registration.

### Important limitations

- V1.1 header/line tables are **not created**. The `from_v11_rows` adapter is a pure mapping function, not an operational database reader.
- No POST ERP routes are registered. No order writes, confirmations, procurement creation or BOM publication.
- The MRP engine's existing global read semantics are unchanged. Scope validation is not yet connected to actual MRP execution or persisted input hashes.
- Legacy orders are represented as one line; there is no automatic dual-write or backfill.
- API GET routes require a live database matching V1.0 schema. They do not fall back to fabricated data.
- Existing V1.0 MRP, Agent, Workflow, Workbench and audit logic are unchanged.
- No production deployment or PostgreSQL integration tests have been run.

### Test result

Run from `backend/`:

```bash
python -m pytest -q -m 'not integration'
```

Result: **145 passed, 5 skipped, 27 deselected**. `backend/` dependencies must be installed.

### Next gate

1. Create an isolated Neon branch, validate the migration DDL against the branch schema, and test rollback.
2. Design and test transactional multi-line order ingestion, authoritative order identity and line-level genealogy.
3. Integrate selected order scope into `read_integrated_sources` / `run_integrated`, including input hash, result scope, source version, persistence and regression tests.
4. Only then add protected ERP write endpoints with authorization, audit and idempotency.
5. Keep public Render `PUBLIC_READ_ONLY=1` throughout.
