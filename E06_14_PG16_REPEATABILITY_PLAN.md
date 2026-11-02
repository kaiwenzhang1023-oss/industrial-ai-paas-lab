# E06-14｜PG16 连续两轮重复执行门禁

## 1. 本阶段目标

在用户现有 Docker PostgreSQL 16 容器中，对 V1.8 Phase 4 的真实 PG16 持久化幂等测试执行连续两轮，验证：
- DSN 指向专用 E06 验收库；
- 数据库身份为 `industrial_ai_v18_e06_acceptance / v18_tester / PostgreSQL 16 primary`；
- 测试每轮创建独立随机 schema；
- 测试结束在 `finally` 中删除本轮随机 schema；
- 第二轮不依赖第一轮遗留状态。

## 2. 本轮完成的工程工作

新增 `E06_14_PG16_REPEATABILITY_GATE.ps1`，作为 Windows PowerShell 5.1 一键执行入口。

脚本安全约束：
- 只接受 Docker 容器 `industrial-v18-pg16-test`；
- 只接受镜像 `postgres:16`；
- 只接受映射端口 `55432`；
- 只接受数据库 `industrial_ai_v18_e06_acceptance`；
- 只接受用户 `v18_tester`；
- 在容器内先做数据库身份只读核验；
- 仅对该 E06 数据库读取 `pg_stat_user_tables` 快照；
- 密码以隐藏输入方式读取，不写入证据文件；
- 只运行 `tests/test_v18_phase4_live_pg16.py` 两次；
- 不创建数据库、不运行迁移、不执行全库清理、不删除历史数据；
- 每轮 JUnit 报告和前后快照写入独立证据目录；
- 脚本结束时清除本进程环境变量。

## 3. 源码级验证

审查 `test_v18_phase4_live_pg16.py`：
- 测试要求 `V18_ALLOW_ISOLATED_PG16=YES`；
- DSN 固定要求 `127.0.0.1:55432`、`industrial_ai_v18_e06_acceptance`、`v18_tester`；
- 运行时再次验证 PostgreSQL 16、主库和数据库身份；
- 每次运行使用 UUID 随机 schema；
- 所有业务 DDL 和 ledger 断言均限定在该 schema；
- `finally` 中执行 `DROP SCHEMA IF EXISTS <本轮随机 schema> CASCADE`。

该测试的清理对象是本测试自己创建的随机 schema，不是数据库或其他业务 schema。

## 4. 本地离线验证

从 RC3 源码提取 E06 guard、其测试文件及 `conftest.py` 后，执行纯单元测试：

**24 passed**

注意：当前执行环境为 Python 3.13，而项目要求 Python 3.14。因此该结果仅证明 guard 纯逻辑测试通过，不代替用户 Windows Python 3.14 结果。

## 5. 尚未完成的现场门禁

以下必须由用户本机 PowerShell 5.1 + Python 3.14 + Docker PG16 执行：
1. 输入现有 `v18_tester` 数据库密码；
2. 通过两轮真实 PG16 测试；
3. 检查两轮 JUnit 报告均为 1 passed；
4. 检查两轮结束后 `v18_gate_%` schema 无残留；
5. 审阅测试前后只读快照。

脚本对 `pg_stat_user_tables.n_live_tup` 的变化只给出提示，不把统计估算值作为严格失败条件；它是近似统计值，不能用作精确行数证明。随机 schema 清理与否以 schema inventory 和测试 finally 清理结果为准。

## 6. 执行方式

在解压后的 RC3 项目根目录打开 PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\E06_14_PG16_REPEATABILITY_GATE.ps1"
```

如果脚本不在项目根目录，可显式传入 `-ProjectRoot`。

## 7. 当前结论

**E06-14 自动化执行器与源码审查已准备完成；真实 PG16 两轮结果待用户现场运行。**

未连接 Neon / Render；未连接用户 Docker；未运行迁移；未修改数据库；未删除任何数据。
