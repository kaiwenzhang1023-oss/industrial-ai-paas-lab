# M2-02-01 数据快照一致性与版本围栏｜V0.1

## 实现
- `calculate_and_save` 必须在空闲连接上开启 **单一 REPEATABLE READ 事务**，先对 ERP 订单、物料、BOM 版本/BOM 行、供应订单和 WMS 库存六张来源表获取 SHARE 锁，再读取、计算、写入需求/pegs/围栏元数据，并一次性提交。
- SHARE 表锁与常规 INSERT/UPDATE/DELETE 的 ROW EXCLUSIVE 锁冲突，保证锁持有期间源记录不发生并发修改；锁超时 5 秒则失败，**不得**降级为无锁快照或 JSON。
- `input_hash` 对实际参与计算的规范化输入生成 SHA-256；`source_versions` 保存订单与库存行版本清单供诊断，**不能**替代锁。run_id 与 hash 在同一事务落库。
- 数据库 migration: `database/004_snapshot_fence.sql`。已有 Docker volume 必须手动执行 migration；initdb 脚本只对首次建库生效。

## 已知限制与下阶段
1. SHARE 表锁为教学项目的强一致性保守实现，阻塞来源系统写入，不适用于高并发生产环境；未来改为来源变更流水/提交序列+MVCC/乐观围栏。
2. 现有 `load_snapshot` 按全局 as_of 选择 BOM，未实现按订单需求日期选 BOM；属于 M2-02-02。
3. 目前供应订单、BOM 等表尚无统一单调版本字段；版本清单仅覆盖订单和库存，hash 覆盖参与计算的数值；全量 source revision 属后续增强。
4. 跨系统独立真实服务及源头版本证明不在本阶段；此锁仅保证**同一个 PostgreSQL 模拟数据库内**一致性。
5. PostgreSQL 集成测试必须配置 TEST_DATABASE_URL 并真实执行；未配置导致 SKIP 不可作为 M2-01 签核证据。

## 强制签核门槛（M2-01 保持未签核）
- 在独立 PostgreSQL 16+ 测试库执行 `schema.sql`、`003_v03.sql`、`004_snapshot_fence.sql`。
- 执行 `TEST_DATABASE_URL=... python -m pytest -q`，数据库用例零跳过、零失败。
- 重复 seed、运行、回读，验证 input_hash、pegs 和 snapshot_versions 一致。
- 双连接并发更新来源表时，验证计算期间更新被阻塞，或锁超时导致计算失败；不能产生混合版本计划。
- 保留实际执行日志、PostgreSQL 版本、迁移版本和签核记录。
