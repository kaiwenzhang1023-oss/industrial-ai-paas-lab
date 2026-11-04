# Industrial AI PaaS Lab · Version B Cloud Preview RC2 — Unified Acceptance

Date: 2026-11-04. Scope: standalone Render + dedicated Neon PG16 preview; original RC4 Frozen source and the V1.8 production/preview branches were not changed by this release build.

## Evidence by gate

| Gate | Test or inspection | Result | Meaning |
|---|---|---|---|
| SOURCE | Node `--check` on enterprise-status.js; Python `compileall` | PASS | Syntax only |
| API_OFFLINE | `pytest -q tests/test_preview_rc2.py` | **14 passed** | FastAPI in-memory HTTP perimeter; no PG16 SQL performed |
| BROWSER_OFFLINE | Headless Chromium, page loaded from RC2 assets with deterministic fetch mocks | **5 checked, zero page errors** | New enterprise nav, pane visibility, session role UI, return to browser tabs; NOT online browser testing |
| PACKAGE | SHA-256 file manifest + ZIP `testzip` | PASS | Archive completeness/integrity |
| NEON_SCHEMA | Prior setup: separate Neon project, `industrial_v19b_preview`, nine `version_b_rc2` tables, golden seed | PASS (previous setup) | Infrastructure only, not RC2 runtime validation |
| RENDER_RC1 | Render `industrial-ai-paas-v19-version-b-preview`, commit `bf3e3335…` | LIVE (previous release) | Still **RC1**, NOT RC2 |
| GITHUB_RC2 | GitHub direct connector write | HOLD: HTTP 403, integration lacks Contents write access | RC2 not pushed |
| RENDER_RC2 | Build/deploy new RC2 commit | HOLD: wait for branch push | Not live |
| CLOUD_READY | GET `/ready` against deployed RC2 via public internet | HOLD | Public Neon connectivity not confirmed |
| CLOUD_E2E | Browser → signed session → PostgreSQL MRP → decision → Worker → receipt → audit → tenant isolation | HOLD | **No public E2E pass claim** |

## What changed

- Added a dedicated first-class **Version B · 企业闭环** tab in the Workbench sidebar, with in-page layout. Existing static scenario tabs remain available and unchanged.
- Bound UI actions to the existing RC2/RC4 PostgreSQL-backed enterprise API with temporary bearer sessions and per-visitor tenant separation.
- Added `/ready` probe before session issuance from the UI; 30-second API request deadline and explicit auth-expiry behavior.
- Enforced PostgreSQL 16 in the `/ready` application check.
- Did **not** create external ERP/MES/SRM write adapters.

## Known limitations and release policy

- Guest identities have an `admin` role **within their private tenant** for portfolio demonstration; this is not an enterprise SSO/RBAC deployment.
- The rate limiter is per-process in memory; it is not a distributed abuse prevention layer. Only serve synthetic data.
- The standalone browser simulation uses localStorage for its *own* data, but preview bearer tokens do **not** persist there.
- The cloud preview is not production-grade security certification. The Worker produces internal-only receipts, not manufacturing orders at a real factory.
- Do not deploy RC2 until `RC2_GITHUB_PUSH=PASS`. After push, trigger Render deploy exactly once because autoDeploy is off.
- After deploy, run public API/real browser/DB end-to-end tests and add evidence; until then, cloud release remains `HOLD`.

## Reference identifiers

- GitHub repository: `kaiwenzhang1023-oss/industrial-ai-paas-lab`.
- Preview branch: `v19-version-b-preview`.
- Render service: `srv-dbljfmgae00c73ce2jcg`; URL `https://industrial-ai-paas-v19-version-b-preview.onrender.com`.
- Neon project: `super-glade-55757112`; preview database: `industrial_v19b_preview`, role `v19b_app_runtime`.
- Old RC4 Frozen and G1–G4 local acceptance remain valid as historical gates; no redundant user reruns requested.
