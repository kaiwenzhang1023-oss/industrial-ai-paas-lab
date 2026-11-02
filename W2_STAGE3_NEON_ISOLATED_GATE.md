# V1.1 W2 Stage 3 — Neon 隔离分支集成验收

## 状态
本包只包含隔离分支验收测试和只读预检 SQL；**没有连接 Neon，也没有执行迁移或生产部署**。

## 操作前置条件
1. Neon Console 新建独立 branch，例如 `v11-w2-stage3-test`，确认与 `production` 不同，保存 branch 名称与 endpoint host；不要把生产 URL 粘贴到聊天中。
2. 在 Neon Console 该 branch 的 SQL Editor 执行 `database/014_v11_stage3_readonly_checks.sql`，确认订单、effective BOM、MRP 追溯表存在。
3. 该测试使用现有 V1.0 表结构，**不依赖 013 草案**。不要在生产运行 DDL、seed、bootstrap。
4. 只有确认 `TEST_DATABASE_URL` 属于隔离 branch 后，才设置 `V11_ISOLATED_BRANCH_ACK=YES`。Neon 分支可使用相同数据库名，因此**不能仅用数据库名判断是否为生产**。

## 执行（本地，backend 目录）
```bash
python -m pip install -r requirements.txt
export TEST_DATABASE_URL='postgresql://...isolated-branch-host.../industrial_lab_demo?sslmode=require'
export V11_ISOLATED_BRANCH_ACK=YES
export V11_TEST_AS_OF=2026-11-20
python -m pytest -q -m integration tests/test_erp_v11_stage3_postgres.py -s
```
Windows PowerShell 用 `$env:TEST_DATABASE_URL=...` 和 `$env:V11_ISOLATED_BRANCH_ACK='YES'`。

## 测试行为及限制
- 只对隔离分支写入新生成的 `platform.requirement_runs` / `integrated_mrp_payloads` / pegging 追溯行，不会删除旧数据；不运行 seed 或 013 迁移。
- 验证指定订单实际计算与持久化、跨订单泄漏、重复运行哈希、原全局 MRP、缺失订单原子回滚、重复 run_id 原子性。
- 不能证明 Agent、Workflow、Workbench 全链路兼容；需另行执行原有数据库集成测试，且部分测试会修改种子数据，**必须仅在可丢弃的隔离分支执行**。
- 本阶段范围持久化仍在 `integrated_mrp_payloads.source_versions.v11_order_scope` JSONB 中；`platform.mrp_run_order_scope` 表尚未创建，不能宣称关系表追溯已完成。
- 失败后保留隔离分支用于排错，不自动回滚生产，也不自动删除测试分支。

## 验收
四项新集成测试全部 PASS，且 27 项原有数据库集成测试在隔离分支完成验证后，才能考虑 W2 Stage3 通过；否则标记为 PENDING。生产部署需独立审批。
