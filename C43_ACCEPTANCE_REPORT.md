# C4.3 Acceptance Report

## Build identity

- Source baseline: `Industrial_AI_PaaS_Lab_V1.8_Final_RC_Route_Compatibility_Fix_Full_Source.zip`
- Change set: C4.3 identity resolver, immutable identity, per-request re-authentication, tenant/principal/scope-bound sessions, session TTL, identity-bound DELETE, secure bridge call binding, tests, Python 3.14 non-root Dockerfile.
- Python used for offline checks: 3.13.5 in the build sandbox. The project Dockerfile and user-side gate target Python 3.14. Docker build/runtime was not executed in this sandbox because Docker CLI/daemon is unavailable.

## Offline test results

- Focused C4.3 + V1.8 MCP regressions: **70 passed**.
- Broad offline regression: **396 passed, 12 skipped, 6 deselected**.
- The broad command excludes database-backed files that require `psycopg`/isolated PostgreSQL and the browser test that requires an installed Chromium executable.
- A first broad attempt including browser test produced one environment failure because Playwright Chromium was not installed. This is not reported as a product test pass.

## Not run / not certified

- PostgreSQL 16 live integration and schema/ledger tests.
- Python 3.14 execution in this build sandbox (user-side Docker base is set to Python 3.14).
- Real Chromium browser E2E.
- Full MCP Streamable HTTP conformance suite.
- Enterprise OAuth/OIDC provider integration.
- Production business-adapter E2E and penetration testing.

## Source/runtime provenance warning

The C4.2 terminal output supplied by the user reported an active Docker image running Python 3.14.10 and MCP files `streamable_http.py`, `batch_b_local.py`, and `local_host.py`. Those files are not present in the supplied V1.8 Final RC Route Compatibility Fix source ZIP's `backend/app/mcp_v18` tree; that ZIP instead contains `http_transport.py`, `secure_bridge.py`, `durable_ledger.py`, `pg_ledger.py`, and `recovery.py`. The supplied ZIP's original Dockerfile also declared Python 3.13. The C4.3 package aligns the Dockerfile to Python 3.14 and is built from the supplied ZIP, but the previously running Stage B image must not be treated as a build artifact from this source ZIP. Rebuild a fresh C4.3 image from this package and compare its image digest/source commit before deployment.

## Signoff

C4.3 code-level offline regression: PASS.
Full V1.8 release acceptance: **PENDING** isolated PG16, Python 3.14 user-side gate, fresh Docker image verification and any required external conformance tests.
Production: **NO-GO** until all required gates are independently passed.


## Compatibility repair follow-up

The supplied user's first C4.3 gate reported 68 passed / 2 failed because two assertions inspected only top-level `app.routes`. A recursive route diagnostic subsequently found both routes, and direct HTTP checks returned Portfolio MCP HTTP 200 and Workbench Snapshot HTTP 503 (`WORKBENCH_DATABASE_UNAVAILABLE`, expected without DB credentials). The source tests and Docker smoke were corrected to use the effective OpenAPI route map.

A concurrent SQLite WAL startup race was also exposed by the focused suite. WAL configuration now runs at ledger initialization with bounded retry for transient lock contention. After this change, focused tests passed **70/70**, broad offline tests passed **396/396 with 12 skipped and 6 deselected**, and the concurrent ledger test passed five additional repeated runs.

These follow-up checks were run using Python 3.13.5 and FastAPI 0.128.2 in the build sandbox. They do not replace the required Python 3.14 / FastAPI 0.162.0 Windows run, live PostgreSQL 16 integration, or fresh Docker build/runtime gate.
