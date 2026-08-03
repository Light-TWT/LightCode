# Phase 2 模型 Provider 与可观测性设计

本文件是 Phase 2（WP5–WP8）模型 Provider 子系统与可观测性/发布门禁的**权威设计参考**。
工作包划分、里程碑与验收标准见 `2026-07-30-phase-2-model-and-dx-plan.md`；本文件只记录
已落地的架构决策、接口契约与验证证据，避免与计划文档重复。

> 约束：Phase 2 首版**不**实现 Shell/外部命令、包管理、网络下载、Git 写操作、删除/新建/重命名、
> 多文件事务、二进制/非 UTF-8 修改、Electron、本地文件夹选择、自动批准或模型直接写文件。
> WP8 经用户确认采用**零新增第三方依赖**策略（stdlib `logging` + 进程内指标 + 既有 pytest/vitest）。

---

## 1. Provider 配置（WP5，M4）

### 1.1 配置来源与 fail-closed

- 配置**仅**来自后端环境变量，浏览器不输入、持久化、回显或传输 API Key / base URL。
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
- 受限工具协议：模型仅可请求 `read_file` / `search_files`（见 `MODEL_ALLOWED_TOOLS`）。
- 候选编辑由服务端 `build_model_change_set` 独立生成 Difference，绝不依赖模型输出的补丁文本。
- 恶意工具请求（含 `rootPath`/`filePath`/自由路径/超预算）fail-closed 拒绝。
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

- `MODEL_BUDGET_EXCEEDED`：输入字节 / 输出 token / 每 task 请求数任一超预算（在 `_check_budgets` 内计入指标）。
- `MODEL_CONCURRENCY_EXCEEDED`：进程内 `_ModelTaskGate`（Phase 1 写租约的 Phase 2 类比）已达
  `max_concurrent_tasks=1`，任务直接置 `failed` 并落 `task.failed` 事件；**无 schema 变更**。
- `APPLY_CONFLICT` / `STALE_BASE`：沿用 Phase 1，审批写前重检基线哈希。
- provider 侧错误经 `map_llm_errors` 映射为 `MODEL_TIMEOUT` / `MODEL_RATE_LIMITED` / `MODEL_UPSTREAM_ERROR` /
  `MODEL_RESPONSE_INVALID` 等，并在 `chat()` 的 try/except 内统一计入 `provider.call:<分类>` 指标后重抛。

### 3.5 SQLite busy 仪表化（无 schema 变更）

`InstrumentedConnection` 薄包装：
- 仅拦截 `execute` / `executemany`，其余属性（含 `commit`、上下文管理器协议）原样委托。
- 捕获 `sqlite3.OperationalError` 且消息含 `locked`/`busy` 时调用 `Metrics.sqlite_busy()` 后原样重抛。
- 保留引擎级 `PRAGMA busy_timeout=5000` 与 WAL，不影响既有迁移/并发语义。

---

## 4. 验证证据（WP8）

- 后端全量 `pytest`：**190 通过 + 2 skipped**（含 WP8 新增 `test_observability.py` 9 例 +
  `test_model_e2e.py` 4 例）。
- WP8 聚焦（observability + API-mode E2E）：**13/13 通过**。
- 敏感数据扫描：
  - `test_model_e2e.py` 断言日志与事件载荷不含 `test-key` / `api.example.test` / `Bearer` /
    `Authorization` / 真实临时路径。
  - `test_observability.py` 断言 `redact()` 与 `Metrics.snapshot()` 不含密钥/路径。
- 故障注入覆盖：Provider timeout / 429 / 5xx / 畸形 JSON / 恶意 tool request / 预算耗尽 /
  SQLite busy / SSE 断线续传 / 并发闸门拒绝。
- 前端 WP8 无代码变更；既有 64 测试 + `vue-tsc -b` + `vite build` 仍有效。
- 无 skip / 假成功 / 关闭检查绕过门禁。

---

## 5. 已知限制

- 指标为**进程内**单例，仅在单进程后端有效；多 worker 部署需外部聚合（Phase 2 不在范围内）。
- 并发闸门是进程内锁，不是跨进程写租约；并发模型任务上限 1 在 Phase 2 下足够，跨进程互斥留给后续阶段。
- 日志为 JSON 文本输出到 stderr，未接入外部日志系统（零新依赖约束）。
