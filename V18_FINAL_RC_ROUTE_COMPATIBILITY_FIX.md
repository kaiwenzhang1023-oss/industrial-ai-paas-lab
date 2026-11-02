# V1.8 Final RC route compatibility fix

- Fix only `backend/tests/test_v18_phase4_http_workbench.py`: safely inspect routes with optional `path` attribute.
- No business logic, schema, authentication, MCP protocol, or production configuration changes.
- User observed original gate: 88 passed, 1 failed, 1 warning.
- Run `RUN_ACCEPTANCE_V18_FINAL_RC.cmd` once in Windows to verify.
- PG16 live, browser E2E, full MCP conformance remain uncertified.
