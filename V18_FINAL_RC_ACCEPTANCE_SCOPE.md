# V1.8 Final RC — integrated gate and release boundary

This is a **Final Release Candidate**, not a production-certified final release.

## One-shot Windows entry

`RUN_ACCEPTANCE_V18_FINAL_RC.cmd` uses Python 3.14 and runs selected offline tests and local loopback HTTP tests.

Optional isolated PG16 gate: set `V18_ALLOW_ISOLATED_PG16=YES` and `V18_ISOLATED_PG16_DSN` to a PostgreSQL 16 isolated test database. The existing Phase 4 test creates/drops only its own temporary schema. Never supply a production DSN.

Optional browser smoke: set `V18_RUN_BROWSER=YES`, install Playwright and its Chromium browser locally. The test opens Workbench HTML in a real browser and checks render/JS errors; it **does not** certify database-backed interactive E2E. Browser mode is opt-in, to avoid hidden browser installation and external downloads.

## Explicitly not certified

- PG16 live gate: cannot be certified without a reachable PG16 instance and explicit isolated credentials.
- Browser end-to-end: a real API/database-backed interaction is not exercised by static HTML render smoke.
- Full MCP Streamable HTTP specification conformance and OAuth resource-server trust.
- Authorized real adapter network E2E and durable crash recovery with replay guarantees.
- Production: NO-GO. No Neon Production or Render Production access or changes.

The report `acceptance_reports/V18_FINAL_RC_ACCEPTANCE.json` records separate statuses. No pass is inferred for unexecuted gates.
