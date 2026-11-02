# M3-01 V0.2 Worker and reliable outbox contract

- DB claim uses `FOR UPDATE SKIP LOCKED` and a bounded lease; separate transaction from callback.
- At-least-once, **not exactly-once**. Publisher consumers MUST deduplicate `message_id`.
- Crash after publish and before ack causes replay; expired lease may be claimed by another worker.
- `finish` checks lease owner and expiry; stale worker cannot ack.
- Retry exponential backoff, max attempts moves to `DEAD`; no automatic replay of DEAD.
- `pump_once` is one bounded execution, not a deployed always-on service. The host must schedule it.
- Auto advance supports CREATED→VALIDATING→CALCULATING; CALCULATING requires injected real M2 runner returning a persisted `mrp_run_id`; the workflow checks persistence before transition.
- No Agent, HITL, broker, ERP write, or scheduled daemon in this version.
- Caveat: Outbox `workflow.state_changed` is an event notification; automatic progression is an explicit orchestrator call, not currently triggered by outbox publication. A later adapter must bind these.
- Live gate: PostgreSQL 16 with 009 migration, all integration tests executed (zero skips). Historical M2 signoff does not imply V0.2 signoff.
