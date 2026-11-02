# Industrial AI PaaS Lab V1.8 — C4.3 Full Source Release

## Included

- `backend/app/mcp_v18/auth.py`: trusted in-process opaque token registry, immutable verified identity, expiry and revocation.
- `backend/app/mcp_v18/http_transport.py`: loopback-only HTTP host with per-request authentication, identity-bound sessions, session TTL and identity-bound DELETE.
- `backend/app/mcp_v18/secure_bridge.py`: bridge allowlist, scope enforcement, tenant/principal-scoped idempotency and no automatic replay of ambiguous calls.
- `backend/tests/test_v18_c43_identity_isolation.py`: C4.3 security regression cases.
- `C43_SECURITY_ARCHITECTURE.md`: trust model, call boundary, known limitations.
- `RUN_C43_FULL_GATE.ps1`: Python 3.14 focused and broad offline gates.
- `RUN_C43_DOCKER_SECURITY_GATE.ps1`: fresh image build and isolated runtime security check.

## Offline verification performed in build sandbox

- `compileall`: PASS.
- Focused MCP/C4.3 regression: 70 passed.
- Broad offline regression: 396 passed, 12 skipped, 6 deselected.

The build sandbox used Python 3.13.5, not Python 3.14. The Dockerfile now uses `python:3.14-slim`; the included Windows gate explicitly requires Python 3.14.

## Mandatory remaining verification

- Run `RUN_C43_FULL_GATE.ps1` with Python 3.14 on the user's Windows environment.
- Run isolated PostgreSQL 16 live integration and existing PG16 regression gates.
- Run Chromium browser E2E if browser acceptance is required.
- Build a fresh C4.3 Docker image and run `RUN_C43_DOCKER_SECURITY_GATE.ps1`.
- Do not reuse the old Stage B image as C4.3 provenance evidence.

## Release status

C4.3 implementation candidate; offline regression passed. Full release acceptance pending user-side Python 3.14, PG16 and fresh Docker verification. Production remains NO-GO until all required gates pass.


## Compatibility repair included

- Route contract checks now use the effective OpenAPI path map, avoiding false negatives from FastAPI deferred included-router objects.
- Docker runtime smoke now checks both `/api/v1/portfolio/mcp/tools` and `/api/v1/workbench/snapshot` through OpenAPI while continuing to assert that no public `/mcp` endpoint is exposed.
- Durable-ledger WAL initialization now retries transient SQLite lock contention during concurrent startup.
- See `C43_COMPATIBILITY_REPAIR_NOTES.md` for exact verification scope and remaining release gates.
