# Industrial AI PaaS Lab｜M3-02 V0.2 开发候选包

**基线**：M3-02 V0.1.1（用户提供真实 PostgreSQL 16 测试日志：22 集成测试、143 全量测试通过）。

**新增**：`app/agent_policy.py` 策略白名单/状态/主体/参数治理；`app/agent_audit.py` 审计辅助；`database/011_agent_governance.sql`；`tests/test_agent_governance_v02.py`；跨模块契约文档。

**运行**：Windows 解压后在 `m2_pg16_gate` 目录执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\run_pg16_gate.ps1
```

脚本会**删除并重建 `industrial_lab_test`**。使用 Python 3.14 + Docker PostgreSQL 16。日志保存于 `m2_pg16_gate/pg16_integration.log` 和 `pg16_full_regression.log`。

**验收**：本包仅为 V0.2 开发候选；本地非集成测试已运行，Windows 真实 PostgreSQL 16 仍待执行。不能仅凭 `TEST COMMANDS PASSED` 宣布签核，须检查两份日志全部强制测试且无失败/跳过。
