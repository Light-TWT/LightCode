# 开发与验证脚本

`scripts/` 用于保存可复现的开发、验证和打包脚本。当前 Phase 0.5 的验证命令已由前后端包配置提供，尚不需要重复脚本：

```bash
# backend/
python -m pytest -q

# frontend/
npm run test
npm run typecheck
npm run build
```

当新增脚本时，必须遵循以下约定：

- 脚本只封装可重复的开发、测试或构建流程；不得隐藏文件写入、Shell 放行、网络下载、依赖安装或 Git 写操作。
- 脚本名称使用小写 kebab-case，并明确表达动作，例如 `verify-backend.sh`、`verify-frontend.sh`。
- 脚本必须在对应 README 或阶段计划中记录用途、输入、输出和验证方式。
- Phase 1 的真实文件能力测试应使用隔离 fixture 工作区，不得指向开发者任意本地目录。
- 不得在脚本中记录或输出密钥、token、密码或真实工作区根路径。

Phase 1 的安全边界见 `../docs/phase1-safety-contract.md`。
