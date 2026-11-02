# Industrial AI PaaS Lab — M3-01 V0.3

Development snapshot: worker scheduler, replay-safe M2 runner, initial Outbox notification, PostgreSQL reliability tests.

Local Python test result: **110 passed, 26 skipped**. The skipped tests require a real PostgreSQL instance. **V0.3 is NOT signed off** until the Windows PostgreSQL 16 gate is executed and the new reliability tests pass.

M2 V0.2.1 baseline previously reported by user: 127 passed on Windows PostgreSQL 16. This is historical baseline evidence, not V0.3 evidence.

## V1.8 C4.3 — MCP identity and session isolation

Implementation candidate added: trusted token resolver, immutable VerifiedIdentity, per-request re-authentication, tenant/principal/scope-bound MCP sessions, session expiry and identity-bound session termination, SecureBridge allowlist/scope enforcement, regression tests, Python 3.14 non-root Dockerfile. Offline verification: 70 focused tests passed; broad offline regression 396 passed / 12 skipped / 6 deselected. PG16 live, Python 3.14 user-side execution, Docker build/runtime and browser E2E remain pending. Production: NO-GO.
