# V1.5 独立完整工程包（源码整合版）

本包包含项目源码、017/018/019 数据库迁移、五个 MCP 适配器、单元测试、Docker PG16 集成测试和一键脚本。**不包含 Windows Python 虚拟环境和 PostgreSQL 数据库数据**。

## 第一次运行
1. 解压本 ZIP 到 `D:\Download\Chatgpt\Industrial AI PaaS Lab\Industrial_AI_PaaS_Lab_V1.5_Standalone_Full`。
2. 暂时保留旧 `Industrial_AI_PaaS_Lab_V1.5_M1-01_Full_Source_Candidate` 目录，因为里面有 `.venv314`。
3. 在新目录打开 PowerShell，执行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_V15_FULL_GATE.ps1`。
4. 脚本会**仅首次**复制已有 `.venv314` 到当前目录；此后只使用本目录环境。自动重建两个环境变量，无需手动配置，不运行 pip。
5. **只有当新目录下完整 PG16 门禁通过**，并确认 `.venv314` 在新目录存在、重开 PowerShell 仍可单独通过测试后，才删除旧版本目录与旧 ZIP。

## 删除范围
可清理的是 `Industrial AI PaaS Lab` 父目录下旧候选源码文件夹及历史 ZIP；不要删除本独立目录、Docker 容器、Docker volume、任何数据库备份、个人项目数据或尚在使用的其他项目目录。**不要用递归通配符自动批量删除整个父目录**。

## 门禁
目前仍是候选源码。真实 Docker PG16 验收未在此环境执行。五个业务工具默认禁用，未完成标准 MCP 传输与 44 黄金案例之前不得称生产发布完成。
