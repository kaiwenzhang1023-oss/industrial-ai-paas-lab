# Dual DB integrated gate correction
- Previous full_batch_pg16 test mistakenly used V1.5 security connection for V1.4 business reads.
- The five adapter tests now open V15_BUSINESS_DATABASE_URL and use SET LOCAL ROLE mcp_v15_business_reader_test.
- Gateway itself enforces the same restricted business role before executing business adapters.
- Empty business tables produce explicit SKIP rather than a false success.
- Existing 017/018/019 migrations are not replayed when the role/function checks pass.
- Docker PG16 verification requires running RUN_V15_FULL_GATE.ps1 on the user's machine; no Docker success is claimed here.
