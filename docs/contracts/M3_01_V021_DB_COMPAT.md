# M3-01 V0.2.1 | PostgreSQL compatibility patch

- M2 `platform.workflow_instances.instance_id` remains the primary key, preserving `approval_tasks` FK.
- Public Python/API key `workflow_id` maps to SQL `instance_id`; inbox/outbox/audit use `instance_id`.
- `trace_id` is mandatory and created on new workflows. M3 initial version is explicitly 0, without changing existing M2 rows/default 1.
- 008 is a transactional additive migration; 009 continues to add leases, retries and dead letters.
- This patch does **not** assert that PostgreSQL 16 integration tests have passed. Run `run_pg16_gate.ps1` with the isolated disposable test DB and inspect logs.
- Existing tables created by an older incompatible 008 variant (with workflow_id columns) are not automatically rewritten; migration is intended for the supplied M2 baseline schema.
- Reliability tests beyond the existing suite (true simultaneous independent-connection claim, expired-lease reclaim and retry-time validation) remain a release gate.
