# M3-01 V0.1 Workflow Runtime contract

- PostgreSQL is authoritative; migration `008_workflow_runtime.sql`.
- Supported state chain: CREATED → VALIDATING → CALCULATING → GENERATING_ADVICE → WAITING_REVIEW.
- MRP_COMPLETED requires existing `platform.requirement_runs` row with COMPLETED status. It does not itself run MRP.
- `ADVICE_DRAFTED` only marks a future extension hook; it does not invoke an LLM.
- `event_id` is globally unique; same ID+same type+same payload is deduplicated, changed payload rejected.
- Inbox, instance, audit, outbox are committed atomically.
- `expected_version` supports optimistic concurrency; row-level lock serializes same workflow.
- Outbox is at-least-once; external consumers deduplicate by `message_id`. Acknowledge only after publish.
- No Agent, HITL, approval or ERP PR execution in this release. No background worker in this release.
- Known gaps: no lease-based multi-worker outbox claim, no automatic timer/retry policy, no actor auth, no cross-service delivery.
- Signoff requires real PG16 integration execution and zero skipped mandatory tests.
