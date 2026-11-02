# M1-01 Security hardening candidate — Docker PG16

This is an additive hardening-test candidate based on the previously delivered full M1-01 source. **Do not re-run migration 017.** Five MCP tools remain disabled. No V1.4 database is touched.

## Prerequisites
- Existing Docker container: `m2_pg16_gate-postgres-1`
- Existing independent database: `industrial_lab_v15_test`, already migrated with 017
- Existing Python 3.14.6 `.venv314` with pytest 9.2.0 and psycopg 3.3.6
- Private environment variable `M1_TEST_DATABASE_URL` pointing exclusively to `industrial_lab_v15_test`

Run from the extracted full-source directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_M1_01_SECURITY_HARDENING.ps1
```

## Coverage
1. Tenant/resource/principal isolation, inactive resources, revoked/expired grants and disabled principal.
2. Audit UPDATE and DELETE trigger protection, invalid transition and transaction rollback.
3. No PUBLIC ACL on governance schema/tables/functions.
4. Two independent PG16 connections racing the same CAS: exactly one winner; state and audit consistency.

## Known limitations and cautions
- **The concurrency test commits a uniquely identified test call and two audit events in the V1.5 isolated test database**, intentionally retaining append-only evidence. It does not delete audit rows. Repeated executions add test evidence.
- This is not a full low-privilege runtime role test. No roles are created or modified; runtime role separation and RLS are still pending.
- Existing `lab` role may own the schema. Passing tests as owner is not evidence that untrusted principals cannot directly read tables or impersonate identity.
- This suite has been syntax-checked in the assistant container, **not executed against your Docker PG16**. Mark NOT RUN until local log is returned.
- The frozen V1.4 source files and migrations are unchanged; this candidate adds one test file, one runner, and this README.
