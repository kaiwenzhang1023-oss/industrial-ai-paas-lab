# E06-15 Migration Source Audit — Final RC1

## 审查对象

完整源码来自用户上传的 `Industrial_AI_PaaS_Lab_V1.8_C4.5_E06_Gate_Hardening_RC3_E06-14` ZIP。E06-15 Final RC1 在该源码基础上新增集中式验收脚本与说明，不改变业务应用 Python 源码或原始 SQL 迁移文件。

## 核心迁移链

| 顺序 | 文件 | 审查结论 |
|---:|---|---|
| 1 | schema.sql | 创建五个基础业务 schema 和核心表；以 IF NOT EXISTS 为主 |
| 2 | 003_v03.sql | 新增 pegging 表和索引；可重复创建对象 |
| 3 | 004_snapshot_fence.sql | 新增快照围栏表 |
| 4 | 005_effective_bom.sql | 包含数据 UPDATE 和条件约束创建；不能只凭 IF NOT EXISTS 推断全文件无副作用 |
| 5 | 006_m2_integration.sql | 新增 effective BOM 与集成 MRP 持久化对象 |
| 6 | 007_normalized_pegging.sql | 新增规范化供需分配对象及索引 |
| 7 | 008_workflow_runtime.sql | 使用普通 CREATE TABLE 与显式约束名；不适合盲目重复执行 |
| 8 | 009_workflow_worker.sql | 对状态约束先 DROP 再 ADD；在已有约束时会重建约束 |
| 9 | 010_agent_harness.sql | 新增 Agent drafts 表及索引 |
| 10 | 011_agent_governance.sql | 新增 Agent tool audit 表及索引 |
| 11 | 012_outbox_receipts.sql | 新增 outbox receipt 表 |

## 被排除文件

- `013_v13_mes.sql`：历史 V13 专用迁移。
- `015_v14_srm_batch_a.sql`、`016_v14_mapping_batch_b.sql`：历史 V14 专用迁移。
- `017`、`018`、`019`、`020`、`025` V15 文件：V15 安全/测试专用脚本。
- `024_v18_phase3_pg_ledger_DEV_ONLY.sql`：DEV_ONLY。
- `*_TEST_ONLY.sql`、`*_ACCEPTANCE_TEST_ONLY.sql`：不属于部署迁移。
- `014_v11_stage3_readonly_checks.sql`：诊断查询。
- `seed.sql`：独立种子数据，不自动加载。

## 重复执行策略

采用 `platform.e06_schema_migrations(version, sha256, applied_at)` 作为本门禁迁移账本。第一轮应用每个核心迁移，并在该迁移成功后写入其 SHA-256。第二轮逐个核验版本和 checksum，全部一致则跳过，不再次执行原始 DDL。此策略验证迁移 runner 的幂等性，而不是声称所有原始 SQL 都可直接重放。

## 已知限制

1. 旧迁移并非统一事务封装。如果迁移在中途失败，SQL 可能部分生效但账本尚未记录；脚本停止并保留现场，不自动回滚或清理。
2. 本次目录快照用于比较 schema、关系、列、约束、索引和触发器定义；不代表业务数据性能、并发压力或灾备恢复测试。
3. 不运行 seed.sql，因此数据守恒/业务黄金样例不是本阶段数据库迁移门禁的测试对象。
4. Python 3.14 全量 pytest 在用户本机执行；未执行的数据库测试若按项目配置 skip，报告会保留其 skip 结果，不能将 skip 解释为 live PG 集成通过。
5. PowerShell 5.1 解析和真实 Docker 执行必须在用户 Windows 主机完成；当前打包环境不能访问用户 Docker daemon。

## 交付声明

本阶段提供一次性集中执行器与源代码审查记录。没有在用户 Docker 容器上执行任何迁移；没有连接 Neon/Render；没有修改任何用户数据库。
