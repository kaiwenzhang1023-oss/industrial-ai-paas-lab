# V1.6 staging-only migration candidates

These are copies of the original V1.3/V1.4 DDL for isolated review; **not PG18-certified** and **not production-ready**. Do not run blindly. Mapping DDL contains role creation and trigger drops/recreates; assess privileges and second-run behavior. MES/SRM FK targets must be inspected on the target branch. No automatic migrations are wired into Docker startup. MCP V1.5 test-only migrations are intentionally excluded. No production credentials or test role reuse.

Gate: Neon isolated branch -> full read-only inventory -> reviewed DDL -> transactional migration on isolated branch -> repeatability + rollback -> role grants -> API integration -> regression -> explicit production approval.
