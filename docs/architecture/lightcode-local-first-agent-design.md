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
  backend/        FastAPI + SQLite；Phase 0.5 Mock Runtime 与 Phase 1 真实安全变更闭环
  electron/       为桌面 shell 保留
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
- **实现状态**：后端闭环已完成 —— 静态注册、`WorkspaceGuard`、受控只读工具、确定性 ChangeSet、版本绑定审批、单文件原子替换与内建验证均已落地并通过测试；前端 T8 也已闭环，8 个 Phase 1 端点（注册工作区浏览/文件预览/搜索、真实任务创建/审批/SSE）已接入 Vue 视图并通过 60 个前端测试。
- 添加工作区守卫和只读工具，拒绝路径遍历、符号链接逃逸、秘密文件和工作区外访问。
- 实现持久化状态机、差异审查、版本绑定审批、单个既有 UTF-8 文本文件的受控原子写入和会话持久化。
- Phase 1 仅执行内建完整性验证，不启动 Shell、外部测试命令或命令白名单中的进程；真实命令策略与 `awaiting_command_approval` 留给后续允许受控进程执行的阶段。
- 具体安全不变量、拒绝规则、恢复承诺和验证矩阵见 `../phase1-safety-contract.md`；工作区注册见 `../workspace-registration.md`。

### 阶段 2：真实模型与开发者体验

- 添加 OpenAI 兼容适配器和本地提供商配置。
- 添加命令风险分类、会话搜索、代码库问答和基本回滚。

### 阶段 3：桌面端交付

- 添加 Electron shell、FastAPI sidecar 生命周期、原生文件夹选择以及打包的本地数据存储。

### 阶段 4：可选扩展

- 账户、云同步、备份、协作、远程执行、任务工作流、长期记忆和多智能体协作。

## 阶段 0 验收标准

- 所有四个已批准的视图已作为 Vue 页面重新实现。
- 所有视图数据来自类型化本地夹具和服务接口。
- Agent Workspace 支持 Mock 任务状态、可展开的工具行、可调整大小的上下文抽屉、差异审批模拟和验证输出模拟。
- Session History 在页内打开任务详情，并将待处理任务返回 Agent Workspace 审查。
- 不声称或实现任何运行时、文件系统、数据库、命令、提供商或 Electron 行为。
