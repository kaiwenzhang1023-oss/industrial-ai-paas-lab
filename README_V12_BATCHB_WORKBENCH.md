# Industrial AI PaaS Lab V1.2 — Batch B Workbench

## 交付范围
- 新增 WMS 库存工作台：通过 PostgreSQL 只读 API 查询库存，按物料、仓库筛选，分页展示批次、在手、预留、冻结、可用量、快照和版本。
- MRP 详情页展示新运行的 `wms_stock_attribution` 持久化来源证据；历史运行无此证据时明确告知，不伪造来源。
- 保留 ERP、MRP 算法、Workflow、Agent 和写入权限门禁；没有新增写接口或数据库迁移。
- 计划归属不代表 WMS 实际预留、拣货、出库或跨仓可达性。

## Windows 离线回归
在 `m2_pg16_gate\backend` 目录运行：

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -e ".[test]"
.\.venv314\Scripts\python.exe -m pytest -q -m "not integration"
```
构建环境：179 passed, 5 skipped, 31 deselected。Windows 需独立验证。

## 只读浏览器验收
确认 `DATABASE_URL` 指向经核实的 Neon 测试分支，禁止连接生产数据库进行本地验收。

```powershell
$env:PUBLIC_READ_ONLY="1"
$env:DEMO_WRITE_ENABLED="0"
Remove-Item Env:DEMO_OPERATOR_KEY -ErrorAction SilentlyContinue
.\.venv314\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/workbench/`，核验 WMS 库存页面、WH-A 筛选、物料筛选、库存版本/快照与 MRP 历史记录提示。旧运行没有 V1.2 计划归属证据是预期结果。

## 真实数据库集成验收边界
尚未执行 Neon 写入集成验收。Neon Free 不能创建额外隔离分支时，不在 V1.1 冻结分支执行测试写入。请另建 Neon 项目或使用独立本地 PostgreSQL，经隔离确认后再运行集成测试。

当前版本为 Batch B RC1，不是 V1.2 Final。
