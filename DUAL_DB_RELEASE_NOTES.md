# V1.5 Dual-Database Integration Candidate

- Security DB: industrial_lab_v15_test; business DB: industrial_lab_v14_test.
- Existing Python 3.14.6, Docker PG16.15. No pip, no venv creation, no 017/018 replay.
- The runner creates test-only NOLOGIN business role (019) and narrow column-level SELECT grants once; never copies V1.4 business data.
- Gateway business transaction uses SET TRANSACTION READ ONLY and SET LOCAL ROLE.
- Five real business adapter tests require five real persisted business rows. Missing rows cause FAIL, never silently skip.
- Audit recovery marks stale RUNNING as UNKNOWN with CAS; does NOT retry business work. This avoids duplicate execution but cannot guarantee exactly-once cross-DB commits.
- Remaining gaps: no standard network MCP transport; no production credential provisioning; no 44-case business golden suite; no durable idempotency key/replay ledger. Production tools remain disabled.
- IMPORTANT: Docker PG16 validation must be run by user; not verified in build container.
