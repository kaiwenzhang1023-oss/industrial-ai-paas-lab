# M2 集成收口｜验收记录 V0.1

## 已实现
- 独立 `mock_erp.effective_bom_headers/components`，按父件/版本/有效日期保存 BOM；历史 `bom_versions` 仍保留。
- `run_integrated`: PostgreSQL `REPEATABLE READ` + 来源表 `SHARE` 锁；同一事务读取订单、库存、供应、有效 BOM，运行 `run_acceptance`，原子保存结果 JSONB 和来源版本。
- `read_integrated_run`: 从数据库回读并校验 SHA-256，拒绝结果篡改。
- 新接口 POST `/api/v1/db/integrated-mrp/runs?as_of=2026-11-20`，GET `/api/v1/db/integrated-mrp/runs/{run_id}`。数据库不可用时不会降级为内存模拟。
- `seed_effective_bom` 仅在版本表为空时由历史 BOM 导入 V1，避免覆盖已有修订。

## 测试结论
- 当前环境执行 `96 passed, 7 skipped`，其中 7 项为未连接真实 PostgreSQL 的集成测试（旧 5 + 新 2）。
- **PostgreSQL 真实建表、导入、事务回滚、双连接并发锁与持久化回读尚未执行；M2-01 不予最终签核。**
- API 仍保留旧的 JSON 演示路径；仅新 integrated-mrp 路径使用统一数据库引擎。

## 已知边界 / 后续修正
- 供应行 ID 以来源单据保存在 `source_versions.supply_ids`，但 Pegging 内部供应 ID 仍按排序序号构建，尚未实现跨运行稳定来源 ID 端到端传递。
- 库存行版本与订单行版本已记录，物料和 BOM 暂未实现数据库行版本控制；依靠共享锁与快照一致性。
- JSONB 保存完整计划结果，尚未规范化拆分为可 SQL 分析的 BOM 选择、计划批次、分配和血缘明细表。
- 目前的共享表锁会阻塞并发写入，仅适合教学/低并发验证。
- 历史到货的未消耗余额在教学简化下结转到 as_of，实际业务需依据 ERP 收货/占用状态去重。
- BOM 已发布版本的日期重叠由 Python 校验，尚未建立 PostgreSQL 排他约束。
- 未接入外部 ERP/WMS/MES 独立服务，数据来自模拟 schema。

## 真实 PostgreSQL 签核门槛
1. PostgreSQL 16 实例与独立 `industrial_lab_test` 测试库可用。
2. `schema.sql`, `003_v03.sql`, `004_snapshot_fence.sql`, `006_m2_integration.sql` 初始化成功。
3. 种子加载与 BOM 导入成功，运行后回读 hash 相等。
4. 相同输入两次运行 input_hash、result_hash 相等。
5. 真实数据库回滚、锁冲突和快照并发场景完成测试；所有 PostgreSQL 用例不再跳过。
6. 数据契约签核覆盖来源 ID、供应可用性、BOM 有效期、审批前快照复核。
