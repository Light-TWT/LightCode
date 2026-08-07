# Phase 2 模型 Provider 与可观测性设计

本文件是 Phase 2（WP5–WP8）模型 Provider 子系统与可观测性/发布门禁的**权威设计参考**。
工作包划分、里程碑与验收标准见 `2026-07-30-phase-2-model-and-dx-plan.md`；本文件只记录
已落地的架构决策、接口契约与验证证据，避免与计划文档重复。

> 约束：Phase 2 首版**不**实现 Shell/外部命令、包管理、网络下载、Git 写操作、删除/新建/重命名、
> 多文件事务、二进制/非 UTF-8 修改、Electron、本地文件夹选择、自动批准或模型直接写文件。
> WP8 经用户确认采用**零新增第三方依赖**策略（stdlib `logging` + 进程内指标 + 既有 pytest/vitest）。
>
> **核心 Agent 更新（阶段 A，2026-08-04+）**：Provider 配置来源扩展为「后端环境变量 +
> 运行期设置表单（进程内存凭据）」，聊天会话持久化到 SQLite，模型检索工具扩展为
> `read_file` + `search_files`；完整改动见 §6。

---

## 6. 核心 Agent 更新（阶段 A）：运行期设置、凭据存储与聊天闭环

### 6.1 Provider 运行期配置与可替换凭据存储

- **配置来源**：环境变量快照（`ModelProviderConfig`，启动时加载）作为部署回退；
  设置页表单（`POST /api/v1/provider/settings`）在「测试并保存」成功后把凭据写入
  `ProviderCredentialStore`（`app/services/credential_store.py`）。生效优先级：
  运行期凭据 > 环境变量 > unconfigured/disabled。
- **凭据存储协议**：`ProviderCredentialStore`（get/set/clear）——Web 开发期使用
  `InMemoryProviderCredentialStore`（进程内存，重启后丢失，绝不落盘）；Electron 阶段
  （阶段 C）替换为 OS Keychain 实现，设置 API/聊天/编排接口不变。这是桌面交付的迁移边界。
- **允许名单**：`LIGHTCODE_MODEL_ALLOWED_ORIGINS` 非空时严格校验运行期 Base URL 的 origin；
  为空时接受用户在设置表单中显式提交的 origin（用户主动输入，非静默环境派生）。
- **连接测试**：`POST /api/v1/provider/settings/test`（不保存）与 `POST /api/v1/provider/settings`
  （测试并保存）都经 `OpenAICompatibleProvider.test_connection()` 做最小化 round-trip；
  失败只返回稳定错误码（`PROVIDER_SETTINGS_INVALID` / `PROVIDER_CONNECTION_FAILED`）。
- **安全视图**：`GET /api/v1/provider/settings` 与 `GET /api/v1/provider/health` 只返回
  `{configured, status, provider, modelId, detail, originAllowlisted, transport}`，绝不返回
  API Key 或完整 Base URL。

#### 6.1.1 多供应商配置（阶段 B，2026-08-07）

- `ProviderCredentialStore` 扩展为**多配置**：每个运行期配置拥有稳定 `id`，协议
  增加 `get_all()`（按 id 返回全部）/ `get_named(id)` / `remove(id)`；`get()` 保持
  返回"当前激活"配置，使 `ChatService` / `ModelOrchestrator` 既有调用路径零改动。
  仍是进程内存 + 线程安全（`InMemoryProviderCredentialStore`），Electron 阶段（阶段 C）
  整体替换为系统密钥库实现。
- 新增安全摘要 DTO（`extra="forbid"`、camelCase、无 key/完整 baseUrl）：
  `ProviderProfile`（id/name/provider/modelId/enabled/status/baseUrlHost）与
  `ProviderProfileCreate`（name/provider/baseUrl/apiKey/modelId/enabled，凭据仅存在于
  请求体与内存存储）。
- 新增 CRUD 端点 `/api/v1/provider/profiles`：GET 列表 / POST 创建 / GET|DELETE by id。
  POST 先经 `test_connection()` 最小化 round-trip，**测试通过才保存**（fail-closed），
  失败返回 `PROVIDER_CONNECTION_FAILED`；删除激活配置自动回落到其余配置或环境变量。
  未保存任何配置时列表回落为环境变量派生的单个 `default` 条目（disabled 时为 `[]`）。
- 安全不变量不变：任何响应/日志/SSE 绝不出现 API Key、完整 Base URL 或
  Authorization header（响应仅含 `baseUrlHost` 域名）；测试连接沿用 HTTPS origin
  allowlist、显式超时、`trust_env=False`、`follow_redirects=False`、零重试。

### 6.2 聊天会话与消息（SQLite 持久化）

- 新增 `chat_sessions` / `chat_messages` 表；`tasks` 增加 `chat_session_id` 列把编辑任务
  关联回聊天会话。消息只保存 role/content/kind/taskId/时间，不保存 API Key、完整 URL、
  原始异常诊断或不受控隐私数据。
- API：`/workspaces/{id}/chat-sessions`（列表/创建）、`/chat-sessions/{id}`（详情）、
  `/chat-sessions/{id}/messages`（提交）、`/chat-sessions/{id}/events`（SSE `chat.event`）。
- 提交消息先持久化用户消息，再由 `ChatService` + `ChatOrchestrator`（LangGraph）决定
  自由问答（`answer`，不生成 ChangeSet）或编辑任务（`candidate_edit_intent` →
  `kind='model'` 任务 → 版本绑定审批 → 原子写入）。单会话并发提交受进程内闸门保护
  （`CHAT_BUSY`）。

### 6.3 模型检索工具扩展

- `MODEL_ALLOWED_TOOLS` / `_ORCHESTRATOR_TOOLS` 扩展为 `read_file` + `search_files`。
- `search_files` 由模型通过严格 `SearchFilesToolRequest`（仅 `query` 文本，≤200 字符）
  请求；服务端经 `WorkspaceGuard.search_files` 执行，命中返回 `{index, name, fileToken,
  line, snippet}`（≤10 条、snippet 有界），模型上下文不含根路径或自由路径。
- `read_file` 只接受服务端签发的 fileToken；聊天流程中模型只能读取检索命中的文件。
- 编辑目标文件由 `candidate_edit_intent.fileToken` 决定，服务端校验 token 后解析路径并
  独立构建 ChangeSet（`build_intent_changeset`），模型永远不能命名或伪造路径。

### 6.4 聊天与模型任务的失败语义

- 聊天编排失败只持久化固定文案（`_FAILURE_TEXT` 白名单），前端再按固定文案渲染，
  绝不渲染服务端自由 message（延续 M-03）。
- 自由问答失败不创建任务；编辑失败落 `kind='model'` 任务 `failed` + 稳定错误码事件。


---

## 1. Provider 配置（WP5，M4）

### 1.1 配置来源与 fail-closed

- 配置**仅**来自后端环境变量（WP5 原设计），浏览器不持久化、回显或传输 API Key / base URL；
  阶段 A 起设置页可提交运行期凭据（仅提交瞬间存在），阶段 B 起支持多供应商配置，见 §6.1 / §6.1.1。
- 默认关闭：`LIGHTCODE_MODEL_ENABLED` 必须是 `true/1/yes/on` 之一，任何其他值（含拼写错误）保持 disabled。
- 派生状态机（`ModelProviderConfig.status()`）只产出四种状态，且**不发起任何网络调用**：
  - `disabled`：未启用。
  - `unconfigured`：启用但缺 key / base URL / model id。
  - `degraded`：provider 类型不支持、origin 不在 allowlist、非 http(s)、或生产环境明文 HTTP 未开开发开关。
  - `ready`：可出网。
- 任一非 `ready` 状态都**不得打开 socket**。

### 1.2 密钥不变量

- `api_key` 在 `ModelProviderConfig` 上标记 `field(repr=False)`，生成 `repr()` 与任何 f-string/
  日志/ traceback 渲染都无法泄露。
- 唯一合法序列化路径是 `safe_summary()`，只输出：provider、modelId、status、apiKeyConfigured（布尔）、
  transport（仅 `http`/`https`/`none` 方案，非完整 URL）、originAllowlisted、followRedirects、trustEnvProxies。
- HTTP 客户端构造（`llm_client.build_llm`）使用 `trust_env=False`、`follow_redirects=False`、
  `max_retries=0`，避免代理/重定向把流量带离 allowlist 的 origin。

### 1.3 预算（默认值与 §WP8 预算表一致）

| 项 | 默认值 | 环境变量 |
| --- | ---: | --- |
| connect_timeout_seconds | 5.0 | `LIGHTCODE_MODEL_CONNECT_TIMEOUT_SECONDS` |
| read_timeout_seconds | 45.0 | `LIGHTCODE_MODEL_READ_TIMEOUT_SECONDS` |
| total_timeout_seconds | 60.0 | `LIGHTCODE_MODEL_TOTAL_TIMEOUT_SECONDS` |
| max_tool_rounds | 8 | `LIGHTCODE_MODEL_MAX_TOOL_ROUNDS` |
| max_input_bytes | 262_144 (256 KB) | `LIGHTCODE_MODEL_MAX_INPUT_BYTES` |
| max_output_tokens | 2_048 | `LIGHTCODE_MODEL_MAX_OUTPUT_TOKENS` |
| max_requests_per_task | 10 | `LIGHTCODE_MODEL_MAX_REQUESTS_PER_TASK` |
| max_concurrent_tasks | 1 | `LIGHTCODE_MODEL_MAX_CONCURRENT_TASKS` |

所有预算解析 fail-closed：畸形或非正值回退到文档默认值，绝不读作"无限制"。

---

## 2. 编排与工具边界（WP6/WP7，M5）

- `ModelOrchestrator` 用 LangGraph 状态机实现 `create_model_task`；模型只能"提议"。
- 受限工具协议：模型仅可请求 `read_file`（见 `MODEL_ALLOWED_TOOLS`，与编排器 `_ORCHESTRATOR_TOOLS` 一致）；`search_files` 保留给后续版本，模型请求会 fail-closed 拒绝。
- **模型上下文最小化（2026-08-04）**：发往 Provider 的 system prompt 与 read 工具结果不含工作区根路径、逻辑相对路径或文件名，只含服务端签发的 fileToken、baseSha256 与 Guard 受控读取的文本；未知编排异常只投影为固定文案（`_INTERNAL_ORCHESTRATION_FAILURE`），异常原文不进入 SQLite/API/SSE/前端。
- 候选编辑由服务端 `build_model_change_set` 独立生成 Difference，绝不依赖模型输出的补丁文本。
- 恶意工具请求（含 `rootPath`/`filePath`/自由路径/超预算）fail-closed 拒绝。
- **输出预算本地强制（2026-08-04）**：`OpenAICompatibleProvider.chat()` 在响应返回后校验已报告的 `completion_tokens`；usage 缺失时按 `max_output_tokens * 4` UTF-8 字节保守上限拒绝，超出即 `MODEL_BUDGET_EXCEEDED`，不信任上游对 `max_tokens` 的遵守。
- 保持 Phase 1 的显式审批、单文件原子替换、内建验证与工作区隔离边界不变。

---

## 3. 可观测性（WP8，M6）

### 3.1 单一出口 `app/services/observability.py`

为避免多 sink 泄露敏感数据，所有日志与指标只经此模块：

- **JSON 格式器**：每条记录一个 JSON 对象；`exc_info` 文本被脱敏，不出现原始栈帧中的路径/密钥。
- **关联 ID**：`correlation_id_var: ContextVar[str]`（默认 `"-"`）+ `CorrelationFilter`，每个记录附关联 ID。
  FastAPI 同步路由运行在线程池，中间件在 `request.state.correlation_id` 上重绑后再进入同步逻辑，
  保证关联 ID 在线程池内仍可溯。
- **`redact(obj)`**：递归清洗器。
  - `_SECRET_KEYS`：`api_key` / `authorization` / `cookie` / `secret` / `token` / `password` 等。
  - `_LOCATION_KEYS`：`base_url` / `root_path` / `filepath` / `rootPath` 等。
  - `_secret_string()`：遮盖 `sk-[A-Za-z0-9]{20,}` 与 `Bearer/Basic <cred>` 形状。
- **`Metrics` 进程单例**：线程安全（`threading.Lock`）；只存计数器、gauge、耗时直方图（计数/求和/分位数），
  **绝不**存 prompt/response/key/header/完整路径。`snapshot()` 仅返回数值聚合。

### 3.2 埋点位置

| 位置 | 记录内容 |
| --- | --- |
| `main.py` 关联 ID 中间件 | 每请求关联 ID |
| `model_orchestrator.py` | 状态转换、工具调用（名称/类别/耗时）、候选 diff 生成耗时、`MODEL_CONCURRENCY_EXCEEDED` |
| `openai_compatible_provider.py` | provider 调用（provider/模型 ID/HTTP 类别/耗时/token 聚合）、预算耗尽、错误分类 |
| `event_service.py` | SSE 连接开/关（`sse.connections_active` gauge） |
| `routes.py` | SSE 续传（`sse.resume`） |
| `database.py` `InstrumentedConnection` | SQLite `locked`/`busy` → `sqlite.busy` 计数 |

### 3.3 绝不记录（denylist）

- API Key、Authorization/Cookie、完整 prompt/response、原始代码、完整根路径、绝对路径。
- provider 请求头、未脱敏异常栈、`sk-`/`Bearer` 形状的凭据。
- 第三方库（`httpx`/`httpcore`/`openai`/`langchain*`）默认 INFO 会打印完整请求 URL（含 base URL），
  已在 `configure_logging()` 中压到 **WARNING**，从根上阻断 base URL 经日志泄露。

### 3.4 失败语义（稳定错误码）

- `MODEL_BUDGET_EXCEEDED`：输入字节 / 输出 token / 每 task 请求数任一超预算（在 `_check_budgets` 内计入指标）；2026-08-04 起输出预算在响应返回后本地强制（`_check_output_budget`，含 usage 缺失的保守字节上限）。
- `MODEL_CONCURRENCY_EXCEEDED`：进程内 `_ModelTaskGate`（Phase 1 写租约的 Phase 2 类比）已达
  `max_concurrent_tasks=1`，任务直接置 `failed` 并落 `task.failed` 事件；**无 schema 变更**。
- `APPLY_CONFLICT` / `STALE_BASE`：沿用 Phase 1，审批写前重检基线哈希。
- provider 侧错误经 `map_llm_errors` 映射为 `MODEL_TIMEOUT` / `MODEL_RATE_LIMITED` / `MODEL_UPSTREAM_ERROR` /
  `MODEL_RESPONSE_INVALID` 等，并在 `chat()` 的 try/except 内统一计入 `provider.call:<分类>` 指标后重抛。
- **未知编排异常（2026-08-04）**：编排器兜底分支只持久化固定文案，不插值异常原文——异常中的密钥、Provider URL、绝对路径或响应片段绝不进入任务表、SSE payload 或 API 响应。

### 3.5 SQLite busy 仪表化（无 schema 变更）

`InstrumentedConnection` 薄包装：
- 仅拦截 `execute` / `executemany`，其余属性（含 `commit`、上下文管理器协议）原样委托。
- 捕获 `sqlite3.OperationalError` 且消息含 `locked`/`busy` 时调用 `Metrics.sqlite_busy()` 后原样重抛。
- 保留引擎级 `PRAGMA busy_timeout=5000` 与 WAL，不影响既有迁移/并发语义。

### 3.6 SSE 连接上限（2026-08-04）

- `event_service.acquire_connection()` / `release_connection()` / `active_connections()` 由
  模块级 `_connection_lock` 串行化：检查与递增处于同一临界区，跨线程并发建连不会越过 `SSE_MAX_CONNECTIONS`；
  `Metrics.sse_open/sse_close` 在临界区内更新 gauge，计数与指标不漂移。上限仍为进程级语义。

---

## 4. 验证证据（WP8 + 2026-08-04 审查修复）

- 后端全量 `pytest`：**226 通过 + 2 skipped**（当前基线含 WP8 新增 `test_observability.py` 9 例 +
  `test_model_e2e.py` 4 例、2026-08-04 审查修复用例，以及 2026-08-07 多供应商设置页新增
  `test_provider_profiles.py` 11 例与 `test_provider_settings.py` 8 例）。
- WP8 聚焦（observability + API-mode E2E）：**13/13 通过**。
- 敏感数据扫描：
  - `test_model_e2e.py` 断言日志与事件载荷不含 `test-key` / `api.example.test` / `Bearer` /
    `Authorization` / 真实临时路径。
  - `test_observability.py` 断言 `redact()` 与 `Metrics.snapshot()` 不含密钥/路径。
  - `test_model_orchestrator.py`（2026-08-04）断言未知异常原文与逻辑相对路径不出现在 API/SQLite/SSE 与模型请求上下文中。
- 故障注入覆盖：Provider timeout / 429 / 5xx / 畸形 JSON / 恶意 tool request / 预算耗尽（含输出预算）/
  SQLite busy / SSE 断线续传 / 并发闸门拒绝 / SSE 连接上限并发竞争。
- 前端：**96 测试通过（13 文件）**，`vue-tsc -b` + `vite build --emptyOutDir false` 通过（2026-08-07，
  含 M-01 SSE 持续订阅、M-02 Provider ready 门禁、M-03 失败 UI 错误码映射、M-06 路由归属校验，
  以及多供应商设置页组件与 `provider.service` 用例）。
- 无 skip / 假成功 / 关闭检查绕过门禁。

---

## 5. 已知限制

- 指标为**进程内**单例，仅在单进程后端有效；多 worker 部署需外部聚合（Phase 2 不在范围内）。
- 并发闸门是进程内锁，不是跨进程写租约；并发模型任务上限 1 在 Phase 2 下足够，跨进程互斥留给后续阶段。
- SSE 连接上限为进程级语义，与并发闸门作用域一致。
- 日志为 JSON 文本输出到 stderr，未接入外部日志系统（零新依赖约束）。
