# E06 RC3 engineering audit — E06-11

## Change scope
The RC2 source audit found that the user's dedicated database
`industrial_ai_v18_e06_acceptance` was missing from the E06 local DSN allowlist.
This would reject the correct PG16 test target even when the Docker container
and database were healthy.

RC3 addresses that mismatch and strengthens the opt-in gate:
1. Adds the E06 acceptance database to the allowlist, pinned to `v18_tester`.
2. Strictly parses local TCP PostgreSQL URLs; rejects remote hosts, unknown
   databases, unsupported ports, URI query/fragment overrides and wrong
   dedicated V18 database users.
3. On explicit opt-in, connects to every configured test DSN during pytest
   collection and verifies the server-reported database, authenticated user,
   PostgreSQL 16 version and primary-server status.
4. Sanitizes connection errors so credentials are not copied into test output.
5. Expands the conservative DB-test classification list and adds guard tests.
6. Aligns the V1.8 Phase 4 live PG16 test with the dedicated E06 acceptance DB.

## Verification
- E06 guard unit tests: 24 passed.
- Python AST: see packaged `E06_RC3_BUILD_MANIFEST.json`.
- Live PG16 verification: NOT performed by this build process.
- Full Python 3.14 regression: NOT performed.
- Windows PowerShell 5.1: NOT performed.
- Browser E2E: NOT performed.

## Decision
E06-11 source repair is complete as an engineering candidate.
V1.8 final engineering acceptance remains OPEN until E06-12 through E06-16
are completed and the real Docker PG16 gate passes.
