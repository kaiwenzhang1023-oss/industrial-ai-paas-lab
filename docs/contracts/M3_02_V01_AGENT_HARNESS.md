# M3-02 V0.1 | Agent Harness + MCP business tool governance

## Contract and boundary
- M2 persisted PostgreSQL MRP is the **only** source of numeric planning truth.
- Existing M2 integrated run is **global across confirmed orders**. V0.1 suggestion is **run-level**, not an order-specific purchase requisition. No fabricated order allocation.
- Only registered read-only tools (`order.read`, `bom.read`, `inventory.read`, `mrp.read`) can be invoked by the recommendation agent. The V0.1 adapter actually wires **mrp.read only**; other registry entries are reserved and deny access without an adapter.
- The tool gateway is an in-process MCP-style authorization/dispatch boundary, **not an MCP wire-protocol server**. No external LLM provider is configured. The deterministic offline model is a testable contract substitute, not AI inference.
- Structured draft schema, BUY quantities, material set, run ID and workflow order context are validated against immutable persisted facts. Duplicate material/day lines are aggregated by material for the run-level draft.
- No direct ERP PR/PO, WMS stock modification, shell execution, arbitrary HTTP, or write tools.
- `GENERATING_ADVICE` → `WAITING_REVIEW` uses existing `ADVICE_DRAFTED` workflow transition. Draft stored in `platform.agent_drafts`; idempotency key `(workflow_id,workflow_version)` and deterministic event ID. If crash occurs after draft save, replay can complete transition; if source facts change, hash conflict fails closed.
- Tool trace contains hashed arguments/results, not raw sensitive payloads; database stores full draft for HITL. This is a local demo, not a production privacy/security review.

## Test and release gate
1. Python 3.14 only. From `m2_pg16_gate` execute `./run_pg16_gate.ps1` in PowerShell.
2. PostgreSQL 16 integration tests and full regression must pass without skips.
3. Confirm `test_agent_harness_unit.py` and `test_agent_harness_postgres.py` run.
4. Do not sign off before real Windows/PostgreSQL gate logs have been reviewed.
5. Remaining V0.2+: real MCP protocol server, provider LLM integration, per-tool role/policy versioning, provider timeouts, end-to-end multi-process crash tests, production auth, and formal approval workflow.
