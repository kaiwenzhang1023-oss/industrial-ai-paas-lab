# Industrial AI PaaS Lab V1.7 Final RC — acceptance boundary

This is a **Final Release Candidate**, not a production-ready final release.

## Verified in this build environment
- 74 selected offline tests passed (Python pytest): MCP HTTP loopback request/response, bearer rejection, initialize/notification/tools/list, disabled tools/call, invalid route, fail-closed recovery classification, Workbench static contract, and preserved V1.5/V1.6 selected contract/security checks.
- No Neon or production access was used; no migrations executed.

## Single Windows entry point
From the extracted project root run `RUN_ACCEPTANCE.cmd` (or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ACCEPT_V17_FINAL.ps1`).
The report is `acceptance_reports/V17_FINAL_ACCEPTANCE.json`.

Optional `-LivePG16` requires **isolated** test DB DSNs in `M1_TEST_DATABASE_URL` and `V15_BUSINESS_DATABASE_URL` and performs the authorized V1.5 E2E, which writes test authorization/audit records. It is intentionally not run by default. Do not use production credentials.

## Unverified / out of scope
- Real Windows runtime and actual PostgreSQL 16 integration (until user runs them).
- Browser rendering and user interactions; static contract alone is not browser acceptance.
- Production-grade MCP Streamable HTTP (OAuth, SSE, resumability, multi-worker session storage) and automatic crash recovery.
- Production deployment. Local HTTP listener remains loopback-only and disabled for business execution by default.

## Safe defaults
No Neon credential required. No changes to Neon, Render, or frozen V1.5/V1.6. The command launcher is intended for trusted source only.
