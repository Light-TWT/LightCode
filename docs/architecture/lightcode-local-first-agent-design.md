# LightCode 本地优先智能体架构

## 目的

LightCode 是一个新的、独立实现的本地优先可视化编码智能体，面向有基础编程经验的开发者。它不是 MiniCode-Python 的重命名、分支呈现或源码延续。

该产品让智能体操作可见且可控：用户可以看到计划、工具活动、代码差异、审批请求和验证结果。

## 产品工作流

```text
用户任务
  -> 智能体读取已授权的代码库
  -> 智能体生成计划
  -> 智能体生成代码差异
  -> 用户批准或拒绝差异
  -> 智能体应用已批准的变更
  -> 智能体运行验证
  -> UI 显示有序时间线和结果
```

产品绝不能静默修改文件。每次写操作之前都需要可审查的差异和显式审批。

## 范围

### MVP

- 单用户、本地优先的应用。
- Vue 3 + TypeScript + Vite 工作区。
- FastAPI 本地运行时（在后续运行时阶段）。
- SQLite 持久化存储工作区、会话、任务、事件、审批、工具调用和变更集记录。
- 先使用 Mock 模型，后续使用 OpenAI 兼容的模型适配器。
- 只读工具、计划生成、差异生成、审批、受控写入和验证作为一个端到端工作流。
- 前端原型验证后的 REST 命令和 SSE 有序事件。

### 不在 MVP 范围内

- 账户、云同步、协作或云端代码执行。
- 多智能体编排或长期语义记忆。
- 自动 Git 写入、依赖安装、网络下载或不受限制的 shell 执行。
- Electron 打包。Electron 是后续交付阶段。

## 前端优先交付

阶段 0 构建一个仅含 Vue 的交互原型，使用类型化本地夹具来模拟工作区、会话、任务、事件、变更集、审批和测试输出。阶段 0 不创建 FastAPI、SQLite、Electron、真实提供商、本地文件系统桥接或 shell 执行。

所有夹具访问必须通过服务接口进行。未来的 REST 和 SSE 适配器将替换这些服务，而无需更改视图或 Pinia store 合约。

## 架构

```text
Vue 3 + TypeScript 工作区
  |
  | REST 命令 + SSE 事件流（后续）
  v
FastAPI 本地服务
  |
  +-- 智能体运行时
  |     +-- 模型适配器
  |     |     +-- MockModelAdapter
  |     |     +-- OpenAICompatibleAdapter
  |     +-- 任务状态机
  |
  +-- 工具注册中心
  |     +-- read_file, list_files, search_files
  |     +-- apply_approved_diff
  |     +-- run_verification, run_approved_command
  |
  +-- 工作区守卫
  |     +-- 根边界、路径遍历、符号链接、命令策略
  |
  +-- SQLite
        +-- workspaces, sessions, tasks, events
        +-- approvals, tool_calls, changesets
```

Vue 不访问本地文件系统、SQLite、shell 或提供商 API 密钥。FastAPI 是唯一可以进入授权工作区的进程。

## 未来的工作区边界

每个工作区拥有一个稳定 ID、规范化根路径和项目元数据。所有文件系统工具必须拒绝该根目录之外的路径、`..` 遍历、符号链接逃逸、密钥文件读取和 MVP 中的删除操作。

在浏览器开发期间，本地服务最终通过本地启动参数或配置来注册根路径。浏览器请求不得提交任意文件系统路径。Electron 后续提供原生文件夹选择。

## 未来的任务状态机

```text
created
  -> planning
  -> reading_workspace
  -> generating_diff
  -> awaiting_approval
  -> applying_change
  -> awaiting_command_approval
  -> running_verification
  -> completed | failed | cancelled
```

在 `awaiting_approval` 之前只允许只读工具。在 `applying_change` 之前需要特定版本且哈希匹配的已批准变更集。每次实际写入前必须重新校验工作区策略、目标文件身份与基线哈希；基线发生变化时不得覆盖。每个状态转换和工具结果必须在发送到 UI 之前持久化。

## 未来的命令策略

预设的验证命令可能包括：

```text
pytest
python -m pytest
npm test
npm run lint
```

其他命令需要一次性审批，包含精确命令、工作目录和风险说明。禁止删除、依赖安装、网络下载、Git commit/push/reset、进程控制和工作区外部执行。

## 数据模型

```text
Workspace(id, root_path, name, created_at)
Session(id, workspace_id, title, status, created_at, updated_at)
Task(id, session_id, prompt, state, plan_json, error_message)
Event(id, task_id, sequence, type, payload_json, created_at)
Approval(id, task_id, type, target_id, status, reviewed_at)
ToolCall(id, task_id, tool_name, input_json, output_json, status, duration_ms)
ChangeSet(id, task_id, diff_text, status, applied_at, rollback_snapshot)
```

提供商密钥仅属于本地配置。绝不将密钥存储在 SQLite、事件负载、前端状态、截图或日志中。

## 已批准的视图

- `WorkspaceHomeView`：最近工作区和包含所有已注册工作区的可搜索抽屉。
- `AgentWorkspaceView`：任务输入、计划、执行流、工具详情、可调整大小的代码上下文抽屉、差异审批和验证输出。
- `SessionHistoryView`：紧凑的项目任务时间线，加上已完成、失败和已取消任务的页内只读详情抽屉。
- `SettingsView`：两列配置中心，带分类导航和选中的设置面板。

## 视觉与交互规则

- 使用 `docs/design/` 中已批准的暖纸 LightCode 视觉语言。
- Agent Workspace 中保留约 220px 的左侧栏。
- 保持执行流居中，工具调用紧凑且可展开。
- 文件、差异和测试上下文放在可调整大小的右侧抽屉中。
- 完整差异仅属于审查抽屉。执行行只显示受影响的文件和增删行摘要。
- 待处理的变更集替换新任务输入为审查/拒绝操作。
- 测试抽屉在审批前仅显示待处理命令，在记录验证事件后显示结果。
- Workspace Home 仅列出最近工作；所有已注册工作区位于可搜索的右侧抽屉中。
- Session History 使用紧凑摘要。待处理任务通过"继续审查"返回 Agent Workspace；其他状态打开只读详情抽屉。

## 单体仓库结构

```text
lightcode-local/
  frontend/       Vue 应用，阶段 0 实现目标
  backend/        FastAPI + SQLite；工作区、模型、审批与写入的唯一边界
  electron/       Windows 桌面外壳 + FastAPI sidecar + NSIS 安装器
  docs/
    architecture/
    design/
  scripts/
```

包管理器已确定为 `npm`，前端通过 `frontend/package.json` 管理依赖和开发、测试、构建命令。

## 交付路线图

### 阶段 0：视觉原型

- 初始化 Vue 3 + TypeScript + Vite。
- 创建类型化夹具、存储和 Mock 服务接口。
- 实现已批准的视图，从 Agent Workspace 开始。
- 验证桌面端和窄屏布局。

### 阶段 0.5：运行时基础

- 创建 FastAPI API 合约和 SQLite schema。
- 实现 Mock 运行时、事件和 SSE。
- 用 REST/SSE 适配器替换夹具服务。

### 阶段 1：安全变更 MVP（后端 + 前端 T8 已实现）

- 绑定由服务端启动静态配置注册的授权工作区；浏览器只能提交 `workspaceId`，不能提交本地路径。
- **实现状态**：后端闭环已完成 —— 静态注册、`WorkspaceGuard`、受控只读工具、确定性 ChangeSet、版本绑定审批、单文件原子替换与内建验证均已落地并通过测试；前端 T8 也已闭环，8 个 Phase 1 端点（注册工作区浏览/文件预览/搜索、真实任务创建/审批/SSE）已接入 Vue 视图并通过前端测试（当前含 Phase 2 前端共 87 个，见 `AGENTS.md` 状态追踪）。浏览与读取采用不透明 browse token（HMAC 签名、绑定 workspace+operation+relative_path），浏览器不再提交自由路径；Phase 1R 又补齐 SSE 预算/心跳/续传、前端 token 导航与运行时 DTO 校验。
- 添加工作区守卫和只读工具，拒绝路径遍历、符号链接逃逸、秘密文件和工作区外访问。
- 实现持久化状态机、差异审查、版本绑定审批、单个既有 UTF-8 文本文件的受控原子写入和会话持久化。
- Phase 1 仅执行内建完整性验证，不启动 Shell、外部测试命令或命令白名单中的进程；真实命令策略与 `awaiting_command_approval` 留给后续允许受控进程执行的阶段。
- 具体安全不变量、拒绝规则、恢复承诺和验证矩阵见 `../phase1-safety-contract.md`；工作区注册见 `../workspace-registration.md`。

### 阶段 2：真实模型与开发者体验

> Phase 2 的完整设计与验证证据见 `../phase2-model-provider-design.md`；本小节只记录当前落地状态。

- Provider 仅由后端环境变量配置；浏览器不输入、持久化、回显或传输 API Key。
- 添加 OpenAI-compatible adapter；模型只能提出计划、受限只读工具请求和单文件候选编辑意图，服务端验证后独立生成 ChangeSet。
- 保持现有显式审批、单文件原子写入、内建验证与工作区隔离边界；模型不能直接写文件、运行命令、调用网络工具、管理包、写 Git 或决定审批。
- 先收口 Phase 1 的文件策略、审批绑定、并发租约、受控浏览、SSE、质量门禁和 API-mode E2E，再进入模型编排。
- 命令风险分类、会话搜索、代码库问答和基本回滚只在模型边界和 Phase 1R 门禁明确后按计划分批引入；不因 Provider 接入放宽 Shell 或网络下载限制。

#### 阶段 2 实现状态（M4–M6，WP5–WP8 已完成）

- **M4 Provider 基础设施（WP5）**：Provider 仅由后端环境变量配置，默认关闭、fail-closed；`ModelProviderConfig` 的 `api_key` 标记 `repr=False` 且唯一序列化为 `safe_summary()`（无 key、无 header、无完整 base URL）；health 上报 `status`（disabled/unconfigured/ready/degraded）与 `status_detail`；origin allowlist、HTTPS 强制、超时与预算上限齐备。
- **M5 模型只提议（WP6/WP7）**：LangGraph 状态机 + `create_model_task`；受限工具协议（read_file）、服务端 `build_model_change_set` 独立生成候选 ChangeSet；恶意工具请求 fail-closed；前端 8 类生命周期 UI（创建/计划/受控读取/候选 diff/审批/失败提示/SSE 时间线/连接态）已闭环。
- **M6 Phase 2 收尾（WP8）**：可观测性、API-mode E2E、敏感数据扫描与预算/并发/故障门禁全部完成，且**零新增第三方依赖**（stdlib `logging` + 进程内指标 + 既有 pytest/vitest）。
  - 单一可观测性出口 `app/services/observability.py`：JSON 格式器 + `ContextVar` 关联 ID + `redact()` 拒绝名单（secret/location 键与 `sk-`/`Bearer` 形状）+ 进程内 `Metrics` 单例（仅聚合数值，不存 prompt/response）。
  - 埋点覆盖：任务/关联 ID、状态转换、工具名称/耗时/类别、provider 名称/模型 ID/HTTP 类别/耗时/token 聚合、预算、SQLite busy、SSE 连接/续传。
  - `main.py` 关联 ID 中间件；`httpx`/`httpcore`/`openai`/`langchain*` 日志器被压到 WARNING，避免 provider base URL 经第三方 INFO 日志泄露。
  - 失败语义稳定：`MODEL_BUDGET_EXCEEDED`（输入/输出/请求数预算，输出预算在响应后本地强制）、`MODEL_CONCURRENCY_EXCEEDED`（进程内 `_ModelTaskGate` 并发 1，是 Phase 1 写租约的 Phase 2 类比，无 schema 变更）、`APPLY_CONFLICT`/`STALE_BASE` 沿用 Phase 1；`InstrumentedConnection` 拦截 `execute/executemany` 的 `locked`/`busy` 并计入 `sqlite.busy` 指标，保留 `PRAGMA busy_timeout` 与上下文协议。
  - 敏感数据扫描：新增 `test_model_e2e.py` 断言日志与事件载荷中不含 `test-key`/`api.example.test`/`Bearer`/`Authorization`/真实临时路径；`test_observability.py` 断言 `redact()` 与指标无密钥/路径。
  - **验证证据**：后端全量 `pytest` 303 通过 + 2 skipped（含 WP8、2026-08-04 审查修复与多供应商设置页新增用例）；前端 141 测试通过（20 文件）+ `vue-tsc -b` + `vite build`；Electron 12 测试通过。
- **2026-08-04 审查修复（H-01/M-01~06/L-01）**：未知编排异常固定投影（不泄露密钥/路径/响应片段）、模型上下文移除逻辑相对路径、Provider 输出预算本地强制、health 能力收紧为 `read_file`、前端 SSE 持续订阅（`tail=true` + `stream.end→closed`）、Provider ready-only 新建门禁、失败 UI 错误码固定文案映射、任务详情路由工作区归属校验、SSE 连接上限加锁原子化。细节见 `../phase2-model-provider-design.md` 与 `AGENTS.md` 状态追踪。

#### 阶段 A（核心 Agent 更新，2026-08-04+）

- **单一主工作区**：Mock Runtime/页面/服务已移除；产品入口收敛为 `/workspace/:workspaceId` 聊天式 Agent 主界面 + 设置层。浏览器只提交 `workspaceId`、会话标识、用户消息与审批决定；请求体经 `extra="forbid"` 拒绝 rootPath/filePath/patch/command/key。
- **运行期 Provider 设置**：设置层可编辑（Provider/Base URL/API Key/Model ID），「测试并保存」经最小化连接测试成功后写入 `ProviderCredentialStore`（Web 开发期为进程内存；桌面模式为 Windows Credential Manager，2026-08-13 已落地）。密钥绝不进 SQLite/前端持久化/日志/SSE。
- **聊天闭环**：`chat_sessions`/`chat_messages` 持久化；`ChatService` + LangGraph `ChatOrchestrator` 分流自由问答（answer）与编辑任务（候选 ChangeSet → 版本绑定审批 → 原子写入）。模型检索扩展为 `read_file` + `search_files`，均由 WorkspaceGuard/token/策略/预算约束。
- 详细设计见 `../phase2-model-provider-design.md` §6。

#### 阶段 B（多供应商设置页，2026-08-07）

- **前端**：设置页重构为暖纸多供应商配置中心——从 `WorkspaceView` 抽取共享侧边栏（`AppSidebar`），设置层仅保留「模型与供应商」「关于」；供应商列表可搜索、右侧为配置安全摘要（无 key/完整 baseUrl）、「添加供应商」走暖纸弹层（协议模板 + 测试并添加）。
- **后端**：`ProviderCredentialStore` 扩展为多配置 dict（`get()` 保持激活配置语义，`ChatService`/`ModelOrchestrator` 零改动）；`/api/v1/provider/profiles` 提供 GET 列表 / POST 创建（连接测试通过才保存，fail-closed）/ GET|DELETE by id；未保存任何配置时回落环境变量派生的 `default` 条目。`ProviderProfile`/`ProviderProfileCreate` 为 `extra="forbid"` 安全摘要 DTO，任何响应不含 API Key、完整 Base URL 或 Authorization header。
- 实现证据见 `../phase2-model-provider-design.md` §6.1.1。

### 阶段 3：桌面端交付

> **状态：已完成（2026-08-13）。** 设计以 `docs/superpowers/specs/2026-08-13-phase-3-windows-desktop-design.md` 为准。

- 添加 Electron shell、FastAPI PyInstaller sidecar 生命周期、原生文件夹选择以及打包的本地数据存储。
- **仅 Windows 首发**：`electron-builder` + NSIS 手动安装包；FastAPI 构建为随包 sidecar，用户无需安装 Python/Node/pip。
- **安全加壳不变革内核**：Electron 只负责窗口、原生目录选择与 sidecar 生命周期；渲染进程保持沙箱，仍无文件/Shell 能力；FastAPI 仍是工作区访问、模型出网、审批与写入的唯一边界。
- **动态注册工作区**：桌面注册不要求静态 `targetFile`；新目录经 canonical/reparse 校验后进入系统，模型后续经 `search_files`/`read_file` 决定单文件候选编辑，仍走显式审批与原子写入。
- **用户数据在安装目录之外**：SQLite、技能包、工作区注册与日志放 Windows 用户数据目录；升级只替换程序资源，不删除用户数据。
- **凭据持久化**：Provider API Key 在桌面模式经 Windows Credential Manager 适配器保存（`ProviderCredentialStore` 协议不变）。
- **首装全新数据**：不导入开发期仓库数据库或配置。
- **发布门槛**：内部测试阶段暂不签名；公开发布前必须接入代码签名与自动更新，另行制定计划。

### 阶段 4：可选扩展

- 账户、云同步、备份、协作、远程执行、任务工作流、长期记忆和多智能体协作。

## 阶段 0 验收标准

- 所有四个已批准的视图已作为 Vue 页面重新实现。
- 所有视图数据来自类型化本地夹具和服务接口。
- Agent Workspace 支持 Mock 任务状态、可展开的工具行、可调整大小的上下文抽屉、差异审批模拟和验证输出模拟。
- Session History 在页内打开任务详情，并将待处理任务返回 Agent Workspace 审查。
- 不声称或实现任何运行时、文件系统、数据库、命令、提供商或 Electron 行为。
