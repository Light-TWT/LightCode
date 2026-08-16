# LightCode

LightCode 是一个独立实现的、本地优先、可视化的编码智能体，面向具备基础编程经验的开发者。产品目标是让计划、工具活动、代码差异、审批请求与验证结果可见、可控、可追溯；它不是任何现有编码智能体项目的分支、重命名或源码延续。

## 当前状态

LightCode 已完成可发布的 Windows 桌面端 MVP。产品入口是基于已注册工作区的聊天式 Agent，Web 开发模式和 Electron 桌面模式共用 FastAPI、SQLite、Vue 和安全变更闭环。

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia；产品运行时使用 HTTP/SSE 服务，测试仍使用类型化 fixture。
- 后端：FastAPI + SQLite；工作区访问、模型出网、ChangeSet、审批和原子写入均由服务端控制。
- 模型：OpenAI-compatible Provider 默认关闭。模型只能回答问题或提议单文件 ChangeSet，不能写文件、执行命令或决定审批。
- 桌面端：Electron 沙箱渲染进程 + 受限 IPC + FastAPI sidecar + Windows Credential Manager + NSIS 安装器。
- 验证基线：后端 303 passed / 2 skipped，前端 141 passed，Electron 12 passed；具体命令见各子目录 README。

## 快速入口

1. 开发时阅读本地 [项目规则](AGENTS.md)；该文件是内部规则，不属于公开发行文档。
2. 阅读 [产品架构](docs/architecture/lightcode-local-first-agent-design.md)。
3. 涉及真实文件变更时阅读 [安全契约](docs/phase1-safety-contract.md) 与 [工作区注册规范](docs/workspace-registration.md)。
4. 阅读 [设计原型说明](docs/design/README.md) 与相关 HTML 原型；原型只定义视觉和交互，不是运行时代码。
5. 阅读 [文档索引](docs/README.md) 了解各文档角色与推荐阅读顺序。

## 目录

```text
frontend/       Vue 应用、类型、Pinia store 与 HTTP/SSE 服务适配器
backend/        FastAPI + SQLite：Phase 1 真实安全变更闭环与 Phase 2 模型提议（默认关闭）
electron/       Phase 3 桌面端：Electron 安全外壳 + FastAPI sidecar + NSIS 安装器
docs/           架构、安全契约、桌面设计与发布清单
scripts/        可复现的构建、验证与打包脚本
```

## 本地开发

后端与前端可独立启动。开发期前端默认使用测试 fixture；连接真实后端时显式启用 API 模式。

```bash
# 终端 1：从 backend/ 启动后端
python -m pip install -e "backend[dev]"
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 2：从 frontend/ 启动前端
cd frontend
VITE_LIGHTCODE_API_BASE_URL=/api/v1 npm run dev
```

Windows PowerShell 下设置前端 API 模式：

```powershell
$env:VITE_LIGHTCODE_API_BASE_URL = "/api/v1"
npm run dev
```

后端环境变量清单见 [`backend/.env.example`](backend/.env.example)（复制为 `backend/.env` 使用，`.env` 已被忽略，绝不提交）；说明见 [`backend/README.md`](backend/README.md)。

验证命令和临时 SQLite 数据库的使用方式见 `backend/README.md` 与 `frontend/README.md`。

## 非目标

模型 Provider 是**受限、默认关闭、仅提议**的能力：模型不写文件、不执行命令、不调用网络工具、不管理包、不写 Git、不决定审批。项目仍**不**实现以下能力：

- 前端输入、持久化、同步、回显 API Key；
- Shell、subprocess、PowerShell、cmd、pytest、npm、pip、包管理、网络工具或下载；
- Git 写操作；
- 删除、新建、重命名、移动、二进制或多文件 ChangeSet；
- 自动批准、自动修复循环或模型直接写文件；
- 模型列表自动探测、自由 Provider URL 或隐式代理；
- 自动模型发现、自由 Provider URL 或隐式代理。

部署与打包相关约束见 `electron/README.md` 与 `docs/architecture/lightcode-local-first-agent-design.md`。

Phase 1 已实现的后端真实文件能力与 Phase 2 模型提议闭环，仍分别受 `docs/phase1-safety-contract.md` 与 `docs/phase2-model-provider-design.md` 严格约束（仅受控只读工具 + 单文件原子替换 + 内建验证 + 版本绑定审批）。
