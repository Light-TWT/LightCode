# LightCode

LightCode 是一个独立实现的、本地优先、可视化的编码智能体，面向具备基础编程经验的开发者。产品目标是让计划、工具活动、代码差异、审批请求与验证结果可见、可控、可追溯；它不是任何现有编码智能体项目的分支、重命名或源码延续。

## 当前状态

项目已完成 **Phase 0.5：本地运行时基础** 与 **Phase 1：安全变更 MVP（后端 T1-T7/T9 + 前端 T8 均已闭环）**：

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia，以及 Mock/HTTP/SSE 服务适配边界；Phase 1 真实闭环（注册工作区浏览、文件预览、内容搜索、真实任务创建/审批/SSE）已接入 Vue 视图。
- 后端：FastAPI、SQLite，以及两套隔离的闭环——
  - **Phase 0.5 Mock Runtime**：确定性种子数据、审批状态迁移、SQLite 持久化事件的 SSE 回放（仅供演示）。
  - **Phase 1 真实安全变更闭环**：服务端静态注册授权工作区、受控只读工具、服务端生成的确定性 ChangeSet、版本绑定审批、单个既有 UTF-8 文本文件的原子替换，以及不启动外部进程的内建完整性验证。安全不变量见 `docs/phase1-safety-contract.md`。
  - **Phase 2 模型提议（WP5–WP8，M4–M6，默认关闭）**：受限、默认关闭的 OpenAI-compatible Provider 子系统——模型只"提议"计划、受限只读工具请求与服务端独立生成的候选 ChangeSet，不写文件、不执行命令、不决定审批。覆盖 Provider 基础设施（仅环境变量、fail-closed、零密钥泄露）、LangGraph 编排、API-mode E2E、可观测性、预算/并发/故障门禁与敏感数据扫描；WP8 经用户确认采用**零新增第三方依赖**策略。设计细节见 `docs/phase2-model-provider-design.md`。
- 当前验证基线：前端 87 个测试通过（17 文件），后端 190 个测试通过（2 个因 symlink 环境跳过，含 WP8 新增 13 例），前端 `vue-tsc -b + vite build` 通过；Phase 1 API 模式 HTTP 全闭环与 Phase 2 API-mode E2E（含 browse token、SSE 续传、敏感数据扫描断言）均已覆盖。

Phase 1 前端与后端均已闭环，并于 **Phase 1R（安全收尾门禁 M1+M2+M3）** 关闭全部 3 个 P0 缺陷：敏感路径逐段 casefold 拒绝、审批绑定前置校验、多进程文件级 CAS 证明；M3 进一步落地不透明浏览令牌（取代自由路径）、SSE 预算/心跳/续传、前端 token 导航与运行时 DTO 校验。**Phase 2（WP5–WP8，M4–M6）** 已完成：Provider 基础设施默认关闭且 fail-closed、模型只提议（LangGraph 编排 + 服务端 ChangeSet）、API-mode E2E、可观测性、预算/并发/故障门禁与敏感数据扫描全部落地，后端全量 190 测试通过。下一阶段可择一推进：**Phase 3：桌面端交付**（Electron shell、FastAPI sidecar、原生文件夹选择、打包本地存储）或先行**易用性改进**。

## 快速入口

1. 阅读 [项目规则](AGENTS.md)。
2. 阅读 [产品架构](docs/architecture/lightcode-local-first-agent-design.md)。
3. 阅读 [Phase 0.5 运行时基础计划](docs/2026-07-23-phase-0-5-runtime-foundation.md) 了解当前合约与实现证据；Phase 1 后端实现证据见 `AGENTS.md` 问题修复记录与 `docs/phase1-safety-contract.md`。
4. 阅读 [设计原型说明](docs/design/README.md) 与相关 HTML 原型；原型只定义视觉和交互，不是运行时代码。
5. 涉及真实文件变更时阅读 [安全契约](docs/phase1-safety-contract.md) 与 [工作区注册规范](docs/workspace-registration.md)。
6. 阅读 [文档索引](docs/README.md) 了解各文档角色与推荐阅读顺序。

## 目录

```text
frontend/       Vue 应用、类型、Pinia store 与 Mock/HTTP/SSE 服务适配器
backend/        FastAPI + SQLite：Phase 0.5 Mock Runtime、Phase 1 真实安全变更闭环与 Phase 2 模型提议（默认关闭）
electron/       阶段 3 桌面 shell 预留
docs/           架构、设计原型、阶段计划与安全契约
scripts/        可复现的开发、验证和打包脚本预留
```

## 本地开发

后端与前端可独立启动；API 模式同时提供 Phase 0.5 确定性 Mock 数据与 Phase 1 受控真实工作区端点。

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

Phase 2 已实现的是**受限、默认关闭、仅提议**的模型 Provider：模型不写文件、不执行命令、不调用网络工具、不管理包、不写 Git、不决定审批。项目仍**不**实现以下能力（详见 `docs/2026-07-30-phase-2-model-and-dx-plan.md` §刻意不做）：

- 前端输入、持久化、同步、回显 API Key；
- Shell、subprocess、PowerShell、cmd、pytest、npm、pip、包管理、网络工具或下载；
- Git 写操作；
- 删除、新建、重命名、移动、二进制或多文件 ChangeSet；
- 自动批准、自动修复循环或模型直接写文件；
- Electron、原生文件夹选择、远程工作区、云同步或多用户协作；
- 模型列表自动探测、自由 Provider URL 或隐式代理；
- 在 M3 门槛达成前接入任意真实模型依赖、端点或网络调用（M3 已于 Phase 1R 达成）。

Phase 1 已实现的后端真实文件能力与 Phase 2 模型提议闭环，仍分别受 `docs/phase1-safety-contract.md` 与 `docs/phase2-model-provider-design.md` 严格约束（仅受控只读工具 + 单文件原子替换 + 内建验证 + 版本绑定审批）。
