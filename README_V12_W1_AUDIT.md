# V1.2-W1 静态代码与数据库契约审计

基线：V1.1-W3-04-RC1。仅检查源代码、DDL 和测试；未连接 Neon，未执行迁移。

## 数据流
`mock_wms.inventory_balances` → `app/db/integrated.py:read_integrated_sources` 按物料 SUM(on_hand,reserved,blocked) → `Item` → `run_acceptance()` → `platform.integrated_mrp_payloads` 与 `platform.mrp_supply_sources` / `mrp_demand_allocations` → Workbench。

## 字段映射
| 源字段 | 当前行为 | W2/W3目标 |
|---|---|---|
| material_id | JOIN materials | 查询筛选 |
| warehouse_id | 汇总时丢失 | W2 API 保留 |
| lot_id | 汇总时丢失 | W2 API 保留，空串原样返回 |
| on_hand | SUM→Item.on_hand | Decimal，在手 |
| reserved | SUM→Item.reserved | Decimal，预留 |
| blocked | SUM→Item.blocked | Decimal，冻结 |
| on_hand-reserved-blocked | 领域算法开盘可用量 | API 计算可用量 |
| snapshot_at | 未用于 as_of 过滤 | W2 只读返回，不宣称历史 as-of |
| version | 记录于 source_versions.inventory | W2 只读返回 |

## P0 风险
1. MRP 跨仓跨批次按物料聚合；不具备仓库可达性/批次效期/库位规则。
2. STOCK 的 supply_id 是计划器内部标识，`platform.mrp_supply_sources` 不包含仓库批次血缘；不能虚构来源。
3. 只有当前余额快照表，缺少历史流水/快照版本；`as_of` 不是库存历史回溯。
4. 数据库表 CHECK 保证 reserved+blocked<=on_hand；不能在 MRP 中重复扣减。
5. 版本指纹依赖 version 正确维护；绕开仓储写入逻辑直接改值有风险。

## P1 风险
- Workbench snapshot 库存查询 `ORDER BY material_id LIMIT 200` 可能截断且同物料顺序不稳定。
- `RECEIPT` 来源是 `mock_erp.supply_orders`，不能误称 WMS 收货。
- `run_integrated` 使用 REPEATABLE READ + SHARE 锁，不能直接视作高并发生产设计。
- 没有预留写入生命周期、批次效期、单位换算和库存交易流水。

## 最小增量路线
W2：`app/wms` 只读领域模型、Adapter、`/api/v1/wms/inventory-balances` 和 `/inventory-summary`；参数验证、分页、Decimal、稳定排序；不改数据库、MRP、ERP 写入。
W3：在不破坏历史 result_hash 前提下设计库存来源分配契约和快照语义，独立验收库存变化对净需求的影响。
W4：Workbench WMS 页面与证据联动。
W5：Neon `v12-wms-test` 隔离分支现场只读核验与回归；正式冻结前检查实际表结构/索引/时间分布。

## 边界
本报告仅为代码/DDL 审计；Neon 实际数据库现场审计尚未执行。
