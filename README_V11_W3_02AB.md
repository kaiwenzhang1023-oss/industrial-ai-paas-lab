# Industrial AI PaaS Lab V1.1 — W3-02A/B 增量交付

## 范围
- 基于 W2 Stage 3 原 ZIP 增量修改，保留 V1.0 Agent / Workflow / MRP 入口与数据库结构。
- 新增受控 POST `/api/v1/workbench/mrp/runs`，请求 JSON：`{"as_of":"2026-11-20","order_scope":{"mode":"selected_orders","order_ids":["SO-2026-001"]}}`；全局模式为 `{"mode":"global","order_ids":[]}`。
- **不新增 ERP 写入接口**；复用 `app.db.integrated.run_integrated` 计算与持久化。
- MRP 页面从 `GET /api/v1/erp/sales-orders?status=CONFIRMED&limit=100` 加载订单，支持多选、全局/指定范围、快照日期、操作员密钥；计算后加载持久化 MRP 详情。
- MRP 详情从 `source_versions.v11_order_scope` 识别范围并显示 `input_hash` / `result_hash`。
- 合入 W2 `_IncludedRouter` 单元测试修复；新增 6 项 W3 安全及请求契约测试。

## 安全
- 新计算接口需同时满足 `PUBLIC_READ_ONLY != 1`、`DEMO_WRITE_ENABLED=1`、`DEMO_OPERATOR_KEY` 非空、`X-Operator-Key` 匹配；否则 403。
- 仅用于本地或隔离测试分支。**不要把 Neon 测试分支 URL、操作员密钥提交至 Git 或上传公开部署**。
- 新接口会提交新的 MRP 运行记录（并非只读或自动回滚）；没有修改 ERP 源订单。
- 保留 V1.0 原有接口，不代表所有历史 POST 接口都具备同样的强制密钥要求；生产应保持 `PUBLIC_READ_ONLY=1`。

## 本地测试（Windows Python 3.14.6）
在 `backend` 目录，使用已有 `.venv314`：

```powershell
.\.venv314\Scripts\python.exe -m pytest -q -m "not integration"
```

交付构建环境实测：`155 passed, 5 skipped, 31 deselected`；Node `--check` 通过。**尚未对你的 Neon 隔离分支执行 W3 端到端写入验收。**

仅在确认 `DATABASE_URL` 指向 `v11-w2-stage3-test` 的 Neon Host 后，才可在当前 PowerShell 临时设置：

```powershell
$env:DATABASE_URL = $env:TEST_DATABASE_URL
$env:PUBLIC_READ_ONLY = "0"
$env:DEMO_WRITE_ENABLED = "1"
$env:DEMO_OPERATOR_KEY = Read-Host "仅用于本地测试的操作员密钥"
.\.venv314\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器访问 `http://127.0.0.1:8000/workbench/` → MRP 计划 → 刷新 ERP 订单 → 指定订单 → 选择订单 → 输入操作员密钥 → 执行 MRP。测试完成后清理会话变量，并确认隔离分支新增的 Run ID。

## 下一步 W3-03
- 更丰富的 Pegging 订单筛选、来源证据视图、运行记录对比与 JSON 导出。
- 安全与边界场景的 Neon 隔离分支人工端到端验收。
