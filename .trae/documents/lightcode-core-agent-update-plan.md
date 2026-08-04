# LightCode 核心 Agent 更新实施计划

## 摘要

本次更新把目前并存的 Mock 原型工作区与“真实工作区”收敛为一个单一主工作区，交付可用于本地开发测试的 Provider 设置、持久化聊天会话、模型受控检索、自由问答和任务式代码修改入口。

目标体验是：用户选择一个已注册的本地项目，在主页面中通过聊天框提问或提出开发任务；模型根据意图直接回答，或在受控检索后生成候选变更集；所有写入继续走可见 Diff 和显式审批。Provider 采用 OpenAI-compatible 配置，DeepSeek 是首个明确兼容对象。

本计划只实现阶段 A：单一主界面和安全的聊天闭环。完整文件操作（新增、删除、重命名、移动、多文件事务）放入阶段 B，必须先建立新的安全契约、审批绑定与崩溃恢复协议，不能和 UI 收敛混合实现。

## 当前状态分析

- [frontend/src/router/index.ts](file:///c:/Users/Tianw/OneDrive/桌面/lightcode-local/frontend/src/router/index.ts#L1-L21) 同时维护 Mock 路由 `/`、`/workspace/:id`、`/workspace/:id/history` 与真实工作区路由 `/real*`，造成入口和视图重复。
- [frontend/src/views/AgentWorkspaceView.vue](file:///c:/Users/Tianw/OneDrive/桌面/lightcode-local/frontend/src/views/AgentWorkspaceView.vue#L70-L189) 是原始 Mock Agent 页面，依赖带虚构 rootPath、会话、工具和 Diff 的 fixture。
- [frontend/src/views/RealWorkspaceView.vue](file:///c:/Users/Tianw/OneDrive/桌面/lightcode-local/frontend/src/views/RealWorkspaceView.vue#L92-L215) 才连接真实工作区、安全浏览 token 和模型任务入口，但其交互是文件浏览加表单，不是主聊天工作区。
- [backend/app/services/model_orchestrator.py](file:///c:/Users/Tianw/OneDrive/桌面/lightcode-local/backend/app/services/model_orchestrator.py#L149-L192) 已使用 LangGraph，但只支持单个预配置目标文件的 `read_file -> candidate_edit_intent`，不支持自由问答、会话或 `search_files`。
- [frontend/src/views/SettingsView.vue](file:///c:/Users/Tianw/OneDrive/桌面/lightcode-local/frontend/src/views/SettingsView.vue#L108-L222) 只读展示由环境变量派生的 Provider health；不能在产品内测试 DeepSeek 或保存运行期配置。
- [backend/app/db/database.py](file:///c:/Users/Tianw/OneDrive/桌面/lightcode-local/backend/app/db/database.py#L8-L105) 仍包含 Mock workspaces、sessions、tasks 和 task history 的 schema/种子数据；当前任务表也不足以表示用户聊天消息与会话上下文。

## 已确认决策

1. 本次范围为“核心闭环”，不接入 Electron、不执行 shell 或外部验证命令。
2. Mock 专属页面、前端 fixture/mock service、Mock API 及 SQLite Mock 种子数据在实施阶段删除；用户已明确授权文件删除与数据库迁移。
3. 浏览器保持为 UI；FastAPI 继续是工作区访问、模型出网、审批与写入的唯一边界。
4. Provider 设置在 Settings 页面可编辑。API Key 和 Base URL 不进入 SQLite、前端持久化、日志、SSE 或仓库。
5. 新增 `ProviderCredentialStore` 抽象：Web 开发期实现后端进程内存存储，重启后需要重新输入；Electron 阶段替换为 OS Keychain 适配器，不改变前端 API 或业务服务。
6. Provider 表单由用户点击“测试并保存”触发最小网络验证；通过才更新内存配置。健康接口只返回安全摘要，绝不返回 key 或完整 Base URL。
7. 聊天会话与消息保存到 SQLite；消息不保存 API Key、Authorization、完整 Provider URL、原始异常诊断或不受控隐私数据。
8. 聊天支持自由问答和开发任务。模型先以严格结构化协议输出 `answer` 或 `edit` 意图；问答直接回复，编辑进入计划、受控检索、候选 ChangeSet 和显式审批。
9. 模型检索能力扩展为 `search_files` 和 `read_file`，均由服务端 WorkspaceGuard、browse token、文件大小/扩展名/敏感路径策略和预算控制；模型不接收根路径或自由文件路径。
10. 继续使用已有 LangChain/LangGraph：LangChain 作为 OpenAI-compatible 客户端边界，LangGraph 作为聊天/工具循环与编辑任务编排；不自行实现 LLM 调用或图状态机底层。
11. 阶段 A 仍仅允许修改单个既有 UTF-8 文本文件，且由服务端独立构建 ChangeSet；阶段 B 才支持新增、删除、重命名、移动和多文件事务。

## 阶段 A：单一工作区与聊天闭环

### 1. 先重写安全契约与架构文档，再改代码

更新以下既有文档以替换“Phase 0.5 Mock 保留”和“Provider 仅环境变量”的过时约束：

- `AGENTS.md`
- `docs/architecture/lightcode-local-first-agent-design.md`
- `docs/phase1-safety-contract.md`
- `docs/phase2-model-provider-design.md`
- `docs/workspace-registration.md`

明确新的不变量：

- 主 UI 只使用已注册工作区，不存在 Mock runtime 或浏览器提交路径。
- Provider 凭据仅经本机 FastAPI 设置端点接收，送入可替换的凭据存储；内存实现不落盘。
- 健康、事件、日志和 API 响应必须继续执行 secret/location redact，禁止完整 Base URL、key、header、路径和原始上游响应。
- 测试连接必须限制为配置 allowlist 内的 HTTPS origin（开发环境是否允许 HTTP 沿用显式开发开关），`trust_env=False`、`follow_redirects=False`、显式 timeout、无重试。
- 聊天会话持久化只记录用户可见消息、安全的任务引用/状态和时间；模型上下文只来自 Guard 放行的受控读取结果。
- `search_files` 只能由模型通过严格 DTO 请求；服务端限制搜索 query 长度、结果数量、单文件读取大小、总输入字节、工具轮次和单任务请求数。
- 编辑意图仍不能携带自由 path、patch、命令、审批决定或写入内容；服务端用已授权 token 和基线哈希构建 ChangeSet。

文档还应明确阶段 B 前保持禁止：多文件写入、新建、删除、重命名、移动、二进制编辑、Shell、包管理、下载、Git 写入、自动审批、Electron 文件夹选择。

### 2. 数据库迁移与 Mock 数据清理

修改 `backend/app/db/database.py` 的 `SCHEMA_SQL`、`run_migrations()` 和 `seed_database()`：

- 删除 Mock workspace/session/task/history 的固定种子逻辑，删除仅服务于 Mock 的字段和默认值，或在兼容迁移后不再由新业务读取。
- 新增持久化聊天模型，最少包括：
  - `chat_sessions`：`id`、`workspace_id`、`title`、`status`、`created_at`、`updated_at`。
  - `chat_messages`：`id`、`session_id`、`role`（`user`、`assistant`、`system`）、`content`、`kind`（问答/计划/编辑摘要/错误）、`task_id`（可空）、`created_at`、稳定序号。
- 为任务保留或新增对 `chat_session_id` 的关联，使任务生命周期、SSE 事件、ChangeSet、审批记录可从聊天流追溯。
- 使用现有内联、幂等迁移模式而非引入迁移框架；迁移仅创建新表/列和必要索引，历史 Mock 数据清理要显式、可测试、幂等。
- 不把 credential、完整 URL、模型 prompt/tool raw content、根路径写进新表。

为 schema 升级、新库初始化、旧 Mock 库迁移、重启后会话/消息保留、凭据不落库写后端测试。

### 3. Provider 运行期配置与可替换凭据存储

新增后端的 Provider 设置边界，并调整现有配置/Provider 服务：

- 在 `backend/app/services/` 新增 `ProviderCredentialStore` 协议与 `InMemoryProviderCredentialStore` 实现。接口至少包括读取安全配置状态、暂存/替换凭据、清除凭据；绝不提供返回原始 key 的 API。
- 在 `backend/app/config/model_provider.py` 将“环境配置快照”与“运行期配置”拆开：环境变量可以作为启动初始配置/部署回退，运行期配置通过 credential store 覆盖；所有输出仍仅使用 `safe_summary()`。
- 在 `backend/app/services/openai_compatible_provider.py` 和 `llm_client.py` 复用现有 LangChain 客户端工厂、超时、预算和错误映射；新增最小化 `test_connection()`，不存入响应正文，成功只回安全状态。
- 在 `backend/app/schemas/model_contracts.py` 新增严格 `extra="forbid"` 的请求/响应 DTO：可输入 provider 类型、baseUrl、apiKey、modelId 和可控模型参数；响应只能输出安全摘要、验证状态及稳定错误码。请求 DTO 仅用于本机设置端点，绝不进入日志/事件/SQLite。
- 在 `backend/app/api/routes.py` 增加 Provider 设置读取、安全测试并保存、清除的 API；所有路由在同步线程池入口重绑 correlation ID，并复用 `Phase1Error` 的稳定错误投影。
- 在 `backend/app/main.py` 注入 credential store 到 `app.state`，使现有 health、聊天编排和测试连接使用统一的有效配置。
- `GET /provider/health` 改为返回环境/内存组合后的安全摘要；进程重启后内存凭据丢失并回落为环境配置或 unconfigured，这应在 detail 中用固定文案说明。

前端更新：

- 改造 `frontend/src/services/provider.service.ts`，移除 Mock service，新增 provider settings 的 get/save-test/clear typed HTTP 接口和运行时 schema 校验。
- 改造 `frontend/src/views/SettingsView.vue`，去掉 Mock/Runtime mode 卡片，改为 Provider 配置表单：Provider、Base URL、API Key（只允许 `type=password`）、模型 ID、显式“测试并保存”、安全状态、清除当前运行期配置。组件仅保留 UI 临时输入；提交后清空 key input，不以 Pinia/localStorage/sessionStorage 保存。
- UI 明确标注 Web 开发期凭据仅在后端运行内存中保存，重启后需重新配置；Electron 后将迁移为系统密钥库实现。

### 4. 会话、聊天 API 与 LangGraph 编排

新增聊天领域服务（建议 `backend/app/services/chat_service.py`）和聊天 DTO（建议扩展 `model_contracts.py`，或在同目录新增保持 camelCase/extra forbid 的模块）：

- API：列出工作区会话、创建会话、读取会话与消息、提交聊天消息、订阅会话/关联任务事件。
- 浏览器请求只提交 `workspaceId`、`sessionId`（新建时无）、用户消息内容和可选已存在的安全 token；不得提交 rootPath、filePath、patch、文件正文、命令、key 或 base URL。
- 输入限制：空白拒绝、字符长度上限、单会话并发提交保护、消息频率/请求预算、受控错误码。
- 聊天提交先写用户消息，再由 LangGraph 运行 `classify_intent -> answer | search/read loop -> answer | build single-file edit candidate`。
- `answer`：模型只返回用户可见回答；服务端清洗/限制长度后持久化 assistant message，不生成 ChangeSet。
- `edit`：模型生成安全计划，按工具协议请求 `search_files` / `read_file`，服务端逐次验证，再产生当前单文件 `candidate_edit_intent`，复用 `build_model_change_set`、状态事件和版本绑定审批。
- 现有 `ModelOrchestrator` 拆分公共的 Provider 调用、工具 adjudication、预算与错误投影，并由新的聊天图和保留兼容的任务入口共同使用；不复制 LLM 请求逻辑。
- 把 `_ORCHESTRATOR_TOOLS` 和 `MODEL_ALLOWED_TOOLS` 同步扩展为 `read_file`、`search_files`。新增严格 `SearchFilesToolRequest`/联合协议：query 以文本为限，不含路径；服务端 search 结果仅传 token、受控 snippet、行信息/哈希，不传绝对或逻辑路径。
- 更新 `WorkspaceGuard.search_files` 和 browse token 签发/验证，确保搜索结果按当前 policy、扩展名、大小、敏感文件、链接策略过滤；每个 read 仍需服务端签发的 `fileToken`。
- 复用现有 `task_events` SSE 基础设施，新增 chat/session 事件类型或将每个编辑动作绑定 taskId；前端能够断线续传、按 sequence 去重，并把模型错误码映射为固定中文文案。

测试要覆盖：

- DeepSeek/OpenAI-compatible 的设置测试成功、超时、401/429/5xx、无效 URL、非 allowlist origin、异常响应；日志/API/SSE/SQLite 不含 key/完整 URL。
- 会话和消息持久化；跨重启会话能读取；内存配置跨重启丢失。
- 问答意图不生成 ChangeSet；编辑意图只在通过服务端工具校验和基线检查后生成 ChangeSet。
- 恶意模型输出（自由路径、rootPath、patch、命令、未授权工具、非法 JSON、超轮次、超预算）一律 fail-closed。
- `search_files` 不返回/读取 `.env`、`.git`、链接、工作区外文件或超限文件；模型上下文不含根路径。

### 5. 主页面与路由收敛

前端以一个新/重构的主工作区视图替代 `WorkspaceHomeView`、`AgentWorkspaceView`、`SessionHistoryView`、`RealWorkspaceListView` 和 `RealWorkspaceView` 的产品入口。

推荐路由：

- `/`：默认跳转到第一个已注册工作区，或者在尚无注册工作区时展示空状态和配置指引。
- `/workspace/:workspaceId`：唯一工作区主界面。
- `/workspace/:workspaceId/session/:sessionId`：指定聊天会话的主界面状态。
- `/workspace/:workspaceId/task/:taskId`：保留审查深链接；可直接打开右侧审查抽屉，且必须校验 task/workspace 归属。
- `/settings`：Provider 配置和权限/安全摘要。

主界面按照已批准的暖纸视觉语言重写为 Vue 组件，不复制 `docs/design/*.html`：

- 左侧栏：已注册工作区切换、当前工作区受控文件树、该工作区会话列表、新建会话、设置入口。
- 中间主栏：聊天消息流、用户消息输入框、发送/取消状态；任务编辑时呈现紧凑的计划与工具活动，而不是伪造的终端输出。
- 右侧抽屉：当前文件预览、模型受控搜索结果、完整 Diff、审批/拒绝操作、内建验证结果。待审批 ChangeSet 时，底部输入区替换为审查/拒绝操作，保持当前产品规则。
- 模型回复清晰区分“回答”“正在检索”“准备修改”“等待审批”“失败”；错误只展示固定中文文案和可行动建议。
- 显示隐私披露：只有 Guard 放行的内容可发送给配置的 Provider；凭据不离开本机后端。

修改 `frontend/src/stores/real.store.ts` 或将其重命名为单一 workspace/chat store：

- 删除 Mock 分支和 `isApiMode` 选择。
- 保留 token 化浏览、预览、搜索、ChangeSet 审批、SSE sequence 去重与重同步的安全逻辑。
- 新增 workspace 会话列表、当前会话、消息、发送状态、取消/重连状态、聊天 task 与审查抽屉状态。
- 当 assistant 产生 edit task，自动关联消息到 taskId，打开紧凑进度并可进入完整审查抽屉。

删除用户已授权清理的 Mock 专属文件、服务、路由、fixtures、视图测试和后端 legacy runtime/种子逻辑；只删除经静态引用搜索确认未被新实现使用的文件。同步更新相关前端测试，确保不存在 rootPath、Mock runtime label 或 mock service 的残留引用。

### 6. 开发体验、迁移与兼容性

- 保留 `backend/workspaces.json` / `LIGHTCODE_WORKSPACES_CONFIG` 静态工作区注册机制；Web 期不引入浏览器文件夹选择。
- 现有 `RealTaskView.vue` 的 Diff、审批、生命周期和 SSE UI 可拆为审查抽屉组件并复用，避免复制审批逻辑。
- `ProviderCredentialStore` 是 Electron 迁移边界：阶段 C（桌面交付）实现 `ElectronKeychainCredentialStore`，用 OS credential service 替换内存实现；Provider 设置 API、SQLite chat history、聊天 UI 和编排接口保持稳定。
- 现有环境变量仍可作为开发/部署回退，优先级明确为：已测试保存的运行期内存配置 > 有效环境变量配置 > unconfigured/disabled。
- 若 Provider 未 ready，仍可浏览工作区和查看历史；聊天输入禁用并引导进入设置，不隐藏会话或审批。

## 阶段 B：完整文件操作安全协议（独立计划，不在阶段 A 实施）

阶段 B 的目标是让编辑任务支持多个文件的修改、新建、删除、重命名、移动。这不是“将当前 EditOp 加字段”，因为现有 Phase 1 安全模型只证明了单个既有 UTF-8 文件的原子替换。

开始前必须完成新的安全设计，并经用户审阅后再动代码：

1. ChangeSet 数据模型升级为多条操作明细，每条绑定 operation type、opaque file token、基线/目标哈希、内容元数据与策略版本。
2. 定义新建文件允许目录、名称/扩展名、大小、冲突策略；删除和移动的二次确认、目录边界、历史保留与恢复语义。
3. 设计跨文件提交：每文件临时写入、全量预校验、提交日志/恢复日志、崩溃时的 completed/rolled-back/unknown 状态；禁止出现半提交后静默成功。
4. 扩展审批绑定为 ChangeSet 全量 manifest hash，拒绝部分文件被替换、增加或删除后的旧审批重放。
5. 重新评估 symlink/reparse point、TOCTOU、并发写租约、敏感文件策略、文件树缓存、SSE 事件和审计数据最小化。
6. 编写故障注入和 API-mode E2E：多文件冲突、外部改动、权限失败、磁盘不足、进程中断、幂等重放、恶意 rename/path、敏感路径与链接绕过。

成熟库使用原则：继续用 LangChain/LangGraph 处理模型调用与编排；文件系统安全、审批绑定、原子写入和崩溃恢复是本地安全边界，必须由项目的 `WorkspaceGuard`、ChangeSet 服务和可测试协议掌控，不能交给模型框架或通用 Agent 库。

## 验证步骤与验收标准

### 后端

1. 新增/调整 Provider credential、设置 API、聊天 service/orchestrator、Guard 搜索、会话持久化、迁移和安全回归测试。
2. 运行后端全量 `pytest`，修复所有失败；不得新增 skip、假成功或关闭安全检查。
3. 使用临时数据库/API-mode E2E 验证：注册工作区 -> 设置并测试 Provider -> 新建会话 -> 自由问答 -> 受控检索 -> 生成单文件候选 Diff -> 审批 -> 原子写入 -> 事件续传 -> 重启后读取会话。
4. 注入 Provider 和模型失败，验证稳定错误码、无敏感信息泄露、内存凭据重启清空、环境回退语义。

### 前端

1. 新增/修改服务契约、store、主工作区、设置页、路由和审查抽屉单元测试。
2. 断言所有请求体不含 rootPath、filePath、patch、command、完整文件内容、key 或 baseUrl（Provider 设置专用请求除外；该请求不得被保存/记录）。
3. 验证单一主入口、会话新建/切换/刷新恢复、Provider 未就绪门禁、问答渲染、工具进度、Diff 审批、SSE 断线续传与错误映射。
4. 在 `frontend/` 运行 `npm test`、`npm run typecheck`、`npm run build -- --emptyOutDir false`。

### 删除与文档一致性

1. 全仓搜索确认无可达 Mock 路由、Mock service、fixture、`rootPath` Mock DTO、Mock mode 文案或 legacy runtime 入口。
2. 更新现有架构与安全文档中的阶段状态、配置来源、聊天能力和阶段 B 边界；不新建无请求的 README。
3. 不执行 git commit、push、Electron 打包、部署或任何外部发布操作。
