# E06-16｜最终验收收口与交付冻结（RC1）

## 本阶段定位

这是基于 E06-15 完整源码生成的单一收口候选包。它不是新增业务功能版本，也不是已经签署的生产 FINAL。现场最终门禁通过后，才能签署 V1.8 FINAL。

## 执行顺序

1. 解压本 ZIP。
2. 在项目根目录打开 **Windows PowerShell 5.1**。
3. 执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& ".\E06_16_FINAL_FREEZE_GATE.ps1"
```

4. 将完整输出及生成的 `E06_16_FINAL_EVIDENCE_时间戳` 目录保留并提交复核。

## 门禁行为

- 要求 Windows PowerShell 5.1、Python 3.14、Docker PG16。
- 只读核验 `industrial_ai_v18_e06_acceptance` 身份。
- 只读核验 `industrial_ai_v18_e06_migration_replay` 的 11 条核心迁移账本、Schema、业务表、索引、约束和外键。
- 暂时清除当前 PowerShell 进程中的数据库 DSN 与数据库测试 opt-in，执行全量离线 pytest；脚本结束后恢复原环境变量。
- 生成 JUnit XML、逐测试 skip CSV/Markdown、源码清单校验和最终验收报告。
- 不执行任何 SQL 迁移，不执行数据库写入，不删除数据库、Schema、表或历史数据。
- 不访问 Neon、Render 或生产环境。

## 注意

`E06_16_FINAL_FREEZE_GATE.ps1` 是最终只读验收门禁，不会自动把未通过的结果改写成 PASS。任何测试失败、collection error、非预期 skip 或数据库基线不符都会保持 HOLD。

E06-01～E06-11 和 E06-15 原始运行证据若保存在其它本地目录，最终交付前需要收集进 `acceptance/E06-01_to_E06-15/`；本 ZIP 不伪造缺失证据。
