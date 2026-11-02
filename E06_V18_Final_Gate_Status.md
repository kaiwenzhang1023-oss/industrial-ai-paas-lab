# V1.8 E06 final gate — current evidence (2026-11-01)

## Status: NOT ACCEPTED / BLOCKED

This is an offline source repair candidate, **not** a signed-off V1.8 release.

## Changes in this candidate

1. Replaced `pytest_runtest_setup`-time database guard with `pytest_collection_modifyitems` so database tests are skipped or blocked **before fixtures run**. The old hook ran after fixture setup could already have connected or written.
2. Fail closed when explicit database test opt-in is present but no supported test DSN is provided.
3. Added regression checks for missing DSN and early gate placement.
4. Preserved production `app/db/repository.py` and all business/migration code unchanged.

## Evidence obtained in isolated offline runtime

- Python AST: 154 files parsed, 0 syntax errors.
- Guard unit tests: 15 passed.
- Full pytest collection attempted: **439 collected, 8 collection errors** due to missing `psycopg` in this offline Python 3.13 runtime. Project requires Python 3.14; these errors do not establish application defects. No DB connections attempted.
- No PostgreSQL, Neon, Render, Docker, migration, or browser tests run.

## Mandatory blockers before final sign-off

- Verify the guard covers all database/side-effect test paths and cannot be bypassed by fixture setup, test import side effects, subprocesses or unmarked tests.
- Refactor existing `autocommit=True` tests and seeded business fixtures for deterministic cleanup or dedicated disposable DBs.
- Execute the complete test suite using **Python 3.14** with all pinned dependencies installed; resolve every failure and skip explicitly.
- Run PostgreSQL 16 migration replay and M2/Workflow/Outbox/Agent/MCP/MES/SRM/WMS/Mapping contract checks on a **new disposable local test database**, after explicit approval to create/use it. Never run on Neon/Render/production.
- Validate PowerShell 5.1 scripts on Windows, and perform API/frontend E2E checks.
- Compare delivered source manifest with baseline and publish hash, test results and acceptance sign-off.

## Safety

No real database connection, data migration, Docker command, destructive operation or deletion of original source/history was performed. All modifications are in the candidate source copy.
