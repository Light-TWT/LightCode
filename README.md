# LightCode

LightCode 是一个独立实现的、本地优先、可视化的编码智能体，面向具备基础编程经验的开发者。产品目标是让计划、工具活动、代码差异、审批请求与验证结果可见、可控、可追溯；它不是任何现有编码智能体项目的分支、重命名或源码延续。

## 当前状态

项目已完成 **Phase 0.5：本地运行时基础**：

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia，以及 Mock/HTTP/SSE 服务适配边界。
- 后端：FastAPI、SQLite、确定性 Mock Runtime、REST API 和 SQLite 持久化事件的 SSE 回放。
- 运行时仍是 Mock：不访问真实项目目录、不写源码、不运行命令、不调用模型、不处理密钥。
- 当前验证基线：前端 37 个测试通过，后端 16 个测试通过，前端 `vue-tsc + vite build` 通过。

下一阶段是 **Phase 1：安全变更 MVP**。其范围已冻结为：服务端静态注册授权工作区、受控只读工具、服务端生成的确定性 ChangeSet、显式审批、单个既有 UTF-8 文本文件的原子替换，以及不启动外部进程的内建完整性验证。详细约束见 `docs/phase1-safety-contract.md`。

## 快速入口

1. 阅读 [项目规则](AGENTS.md)。
2. 阅读 [产品架构](docs/architecture/lightcode-local-first-agent-design.md)。
3. 阅读 [Phase 0.5 运行时基础计划](docs/2026-07-23-phase-0-5-runtime-foundation.md) 了解当前合约与实现证据。
4. 阅读 [设计原型说明](docs/design/README.md) 与相关 HTML 原型；原型只定义视觉和交互，不是运行时代码。
5. Phase 1 开始前阅读 [安全契约](docs/phase1-safety-contract.md) 与 [工作区注册规范](docs/workspace-registration.md)。

## 目录

```text
frontend/       Vue 应用、类型、Pinia store 与 Mock/HTTP/SSE 服务适配器
backend/        FastAPI + SQLite 的确定性 Mock Runtime
electron/       阶段 3 桌面 shell 预留
docs/           架构、设计原型、阶段计划与安全契约
scripts/        可复现的开发、验证和打包脚本预留
```

## 本地开发

后端与前端可独立启动；当前 API 模式仍只提供确定性 Mock 数据。

```bash
# 终端 1：从 backend/ 启动后端
python -m pip install -e "backend[dev]"
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 2：从 frontend/ 启动前端 API 模式
cd frontend
VITE_LIGHTCODE_RUNTIME=api VITE_LIGHTCODE_API_BASE_URL=/api/v1 npm run dev
```

Windows PowerShell 下设置前端 API 模式：

```powershell
$env:VITE_LIGHTCODE_RUNTIME = "api"
$env:VITE_LIGHTCODE_API_BASE_URL = "/api/v1"
npm run dev
```

验证命令和临时 SQLite 数据库的使用方式见 `backend/README.md` 与 `frontend/README.md`。

## 非目标

在 Phase 1 完成前，项目不会实现真实模型、Electron、本地文件夹选择、任意 Shell、依赖安装、网络下载、Git 写操作、密钥管理、云同步或多用户协作。
