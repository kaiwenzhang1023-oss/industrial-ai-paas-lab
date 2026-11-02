# Industrial AI PaaS Lab V1.4 Batch A RC2 — 专项修复与验收

## 基线与范围

以 V1.4 Batch A RC1 完整工程为基线，保留原始 V1.3 RC2 功能。只修改 `backend/app/srm/service.py`、`backend/tests/test_srm_v14_pg16.py`，新增 `backend/tests/test_srm_v14_readonly.py`、本说明及 `run_v14_rc2_gate.ps1`。数据库 DDL 无变化，**已完成 RC1 迁移的 `industrial_lab_v14_test` 不必重跑迁移**。

## 修复

1. `confirm()` 查询重复 `confirmation_id` 时，同时验证所属 `po_id` 和事件哈希，拒绝跨单 ID 复用。
2. 延期风险快照发生 OPEN / UPDATE / RESOLVE 时写入 `srm_v14.audit`，保存变更前后证据。`supply_exceptions` 仍是当前风险快照表；历史以 audit 为准。
3. PG16 测试新增：来源 Hash 被篡改后的 `BUY_SOURCE_CONFLICT` 和事务回滚；部分确认、多批次延期、延期数量/天数、审计、跨单确认 ID 冲突。
4. 新增只读测试验证 POST/PUT/PATCH/DELETE 在 `PUBLIC_READ_ONLY=1` 时返回 403。

## 已在构建环境执行

- Python 编译检查 PASS
- `tests/test_srm_v14_batch_a.py`: 4 passed
- `tests/test_srm_v14_readonly.py`: 1 passed
- **真实 PG16 专项集成测试未在构建环境执行**；必须在本地独立数据库完成。

## 本地验收（Windows PowerShell）

打开 `m2_pg16_gate` 目录中的 PowerShell，确认 `industrial_lab_v14_test` 已创建并执行过 015 迁移。运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_v14_rc2_gate.ps1
```

脚本自动从 Docker 容器读取密码并配置 `TEST_DATABASE_URL`，不打印密码。会检查数据库名和 10 张 SRM 表，然后运行 4 个单元测试、1 个只读测试和 1 个真实 PG16 集成测试；不会重新执行迁移或重建数据库。脚本明确禁止 `PUBLIC_READ_ONLY=1` 的测试连接，并只操作本地测试库。

如果原 RC1 集成测试已留下采购需求，本版会再创建一个新的 MRP 运行用于测试；不能将既有数据库中的所有采购需求都视为可重复使用。

## Final Gate 待验收

- [ ] 本地 RC2 PG16 集成测试 PASS（不允许 SKIPPED）
- [ ] V1.3 原有测试回归 PASS（独立执行）
- [ ] Workbench 浏览器操作回归 PASS（如本轮有 UI 变更则必需；本 RC2 无 UI 变更）
- [ ] V1.4 SRM API 本地只读模式 HTTP 403 PASS（自动化已验证，建议上线前再验）

## 已知边界

- V1.4 仍为模拟采购协同，不连接真实供应商。
- `supply_exceptions` 为最新风险快照，审计记录用于历史追溯；没有引入新的迁移。
- 未实现取消/拒绝采购单后对未履约采购需求的重新开放流程。
- `DELIVERY_DELAY` 按全部已确认批次的最晚日期计算；不计算未确认量的供应缺口风险。
