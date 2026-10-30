# Industrial AI PaaS Lab — M2-01 V0.2

Simulated industrial integration platform. **Not production software.**

## Local run
```bash
cd backend
pip install -e '.[test]'
python -m pytest -q
uvicorn app.main:app --reload
```
Swagger: http://127.0.0.1:8000/docs. Shared inventory daily MRP: `/api/v1/mrp/multi-order`.

## PostgreSQL
```bash
docker compose up -d postgres
```
SQL schema + reference seed in `database/`. Database-backed API repositories are **not implemented**; current API loads `datasets/seed/multi_order.json`.

## What is tested
Original EM-100 single-order golden case plus shared-stock multi-order time-bucket cases. See `docs/contracts/M2_01_CONTRACT.md` for limitations.

## M2-01 V0.3

See [V0.3 technical contract](docs/contracts/M2_01_V03.md) for PostgreSQL Repository, deterministic order-level pegging, migration, seed CLI and integration-test instructions. PostgreSQL integration is **not yet runtime-verified**; Python unit regression is verified. The current API remains JSON-backed.


## V0.4 signoff audit and M2-02 preparation
See `docs/contracts/M2_01_V04_SIGNOFF_AUDIT.md` and `docs/contracts/M2_02_ENGINE_PLAN.md`. Static contract tests do not replace live PostgreSQL tests.


## M2-02-01 数据快照一致性与版本围栏

见 `docs/contracts/M2_02_01_SNAPSHOT_FENCE.md`。已有数据库执行：

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/004_snapshot_fence.sql
```

**M2-01 PostgreSQL 实测仍为强制签核门槛，未运行不得宣称通过。**


## M2-02-02 V0.1
新增独立版本化 BOM 引擎与 12 项回归测试，详见 docs/contracts/M2_02_02_EFFECTIVE_BOM.md。旧 API 暂未切换。

## M2-02-03 V0.1 供应分配与版本化 BOM
新增 `backend/app/domain/supply_allocation.py` 和 `backend/tests/test_supply_allocation.py`。
使用 `plan_supply(orders, items, revisions, as_of)` 获得按日 MRP 行、需求记录、供给分配、计划批次、BOM 选版记录。
详细边界与签核见 `docs/contracts/M2_02_03_SUPPLY_ALLOCATION.md`。此模块尚未连接数据库 API。

## M2-02-04 V0.1｜供应来源与跨层 Pegging 报表

新增 `backend/app/domain/pegging_report.py` 和 `backend/tests/test_pegging_report_v04.py`。使用 `plan_supply(orders, items, revisions)` 生成计算结果，再调用 `build_pegging_report(result, items)` 获取订单分配、来源守恒台账和计划批次到子件需求的血缘边；详情见 `docs/contracts/M2_02_04_PEGGING_GENEALOGY.md`。数据库集成尚未通过。

## M2-02-05｜统一制造计算业务验收

新增 `app.domain.acceptance.run_acceptance`，聚合版本化 BOM、供应分配、计划批次血缘、守恒校验和稳定 SHA-256 结果指纹。
演示 API：`GET /api/v1/acceptance/m2-02-05/demo`，仅内存模拟。
业务验收契约：`docs/contracts/M2_02_05_BUSINESS_ACCEPTANCE.md`。
本次环境测试：88 passed, 5 skipped（PostgreSQL 集成测试仍待执行）。

## M2 集成收口 V0.1（新增）

数据库驱动版本化 MRP 接口和完整 Pegging JSONB 持久化已实现，**尚未通过真实 PostgreSQL 实测**。

首次启动新数据库：`docker compose up -d postgres`（初始化脚本含 `006_m2_integration.sql`）。
已有 Docker volume 的数据库**不会自动执行新增迁移**，请先备份，再手动执行：
`docker compose exec -T postgres psql -U lab -d industrial_lab < database/006_m2_integration.sql`。

在 `backend` 下设置 `DATABASE_URL=postgresql://lab:local_demo_only@localhost:5432/industrial_lab`，然后：

```bash
pip install -e '.[test]'
python scripts/integrated_m2.py seed
python scripts/integrated_m2.py run
uvicorn app.main:app --reload
```

- `POST /api/v1/db/integrated-mrp/runs?as_of=2026-11-20`
- `GET /api/v1/db/integrated-mrp/runs/{run_id}`

**独立测试数据库**：先创建 `industrial_lab_test`，按上述 SQL 初始化，再设置 `TEST_DATABASE_URL`（数据库名必须包含 `industrial_lab_test`），执行 `python -m pytest -q`。未配置时数据库集成测试跳过，不构成验收通过。

详情见 `docs/contracts/M2_INTEGRATION_GATE.md`。

## M2 Integration V0.2 — normalized Pegging and mandatory live gate

See `docs/contracts/M2_INTEGRATION_V02_LIVE_GATE.md`.
Apply `database/007_normalized_pegging.sql` after 006. The live PostgreSQL gate has **not** been executed in the current environment; no M2 final signoff is claimed.
