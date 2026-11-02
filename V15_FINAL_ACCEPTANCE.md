# V1.5 consolidated engineering delivery — acceptance status

## Source and environment
This ZIP is the complete V1.5 source baseline, including legacy V1.1–V1.4 business code, schema scripts and V1.5 security/MCP components. The existing `.venv314` is intentionally not embedded (Windows venv is not reliably relocatable). Copy or recreate the environment *only after verifying the new project works*. The Docker PG16 database and its volumes are external and **not** inside this ZIP.

## Implemented in this delivery
- JSON-RPC 2.0 stdio transport: initialize, initialized notification, ping, tools/list, tools/call.
- Five read-only V1.4 persistence adapters via V1.5 authorization gateway.
- Trusted host HMAC identity; no caller-controlled identity or release switch.
- Security database request ledger, idempotent replay of committed response, in-progress calls never auto-reexecute, append-only gateway audit.
- Dual DB identity checks; isolated test migration 020; 44 deterministic protocol/contract golden test cases.

## NOT certified — must not be represented as finished
- 44 deterministic cases are NOT the same as 44 real PG16 end-to-end business Golden Cases.
- Real five-tool **authorized** E2E requires provisioned principal, active registry/grants and persisted business records. Current baseline only tests deny and adapter reads separately; the test gate may SKIP empty source rows.
- Crash between business read and audit completion yields UNKNOWN; manual reconciliation is required. No cross-database atomic commit.
- No external MCP client interoperability suite or network Streamable HTTP transport certification.
- Production release remains disabled. Do not delete PostgreSQL volumes or unbacked historical assets.

## Test-only commands
Run `RUN_V15_FULL_GATE.ps1` from the extracted project. To start the opt-in stdio server, set `V15_MCP_HMAC_SECRET`, `V15_MCP_HOST_TOKEN`, and `V15_TEST_MCP_ENABLE=I_ACKNOWLEDGE_TEST_ONLY` in a trusted host process, then run `RUN_V15_MCP_TEST_SERVER.ps1`. Never put credentials in MCP tool arguments or log output.

## Cleanup
Keep this ZIP plus the verified extracted directory and external database backups. After copying the existing Python environment and running the gate successfully from this directory, older extracted source trees and ZIPs may be removed **only if** they contain no unique user work or backup. Never automatically delete them.
