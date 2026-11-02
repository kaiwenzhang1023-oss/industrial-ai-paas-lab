# E06-13｜跨测试重复执行与数据隔离验证（RC3 源码审计）

## 1. 审查边界

本轮基于 RC3 完整源码开展静态审查，并执行 E06 隔离守卫自身的纯单元测试。
没有连接用户 Docker、没有运行迁移、没有写入或清理任何 PostgreSQL 数据。

## 2. 已完成的验证

| 检查项 | 结果 | 证据 |
|---|---|---|
| E06 DB 守卫纯单元测试 | PASS | `tests/test_e06_isolated_db_guard.py`：24 passed |
| pytest collection 前置拦截 | 源码确认 | `conftest.py` 使用 `pytest_collection_modifyitems` |
| 默认禁止数据库测试 | 源码确认 | 未设置 `E06_ALLOW_ISOLATED_DB_TESTS=YES` 时标记 DB 测试 skip |
| 显式启用后的 DSN 校验 | 源码确认 | `check_environment(verify_server=True)` |
| 数据库身份核验 | 源码确认 | database/user/PG16/primary 四项检查 |
| DB 测试文件分类漏网扫描 | PASS（静态） | 仅 guard 自身和纯合同测试出现连接关键词；未发现遗漏的实际 DB 测试模块 |

## 3. 关键发现

### 3.1 E06 守卫本身设计方向正确

`e06_isolated_db_guard.py` 对以下条件 fail-closed：

- 仅接受 PostgreSQL URL DSN；
- 仅允许 localhost / 127.0.0.1；
- 仅允许配置的端口；
- 数据库名称必须在 allowlist；
- E06 数据库必须使用 `v18_tester`；
- 禁止 `DATABASE_URL` 作为生产回退；
- 连接后再次核对数据库名、用户、PG16 版本及非只读副本。

`conftest.py` 在 collection 阶段拦截 DB 测试，避免先执行 fixture 再检查目标库。这一点应保留。

### 3.2 不能把所有历史集成测试统一指向 E06 数据库

这是本阶段最重要的隔离结论。

源码存在明确绑定历史数据库的测试，例如：

- V12 测试要求 `industrial_lab_v12_test`；
- V13/MES 测试要求 `industrial_lab_v13_test`；
- V14/SRM/Mapping 测试要求 `industrial_lab_v14_test`；
- V15 MCP 测试使用 `M1_TEST_DATABASE_URL`，并依赖 V15 专属角色、schema 和权限对象；
- E06 新验收库为 `industrial_ai_v18_e06_acceptance`。

这些测试不是仅靠修改环境变量就能迁移到 E06 库的。部分测试会直接断言数据库名、表数量、角色或既有 schema。把 `TEST_DATABASE_URL` 全局改成 E06 会造成错误失败，甚至使未做硬编码身份检查的旧测试写入错误数据库。

**结论：历史测试库必须保持各自的 DSN；E06 数据库只承载明确设计为 E06 的集成测试。**

### 3.3 E06 目前的 DSN allowlist 尚不能证明 Docker 容器身份

当前守卫验证了本地地址、端口、数据库名、用户和 PostgreSQL 16 主库身份，但没有验证 PostgreSQL 服务一定来自容器 `industrial-v18-pg16-test`。

如果本机另有 PostgreSQL 服务监听允许端口，并且恰好存在同名数据库和用户，现有身份检查理论上仍可能通过。

建议下一次硬化时增加一个由管理员预先设置的容器身份标记（例如专用数据库参数或只读身份表），并由守卫查询核对；不要仅凭端口映射推断容器身份。该标记应在 E06 数据库内创建，不涉及其他数据库。

### 3.4 当前 allowlist 接受的历史库仍须遵守独立 DSN 规则

`ALLOWED_TARGETS` 同时列有 V12/V13/V14/V15 历史测试库和 E06 数据库。这是为了兼容历史测试，但意味着启用数据库测试时，所有已配置的 DSN 都会被逐一验证。

执行前必须明确每个环境变量实际指向哪个库。不得为了方便，把多个变量都复制成 E06 的 DSN。

### 3.5 自动清理不应覆盖持久化语义测试

前一阶段识别的 worker lease、outbox 重试、CAS 并发、append-only audit 测试，确实需要跨事务可见性或持久化证据。它们不能统一改成事务回滚。

E06-13 的重复执行判定应采用：
- 测试专属 UUID / workflow ID / event ID；
- 对每个测试创建的数据按业务主键统计；
- 对确实需要提交的测试，使用显式命名空间；
- 对 append-only 审计，记录预期保留的数据，而不是尝试删除；
- 同一套 E06 测试串行运行两轮，对比业务基线与测试数据增量。

## 4. 尚未通过的验证（必须明确）

以下项目尚未由本轮执行证明：

1. 用户 Docker PG16 上 E06 数据库的 live identity gate；
2. E06 对应完整迁移集是否已全部执行；
3. Python 3.14 下数据库集成测试连续两轮运行；
4. 两轮运行后的表级数据增量、重复键和孤儿记录检查；
5. Windows PowerShell 5.1 一键门禁；
6. 历史 V12/V13/V14/V15 测试库未受影响的现场证据。

本轮不能据此宣布 E06-13 完成，更不能宣布 V1.8 最终工程验收完成。

## 5. 下一步执行顺序

1. 先确认 E06 迁移清单及实际已执行版本，不重放已成功迁移。
2. 为 E06 测试建立独立 DSN：`TEST_DATABASE_URL` 指向 `industrial_ai_v18_e06_acceptance`，端口使用 Docker 映射的 `55432`。
3. `M1_TEST_DATABASE_URL`、`V15_BUSINESS_DATABASE_URL` 等历史测试 DSN 不得擅自改写；本轮 E06 专项测试不需要的变量保持 unset。
4. 设置 `E06_ALLOW_ISOLATED_DB_TESTS=YES` 后，先跑单个 E06 目标测试模块。
5. 通过后串行执行 E06 集成集合两轮，保存两轮 pytest 报告与数据库行数快照。
6. 做重复执行差异核验，再运行 Windows 门禁。

## 6. E06-13 当前结论

**源码审查完成；纯单元测试 24/24 通过；真实 PG16 重复执行门禁仍待现场验证。**

本阶段没有修改生产代码、迁移文件或数据库。没有删除任何数据。
