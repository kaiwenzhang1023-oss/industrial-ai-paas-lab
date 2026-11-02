# Industrial AI PaaS Lab V1.1 — W3-03

## 本次改动

- Workbench MRP 执行按钮就地展示进行中、成功 Run ID、错误信息；请求进行中禁用按钮。
- 计算详情展示结构化证据：Run ID、状态、订单范围、快照日期、规则版本、Input Hash、Result Hash。
- Pegging 对 `root_order_id` 为空的记录显示「未归属（原始为空）」，不推断订单归属；显示已关联/未归属行数。
- 新增 `backend/tests/test_w3_03_ui_contract.py`。

## 兼容与安全边界

- 保持现有 V1.0 页面和后端 API；未修改 MRP 核心算法。
- 未开放 ERP 写入路由，未变更数据库结构。
- 不在生产环境部署；仅对 Neon `v11-w2-stage3-test` 隔离分支做人工验收。
- Hash 是持久化一致性证据，不等于外部独立审计认证。
- Pegging 空根订单只表示当前持久化记录未给出归属，不能简单解释为算法失败或自动归到当前订单。

## Windows / Python 3.14.6 离线验证

进入 `m2_pg16_gate/backend`：

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -e ".[test]"
.\.venv314\Scripts\python.exe -m pytest -q -m "not integration"
```

本次打包前在 Linux Python 环境离线回归：`157 passed, 5 skipped, 31 deselected`；仍须在 Windows Python 3.14.6 复核。

## 本地 Workbench 浏览器验收

1. 核对 `TEST_DATABASE_URL` 和 `DATABASE_URL` 主机与 Neon 隔离分支 Connect Host 完全一致，切勿使用生产分支。
2. 先设置 `PUBLIC_READ_ONLY=1`、`DEMO_WRITE_ENABLED=0`，启动本地服务并打开 `http://127.0.0.1:8000/workbench/`；确认历史 Run 详情的证据面板和 Pegging 未归属标识。
3. 如需写入验收，在确认隔离分支后停止服务；设置 `PUBLIC_READ_ONLY=0`、`DEMO_WRITE_ENABLED=1` 和临时 `DEMO_OPERATOR_KEY`，重新启动服务。
4. 在 MRP 页面选择 `SO-2026-001`、快照 `2026-11-20`，点击执行一次；验证按钮进行中禁用、成功 Run ID 就地显示、详情可读取。
5. 完成后停止服务，恢复 `PUBLIC_READ_ONLY=1`、`DEMO_WRITE_ENABLED=0`，清除 `DEMO_OPERATOR_KEY`。不要在聊天中分享密钥或连接串。

## 已知边界

- 当前 Pegging 列表仍按后端现有上限展示（部分明细 `LIMIT 500`），计数仅指本次接口返回的记录，不是全库统计。
- 目前只做订单归属透明化，不改变供需分配规则；后续可引入业务维度筛选、供给来源详情联动和独立追溯验收。
