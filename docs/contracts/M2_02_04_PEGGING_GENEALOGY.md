# M2-02-04｜MOQ、批量与 Pegging 深化 V0.1

## 交付
- `app.domain.supply_allocation.plan_supply`：同一天多条在途供应保留不同来源行 ID，按日期及确定性顺序分配；沿用 MOQ/批量计划余量结转。
- `app.domain.pegging_report.build_pegging_report`：订单需求分配明细、来源供应容量台账、生产计划批次到子物料需求的血缘边；对需求和来源容量执行 Decimal 守恒校验。
- `report_as_jsonable`：Decimal 以字符串序列化，避免浮点精度损失。

## 冻结的业务边界
1. 库存来源 `STOCK:<material>@<as_of>`，在途来源 `RECEIPT:<material>:<source_row_index>@<date>`，计划来源 `PLAN:<material>@<need_date>`。在途 source_row_index 是**输入快照内**的行序号，仅在同一快照内稳定，尚非 ERP 全局业务主键；生产集成必须改为 `source_system + document_id + line_id` 并结合 snapshot_hash。
2. 对同一个供应来源，所有订单分配之和不超过来源容量；对每个需求，分配总和严格等于毛需求。
3. 自制件 MOQ 超额批次仅展开一次完整 BOM；余量可供后续订单使用，但下层物料需求归属于计划批次，而非任意一张订单。跨层展示为可遍历图，不作伪造的按订单比例归属。
4. 计划分配不是 WMS 库存预留；不存在跨运行的锁定与承诺。供应到货仅按日期，未实现到货时刻、质量状态变化、撤单/重排与计划执行回写。
5. 版本化 BOM 仍按父件计划释放日期选择；报表保留版本和计划批次血缘。

## 未完成及签核门槛
- 尚未将追溯报表持久化到 PostgreSQL 或接入 DB API；未执行 PostgreSQL 并发、事务和数据契约集成测试。
- 当前计划批次 ID 在单次运行中唯一；跨运行须补充 `run_id` 命名空间。
- 输入快照源行身份必须改用 ERP/WMS 不变主键，才能支持跨运行一致性审计。
- M2-01 PostgreSQL 实测仍是强制签核条件，不得因单元测试通过而视为完成。
