# Industrial AI PaaS Lab V1.1 — W3-04 冻结候选（RC1）

## 状态与证据

**状态：W3-04 RC1（冻结候选），非生产发布。**

- 基于 W3-03 完整项目 ZIP 增量打包；没有改动 MRP 计算核心、ERP API、数据库迁移及 Workbench 页面逻辑。
- 新增 `backend/tests/test_w3_04_freeze_gate.py`，共 6 项离线门禁：只读拒绝、全局计算转发、指定订单转发、ERP 只读、旧 Workbench 路由、UI 反馈与归属标识。
- 本打包环境离线回归：**163 passed, 5 skipped, 31 deselected**；`node --check app/web/app.js` 和 Python compileall 通过。
- 用户此前在 Windows Python 3.14.6 上完成 W3-03 **157 passed, 5 skipped, 31 deselected, 1 warning**，且通过 W3-02 指定订单真实计算（Run `M2-b8b5295014b4466e8661`）和 W3-03 只读证据/Pegging 截图验收。
- **尚未执行**本 RC1 在用户 Windows 环境的 163 项回归、W3-03 新版执行反馈/防重复提交的浏览器验收、全局模式实际执行回归、31 项集成测试的本版本全量复跑。不得将其写成已通过。

## Windows Python 3.14.6 离线验收

进入 `m2_pg16_gate/backend` 后：

```powershell
py -3.14 -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install -e ".[test]"
.\.venv314\Scripts\python.exe -m pytest -q -m "not integration"
```

预期 **163 passed, 5 skipped, 31 deselected**。如结果不一致，保留完整输出并暂停冻结。

## 隔离分支只读验收（不产生写入）

1. 使用 Neon `v11-w2-stage3-test` 的连接串配置 `TEST_DATABASE_URL` 与 `DATABASE_URL`；先在 Neon Console 对照 Host。不要在聊天、截图、日志中泄露凭证。
2. 设置 `PUBLIC_READ_ONLY=1`、`DEMO_WRITE_ENABLED=0`，并删除 `DEMO_OPERATOR_KEY`。
3. 启动 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`，访问 `/workbench/`，强制刷新。
4. 回归六个导航页：经营总览、销售订单、BOM 与库存、MRP 计划、Agent 建议、工作流与审计。只查看既有数据，不触发写入操作。
5. 查看历史 Run `M2-b8b5295014b4466e8661`：范围 `SO-2026-001`、快照 `2026-11-20`、Input/Result Hash、Pegging 9 条关联和 8 条原始未归属（该计数是此前页面返回的 17 条，不代表全库统计）。
6. 保持只读模式，在按钮上尝试提交会被后端拒绝（HTTP 403）；建议通过浏览器 Network 验证，不要把密钥填进截图。

## 受控写入与交互验收（需要用户单独确认）

只有完成隔离分支 Host 核验、明确接受新增持久化记录后，才设置 `PUBLIC_READ_ONLY=0`、`DEMO_WRITE_ENABLED=1` 和临时 `DEMO_OPERATOR_KEY`。浏览器选择 `SO-2026-001`、日期 `2026-11-20`，点击一次；观察按钮立即禁用/显示「MRP 计算中…」，成功时按钮附近显示 Run ID、自动展示详情，失败时出现本地错误提示。使用浏览器 Network/服务日志核对仅一个 POST。注意：**该接口没有服务端幂等键，不能把前端禁用按钮视为跨刷新/多窗口的幂等保证**。全局模式若做真实执行也会创建新运行记录，需另行确认。

验收后停止 Uvicorn，恢复只读设置并清除密钥。不要连接 Render V1.0 生产数据库或执行 ERP 写入。

## 最终冻结条件

- [ ] Windows Python 3.14.6 本版本 163 项离线回归通过
- [x] W3-02 指定订单 Neon 隔离分支真实执行（历史已验证）
- [x] W3-03 计算证据和 Pegging 只读浏览器展示（历史已验证）
- [ ] W3-03 新版执行反馈/失败反馈/防重复提交浏览器验收
- [ ] 全局模式兼容性人工回归（可先只读检查旧运行记录；真实运行需单独确认）
- [ ] V1.0 六个页面无回归问题
- [ ] 用户确认冻结 W3 基线

已知边界：Pegging 未归属值不得推断；Hash 仅作一致性证据；前端防重复提交仅当前页面生命周期；快照及详情有查询行数上限；尚未进行本版本真实数据库集成测试。上述项目未完成前只能称 RC1，不得称生产发布版。
