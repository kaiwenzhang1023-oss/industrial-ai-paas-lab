# M3-02 V0.2｜策略执行、工具权限与审计契约（冻结候选）

## 基线
以用户在 Windows PostgreSQL 16 实测 **143 passed / 22 integration passed** 的 M3-02 V0.1.1 为唯一基线。所有旧版测试必须继续通过。新增 `011_agent_governance.sql`，保留原有 `010_agent_harness.sql` 与历史表结构。

## V0.2 约束
- 工具授权：默认拒绝；精确工具名与参数字段；`recommendation-agent-v1` 主体；工作流必须 `GENERATING_ADVICE`；`mrp.read` 限制 `mrp_run_id`，其他读工具限制 `order_id`。
- 允许工具：`order.read`、`bom.read`、`inventory.read`、`mrp.read`；不存在 ERP PR 写入权限。
- 策略执行：默认仅 `offline-contract-v1`，外部注入模型须由显式策略授权；限制工具调用次数与 BUY 行数；必须保留 `HUMAN_REVIEW_REQUIRED` 标记。MRP 采购数量不可被 Agent 修改。
- 审计：`platform.agent_tool_audit` 记录允许/拒绝/适配器异常，保留工作流、主体、工具、策略版本、原因、参数哈希与结果哈希；不记录业务原始数据。审计行仅追加，不提供删除 API。
- 持久化：既有 `agent_drafts` 幂等键 `(workflow_id, workflow_version)` 保留；Workflow Inbox/Outbox/Audit 事件语义不变。
- 边界：此版本是 MCP 风格工具治理适配器，**不是标准 MCP 协议服务器**，也未接入真实 LLM；Agent 仍不得创建 ERP PR。

## 数据契约（不得擅自更改）
- M2 `read_integrated_run()['result']['mrp_lines']` 不承诺 `kind` 字段。BUY/MAKE 继续由 `mock_erp.materials.make_buy` 查询，缺失物料应显式失败。
- `create()` 产生 WORKFLOW_CREATED Outbox；首次 START 产生 START Outbox；重复 START 不新增事件。原有测试不得回退为 1 条总数。
- `agent_tool_audit` 外键引用 `platform.workflow_instances(instance_id)`，绝不新建另一套 `workflow_id` 主表。

## 测试门禁
1. 旧版 143 项全量回归通过；2. 新增策略与审计单测通过；3. 新增 PostgreSQL 审计集成测试通过；4. 数据库测试不得 skipped；5. 多 Worker、租约、重试、死信、MRP 持久化恢复回归通过。

## 已知风险
- 目前只记录经 ToolGateway 调用的工具决策；前置 MRP 事实构建的数据库读取尚未纳入工具级审计，后续应统一受控适配器。
- 审计成功写入与 Draft 状态推进属于不同事务；允许追踪已读取但后续 Draft 失败的场景，尚未提供完整分布式事务保证。
- 未做真实外部 MCP Server 互操作测试、真实模型安全评估、长任务超时及生产级负载测试。
