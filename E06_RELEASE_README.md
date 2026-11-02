# V1.8 C4.5 E06 isolation repair — RC3 engineering candidate

## E06-11 completed in source
- Added `industrial_ai_v18_e06_acceptance` to the allowlisted local test targets.
- Pinned this dedicated acceptance database to the `v18_tester` login.
- Added strict DSN parsing and live server identity verification: database name,
  authenticated user, PostgreSQL 16 major version, and primary (not recovery) server.
- Verification runs during pytest collection after explicit
  `E06_ALLOW_ISOLATED_DB_TESTS=YES`, before database test fixtures or test bodies.
- Every configured DSN is checked, including secondary/business database URLs.
- Added regression tests for target acceptance, wrong user/database, wrong PG
  major version, read replica rejection, connection failure sanitization and
  production `DATABASE_URL` rejection.
- Updated the V1.8 Phase 4 live PG16 test to recognize the dedicated E06
  acceptance database without weakening its user/PG16/primary checks.

## Local verification performed in the build environment
- `tests/test_e06_isolated_db_guard.py`: 24 passed.
- Python AST validation is performed for all project Python files during packaging.
- No real Docker or PostgreSQL connection was made by this build process.

## Remaining release blockers
- E06-12: review and isolate all autocommit/seed side effects in integration tests.
- E06-13: Python 3.14 full regression.
- E06-14: live PostgreSQL 16 cross-module integration on the user's isolated Docker DB.
- E06-15: Windows PowerShell 5.1 and frontend browser E2E.
- E06-16: final release evidence and sign-off.

## Safety boundary
- This RC3 candidate does not connect to Neon or Render.
- It does not connect to the user's Docker container or database.
- It does not modify, delete, or migrate any user database.
- The original RC2 archive remains unchanged.
- The user's existing `industrial_ai_v18_e06_acceptance` database is not modified.
