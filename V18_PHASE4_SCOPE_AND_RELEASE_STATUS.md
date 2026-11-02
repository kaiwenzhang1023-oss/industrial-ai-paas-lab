# V1.8 Phase 4 Integration Candidate

- Based on V1.8 Phase 3 full source, preserving all existing modules.
- Added opt-in isolated PG16 idempotency ledger live gate. It creates and drops only a randomly named schema in a DB ending `_test` or `_isolated`, verifies PostgreSQL major version 16, and never targets production. It requires explicit `V18_ALLOW_ISOLATED_PG16=YES` and `V18_ISOLATED_PG16_DSN` environment variables. **Not executed in the build environment.**
- Added real loopback HTTP request tests for token, Origin, handshake, and fail-closed calls; and Workbench route/static asset smoke. These are **not** real-browser UX tests.
- One-shot Windows entry: `RUN_ACCEPTANCE_V18_PHASE4.cmd`.
- Production: **NO-GO**. Missing full MCP Streamable HTTP conformance, externally trusted OAuth/resource-server authentication, proven PG16 live gate, browser E2E, crash replay policy, and real authorized adapter network E2E.
- Never mount development MCP server on public Render or Neon Production.
