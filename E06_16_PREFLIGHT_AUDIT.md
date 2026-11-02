# E06-16｜最终验收收口与交付冻结：源码预审报告

## 1. 输入基线

- 输入文件：`Industrial_AI_PaaS_Lab_V1.8_E06-15_Final_RC1(1).zip`
- ZIP SHA-256：`1a94753bc1b1235430503d0741b8bae45f1d0a677121fcf40a2d9ed7d1892ad7`
- ZIP 条目：338（含根目录条目）
- 原 E06-15 文件清单：337 项，逐项 SHA-256 与 ZIP 内文件完全匹配；清单文件本身未列入自身清单。
- 项目 Python 文件：154，AST 解析错误：0。
- Python 测试文件：81；AST 可识别测试函数：368。
- PowerShell 脚本：26。
- 历史 `.git`、`.venv`、`node_modules`、`__pycache__` 目录：未发现。

## 2. 已有阶段证据盘点

| 阶段 | 本次可见材料/日志 | 当前判断 |
|---|---|---|
| E06-01～E06-11 | 上传 ZIP 未包含独立阶段证据文件夹或逐阶段报告 | 证据待补齐，不能声称已归档 |
| E06-12 | `E06_12_TEST_SIDE_EFFECT_AUDIT.md` | 源码副作用审查完成；不是现场运行证明 |
| E06-13 | `E06_13_CROSS_TEST_ISOLATION_AUDIT.md` | 源码隔离审查及 24 个 guard 单测记录；live PG16 两轮验证未完成 |
| E06-14 | `E06_14_PG16_REPEATABILITY_PLAN.md`、`E06_14_PG16_REPEATABILITY_GATE.ps1`；用户运行日志显示两轮各 1 passed | 目标重复执行通过；不是全量 V1.8 验收 |
| E06-15 | README、迁移审计、最终门禁、build manifest；用户运行日志显示最终 consolidated gate pass | 11 项核心迁移账本、PG16 结构完整性通过；208 passed / 283 skipped 仍需拆分审计 |

**证据边界：** E06-15 的运行证据目录没有包含在本次 ZIP 中。对话日志可证明部分终端结果，但不能替代原始 `E06_15_FINAL_EVIDENCE_*` 目录中的逐条日志、SQL 快照和 JUnit 文件。最终归档时应从用户本机原目录收集这些证据。

## 3. E06-15 迁移链和数据库基线

上传包的 `E06_15_FINAL_BUILD_MANIFEST.json` 明确将以下 11 个 SQL 文件定义为 E06-15 核心迁移链：

1. `schema.sql`
2. `003_v03.sql`
3. `004_snapshot_fence.sql`
4. `005_effective_bom.sql`
5. `006_m2_integration.sql`
6. `007_normalized_pegging.sql`
7. `008_workflow_runtime.sql`
8. `009_workflow_worker.sql`
9. `010_agent_harness.sql`
10. `011_agent_governance.sql`
11. `012_outbox_receipts.sql`

用户提供的 E06-15 最终运行日志记录：PG16.15、5 个业务 Schema、32 张业务表、11 条迁移账本记录、无效索引 0、未验证约束 0、失效外键 0。迁移重放使用 checksum ledger，第二轮按 checksum 核验并跳过，不盲目重复执行 DDL。

**重要范围说明：** `database/` 中还存在 V13/V14/V15/V18 等其他 SQL 文件，其中部分为 `TEST_ONLY`、`DEV_ONLY` 或单独阶段迁移。它们不属于上述 11 项 E06-15 核心迁移链；不能在最终报告中将“11 项核心迁移通过”表述为“所有数据库 SQL 均已执行”。

## 4. E06-15 脚本与已执行版本存在差异

原始上传 ZIP 内的 `E06_15_FINAL_ONE_SHOT_GATE.ps1` 仍包含两个已知问题的旧实现：

- PostgreSQL 系统目录 `"char"` / `smallint` / `boolean` 类型与 TEXT 拼接时没有显式 `::text` 转换；
- 数据库布尔值身份校验正则仍匹配 `f`，而现场输出为 `false`。

此前用户在本机对脚本做了修复，之后才取得 `E06-15 FINAL CONSOLIDATED GATE PASS`。因此，**上传 ZIP 原始脚本不是现场成功执行的完全同一份脚本**。

本 E06-16 候选包已把已知修复同步进源码：
- `relkind`、`attnum`、`attnotnull`、`contype`、`convalidated`、`indisunique`、`indisvalid` 显式转换为 TEXT；
- 数据库身份校验统一匹配 `false`。

历史文件清单 `E06_15_FINAL_FILE_INVENTORY.json` 保留原样，作为原始 E06-15 ZIP 的校验基线；本候选包另建 E06-16 文件清单。

## 5. 283 项 Skipped：源码审计发现

`backend/tests/conftest.py` 的 `_DB_FILES` 显式名单把部分纯离线单元测试/契约测试误归类为数据库测试。进一步静态审阅发现 22 个明显不应仅因文件名而被数据库门禁屏蔽的模块，共 115 个 AST 可识别测试函数：

- `test_agent_harness_unit.py` — 6 个测试函数
- `test_mcp_v15_full_batch_unit.py` — 15 个测试函数
- `test_mcp_v15_gateway_unit.py` — 2 个测试函数
- `test_mcp_v15_release_contract.py` — 8 个测试函数
- `test_mcp_v15_security_unit.py` — 2 个测试函数
- `test_wms_v12_unit.py` — 5 个测试函数
- `test_workbench_unit.py` — 3 个测试函数
- `test_workbench_v02_unit.py` — 3 个测试函数
- `test_workflow_unit.py` — 4 个测试函数
- `test_workflow_v03_unit.py` — 4 个测试函数
- `test_workflow_worker_unit.py` — 4 个测试函数
- `test_workbench_schema_contract.py` — 1 个测试函数
- `test_pegging.py` — 7 个测试函数
- `test_pegging_report_v04.py` — 10 个测试函数
- `test_snapshot_fence.py` — 4 个测试函数
- `test_srm_v14_batch_a.py` — 4 个测试函数
- `test_integrated_m2.py` — 8 个测试函数
- `test_mes_v13_batch_a.py` — 6 个测试函数
- `test_mes_v13_batch_b_contract.py` — 5 个测试函数
- `test_mes_v13_batch_c_gate.py` — 7 个测试函数
- `test_srm_v14_readonly.py` — 1 个测试函数
- `test_w3_workbench_mrp.py` — 6 个测试函数

这些模块源码没有直接 `psycopg.connect`、`DATABASE_URL`、`TEST_DATABASE_URL` 或直接 `connect()` 调用；其中多项使用 fake connection、mock、纯内存数据或静态文件断言。原 guard 会在 pytest collection 阶段将它们整组 skip。将这 22 个模块从数据库名单移除后，本次审阅容器使用 Python 3.13.5 定向执行，实际得到 **184 passed**（5.59 秒），无失败、无跳过。该结果支持它们属于离线测试，但不能替代项目要求的 Python 3.14 全量回归。

E06-16 候选源码已从 `_DB_FILES` 中移除上述 22 个模块；真正带 `postgres` / `pg16` 文件名或 `integration` marker 的测试仍受 fail-closed 门禁保护。

**不能把 283 项全部直接归因为环境跳过。** 最终脚本会生成 JUnit XML，并逐个记录 nodeid、reason、category；除 `E06: database tests disabled by default` 外的跳过原因均要求人工审阅。任何离线模块仍被跳过、依赖缺失或未分类原因都会使最终门禁 HOLD。

## 6. 当前执行环境限制

本次独立审阅容器为 Python 3.13.5，不是项目要求的 Python 3.14；未连接用户 Windows、Docker 或 PostgreSQL 实例。

本次尝试直接运行 pytest 时，因审阅容器没有安装 `psycopg`，发生 8 个 collection errors，并有 5 个 `importorskip` 跳过。这是审阅容器依赖不完整，不作为项目 Python 3.14 测试结论，也不修改项目依赖来掩盖问题。

因此以下只能由用户本机 E06-16 门禁最终确认：
- Windows PowerShell 5.1；
- Python 3.14 全量离线 pytest；
- Docker `industrial-v18-pg16-test` / `postgres:16`；
- `industrial_ai_v18_e06_acceptance` 只读身份核验；
- `industrial_ai_v18_e06_migration_replay` 只读结构与 11 条迁移账本核验。

## 7. 当前结论

**E06-16 状态：HOLD（源码预审完成，现场最终门禁待执行）。**

已完成源码清单核验、Python AST 检查、测试分类问题定位、E06-15 脚本已知缺陷同步修复及最终只读门禁准备。尚未签署 V1.8 FINAL，不声称 283 项已全部合理，也不声称 E06-01～11 证据已完整归档。

本阶段不会连接 Neon / Render，不会运行迁移，不会写入或删除任何数据库数据。
