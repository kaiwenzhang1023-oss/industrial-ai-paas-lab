# M2-02-02｜多版本 BOM 与有效日期选择（V0.1）

## 契约
- BOM 仅 `RELEASED` 可用于计划；`DRAFT` 不参与选择。
- 有效期 `[effective_from, effective_to)`：开始包含，结束不包含。
- **父件投料/计划释放日**为该父件 BOM 的选版日期，**不是**销售订单交期，也不是 MRP 执行日。
- 同一父件同一天必须且只能命中一个已发布版本；缺版/重叠直接失败，不自动退回上一版。
- 每次自制件计划订单产生时，按该自制件的计划释放日重新选择其 BOM；跨订单共享库存先统一净需求，再对计划自制件向下展开。
- 自制件因 MOQ/批量产生的超额计划数量也消耗下层物料。当前将其追溯到 `PLAN:<material>@<date>`，不虚构订单级归属。
- 不同订单可命中不同版本，结果保留 `order_id / parent / version / need_date / qty` 证据。
- 对所有 RELEASED 版本组成的图检查循环依赖，宁可保守拒绝潜在跨版本循环。

## 实现
- `backend/app/domain/versioned_bom.py`：版本选择、有效期/循环校验、共享库存时段化计算、BOM 展开来源追溯。
- `backend/tests/test_versioned_bom.py`：边界、草稿、缺版、重叠、循环、跨版本订单、子件选版、重复运行等。
- `database/005_effective_bom.sql`：旧数据库 inclusive `effective_to` 到 exclusive 新字段的兼容迁移（尚未实测）。

## 尚未完成 / 阻断签核
1. 新引擎目前独立于原有 `plan`/`allocate`，尚未接入 PostgreSQL Repository 或 DB API；因此旧端点**不会**自动应用版本化选版。
2. SQL 迁移未在真实 PostgreSQL 运行；版本重叠的数据库排他约束、状态变更校验、并发发布事务未实现。
3. 版本化的订单级库存/计划供应 Pegging 仍待整合；当前 `DemandTrace` 记录 BOM 展开来源，不等于 WMS 库存预留。
4. 真实 ERP/WMS/MES 数据契约与 M2-01 数据库集成测试仍未签核。
5. 计划释放日早于规划起点会拒绝；提前期/时区/日历仍为简化自然日模型。

## 运行
`cd backend && python -m pytest -q`
