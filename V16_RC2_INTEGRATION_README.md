# V1.6 RC2 Integrated Dev — 开发交付（非生产发布）

基于 V1.6 Backend RC1 完整源码；保留原 Workbench 和既有 API，新增 `/workbench/v16.html` 入口及真实只读数据页。

## 已实现
- 复用 `/api/v1/portfolio/` 五个数据库查询端点（MES 工单、SRM 请购/异常、Mapping 版本/执行）。
- 查询只使用 `PORTFOLIO_READONLY_DATABASE_URL`，无该变量时返回 503，绝不退回 owner `DATABASE_URL`。
- 额外拒绝连接用户名为 `neondb_owner` / `postgres`；返回错误码，不向浏览器泄漏连接信息。
- V1.6 页面从真实 API 加载，展示空结果、网络错误、数据源和 request_id；无假数据兜底，DOM 使用 textContent 防止注入。
- MCP 仅显示工具元数据，匿名调用保持禁用。
- `v16_pg18_approved_dev_reference/` 为已在开发分支执行的 021-023 SQL 参考副本，**不得在开发分支再次执行**。

## 尚未完成 / 发布阻断
- 用户仅创建了 `mapping_v14_readonly NOLOGIN` 模板，未创建可登录且仅具最低权限的独立 API 读账号。当前模板仅能 SELECT Mapping 两个视图，不能读取 MES / SRM。**不能把 `neondb_owner` 连接串填入 `PORTFOLIO_READONLY_DATABASE_URL`。**
- 尚无 Neon 开发分支连接串、网络联调权限；本地只能执行无需数据库的 API 契约测试，不能宣称 PG18 E2E 已通过。
- 仍需检查 Mapping 视图字段及安全屏障、数据库角色继承、独立读账号对全部五个查询的授权与拒绝写入测试。
- 尚需按 MRP/WMS/MES/SRM/Workflow/Agent/MCP 全量 PostgreSQL 18 集成回归；生产分支、Render、GitHub main 均未修改。

## 本地运行
在 backend 目录安装项目依赖后启动现有 ASGI 服务；访问 `/workbench/v16.html`。测试：`python -m pytest backend/tests/test_v16_portfolio_contract.py -q`（从项目根目录运行，需设置 PYTHONPATH=backend）。

## 后续最小操作
先在开发分支设计可登录的最低权限读账号（只读五个 API 数据源，Mapping 仅视图）；独立 DSN 只放后端环境变量；在隔离服务上执行五个端点实测，再推进 PG18 全量门禁。
