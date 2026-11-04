# Industrial AI PaaS Lab V1.9 — Version B, public-cloud preview candidate

**Isolated deployment, NOT the old RC4 Frozen bundle.** Does not claim production ERP/MES/SRM writes or production security certification.

## Status and components

- Uses only `preview_cloud.app:app`, never the old V1.8 `backend/app/main.py`.
- Dockerfile: `Dockerfile.version-b-preview` (Python 3.14 + Node + enterprise business modules).
- All Version B persisted operations run against PostgreSQL. Public visitor sessions carry server-authenticated HMAC bearer tokens, scoped to a unique tenant. Session lifetime two hours and is not stored in localStorage.
- `POST /api/v1/version-b/preview/session`: new guest session; no operator key.
- Backend allows only explicit enterprise POST routes; legacy write endpoints are absent.
- Internal Worker only. It will not write to physical ERP/MES/SRM.
- `GET /health`: HTTP service health (not DB). `GET /ready`: checks dedicated DB schema.
- Demo protection is bounded single-process rate limiting, **not** a distributed WAF. Do not use for unrestricted production traffic.

## Independent resources

- Neon project: `industrial-ai-paas-v19-version-b-preview` (PG16, separate from the original PG18 project).
- Target DB: `industrial_v19b_preview`.
- Render service: planned `industrial-ai-paas-v19-version-b-preview` on Free tier; do not point existing services to this code.
- `PREVIEW_SESSION_SECRET`: randomly generated at deployment, do not put it in GitHub.
- `DATABASE_URL`: secret Neon connection URL, configure privately on Render.

## GitHub upload (only user action needed before connected deployment)

Extract the ZIP to a **new empty directory** within the user's Version B workspace, then run the included `RUN_PUSH_V19B_PREVIEW.ps1` using `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` and `-SourceRoot` path. The script verifies SHA-256 for every file, initializes ONLY the extracted release folder as a repository, commits and pushes an independent new branch. It will not force-push or change the existing `main` branch. Git for Windows with working GitHub authentication is required.

## Database migrations

Apply these six SQL scripts in the listed order **only** to the dedicated preview Neon database, then seed `datasets/seed/multi_order.json`:
1. `database/schema.sql`
2. `database/003_v03.sql`
3. `database/004_snapshot_fence.sql`
4. `enterprise_workbench/migrations/rc2_001.sql`
5. `enterprise_workbench/migrations/rc2_002.sql`
6. `enterprise_workbench/migrations/rc3_001.sql`

Only execute after checking target database. Assistant can apply migrations via connected Neon after the GitHub push. `preview_cloud/bootstrap.py` provides a guarded, manually prompted fallback, not automatic migration at startup.

## Acceptance gates

Pending: `READY=200`, public session, two distinct guest tenant IDs, one guest cannot read another guest's run, MRP→decision→Worker→receipt→audit, refresh state behavior, rejected invalid token, cross-origin/write route rejection, Neon sleep/reconnect, Render cold start, failure-safe internal-only execution, cost/quota inspection. **No cloud PASS before these are actually executed.**
