# Industrial AI PaaS Lab V1.8 — E06-15 Final RC1

## 一次性集中执行

本包整合 E06-15A（只读迁移盘点）与 E06-15B（隔离回放库身份核验/创建结果检查），并提供 E06-15C/15D 的集中门禁。用户不需要逐阶段下载脚本。

### 已知现场前置条件

- Docker 容器：`industrial-v18-pg16-test`
- 镜像：`postgres:16`
- 宿主机端口：`55432 -> 5432`
- 数据库用户：`v18_tester`
- 已批准的独立回放数据库：`industrial_ai_v18_e06_migration_replay`
- 既有验收数据库：`industrial_ai_v18_e06_acceptance`（只做身份核验，不写入）
- Python：3.14
- PowerShell：Windows PowerShell 5.1

本脚本假设 E06-15B 已成功创建回放库，且该回放库仍为空。若检测到非空且不存在本门禁迁移账本，会停止，不会猜测状态或重置数据库。

## 执行步骤

1. 将 ZIP 解压到一个新目录。
2. 在 Windows PowerShell 5.1 中进入解压后的项目根目录。
3. 执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\E06_15_FINAL_ONE_SHOT_GATE.ps1"
```

不需要输入数据库密码：脚本通过 `docker exec` 在容器内部使用本地 PostgreSQL socket，以 `v18_tester` 连接。若容器配置要求密码或认证失败，脚本会停止，不会要求用户把密码写入脚本或证据。

## 门禁执行内容

1. PowerShell 5.1、Python 3.14、Docker 服务版本检查。
2. 容器名称、镜像、运行状态和 55432 端口映射核验。
3. 对 `industrial_ai_v18_e06_acceptance` 做只读身份核验。
4. 对 `industrial_ai_v18_e06_migration_replay` 做数据库身份与状态核验。
5. 清除本 PowerShell 进程中的数据库 DSN 环境变量，执行完整 Python 3.14 离线 pytest 回归；执行后恢复原进程变量。
6. 按固定顺序应用核心迁移：`schema.sql`、`003` 至 `012`。
7. 为核心迁移记录 SHA-256 账本。
8. 第二轮重新运行门禁时，逐个核对 checksum 并跳过已应用迁移；若源码发生变化则 fail-closed。
9. 比较两轮迁移后的 PostgreSQL 目录快照。
10. 检查五个业务 schema、业务表数量、无效索引、未验证约束、外键目标及迁移账本完整性。

## 为什么第二轮是“账本核验并跳过”，不是盲目重放 SQL？

源码审查确认 `008_workflow_runtime.sql` 使用非 `IF NOT EXISTS` 的约束/表创建语句；因此不能把整组原始 DDL 不加区分地重复执行。部署迁移的正确重复执行语义是：按迁移版本和内容 checksum 判断是否已经应用；相同版本、相同 checksum 则跳过；checksum 漂移则停止。这样既验证部署器幂等性，也避免破坏性重放。

若第一次迁移中途失败，某些不带事务包装的旧 SQL 可能已部分生效但尚未写入账本。脚本会保留现场并停止；不要删除对象或手工补账。应将 `E06_15_FINAL_EVIDENCE_*` 和失败信息交回工程审查后再制定恢复方案。

## 核心迁移范围

仅包含 `database/schema.sql`、`003_v03.sql`、`004_snapshot_fence.sql`、`005_effective_bom.sql`、`006_m2_integration.sql`、`007_normalized_pegging.sql`、`008_workflow_runtime.sql`、`009_workflow_worker.sql`、`010_agent_harness.sql`、`011_agent_governance.sql`、`012_outbox_receipts.sql`。

V13/V14/V15、DEV_ONLY、TEST_ONLY、ACCEPTANCE_TEST_ONLY、诊断 SQL、seed.sql 均不属于本次核心迁移链，不会被自动执行。

## 安全边界

- 不连接 Neon、Render 或任何云端数据库。
- 不修改 `industrial_ai_v18_e06_acceptance`。
- 不修改 V12/V13/V14/V15 历史测试数据库。
- 不删除数据库、schema、表、角色或历史数据。
- 不自动清理回放数据库。
- 不执行 seed 数据。
- 不把测试 DSN 复制到生产 `DATABASE_URL`。
- 若目标身份、迁移账本、checksum 或对象状态不符合预期，停止并保留证据。

## 证据目录

脚本会在项目根目录生成 `E06_15_FINAL_EVIDENCE_yyyyMMdd_HHmmss`，包含身份核验、迁移日志、Python 测试结果、迁移账本、两次目录快照、完整性计数和 `FINAL_RESULT.txt` 或 `FAILURE.txt`。

**本 ZIP 是可执行候选交付包，不代表用户机器上的最终 PG16/Python 结果已经通过。最终结果以现场门禁日志和证据目录为准。**
