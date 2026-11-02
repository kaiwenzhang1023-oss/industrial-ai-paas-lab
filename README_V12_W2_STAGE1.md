# V1.2-W2 Stage 1：WMS Read-only Adapter

已新增 `app/wms/{models,adapter,api}.py` 和 `tests/test_wms_v12_unit.py`。

## API
- `GET /api/v1/wms/inventory-balances?material_id=A&warehouse_id=WH-A&limit=50&offset=0`
- `GET /api/v1/wms/inventory-summary?material_id=A&warehouse_id=WH-A`

仅从 PostgreSQL `mock_wms.inventory_balances` 读取，不写库，不降级到模拟 JSON；分页默认 50、最大 100；余额按物料/仓库/批次稳定排序；金额与数量使用 Decimal；`available=on_hand-reserved-blocked`。

## 本轮未实现
- 库存交易、预留写入、库存历史 as-of 查询、仓库级 MRP 净需求、STOCK 仓库批次 Pegging 来源关联、Workbench WMS 专属页面。
- 不声称 WMS 已完成端到端验收。

## 安装与验证（Windows Python 3.14.6）
进入 `m2_pg16_gate/backend`：
```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -e ".[test]"
.\.venv314\Scripts\python.exe -m pytest -q -m "not integration"
```
当前构建环境测试结果：`168 passed, 5 skipped, 31 deselected`。Windows 与 Neon 尚待验收。

## 只读数据库验收
确认连接 Host 为新建 `v12-wms-test` 分支后：
```powershell
$env:PUBLIC_READ_ONLY = "1"
$env:DEMO_WRITE_ENABLED = "0"
.\.venv314\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
打开 `/docs` 测试两条 WMS GET API。不要开启写入或执行数据迁移。

## 兼容性
V1.1 ERP/MRP/Workflow/Agent 原代码保留；`app/main.py` 仅增量 include WMS router；没有修改数据库 Schema 和 MRP 算法。生产 Render V1.0 未部署。
