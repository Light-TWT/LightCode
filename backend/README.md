# LightCode 后端

## 概述

`backend/` 是 LightCode 的唯一权威边界：工作区注册、文件访问、模型出网、ChangeSet、审批与原子写入全部在服务端完成。基于 FastAPI + SQLite，当前承载：

- **聊天闭环**：`chat_sessions` / `chat_messages` 持久化，`ChatService` + LangGraph `ChatOrchestrator` 分流自由问答（answer）与编辑任务（candidate_edit_intent）。
- **模型提议**：OpenAI-compatible Provider 默认关闭、仅"提议"——模型计划、受限只读工具请求（`read_file`/`search_files`）与服务端独立生成的候选 ChangeSet；不写文件、不执行命令、不决定审批。发往 Provider 的上下文不含逻辑相对路径（仅 fileToken/哈希/受控文本）。可观测性、预算/并发/故障门禁与敏感数据扫描见本文「可观测性」一节，设计细节见 `../docs/phase2-model-provider-design.md`。
- **真实文件能力**：工作区注册（静态 `workspaces.json` + 桌面动态注册）、受控只读工具（`list_files`/`read_file`/`search_files`）、服务端生成的确定性 ChangeSet、版本绑定审批、单个既有 UTF-8 文本文件的原子替换与内建完整性验证。安全不变量以 `../docs/phase1-safety-contract.md` 与 `../docs/workspace-registration.md` 为准。
- **Provider 运行期设置**：多供应商 profiles（`/api/v1/provider/profiles` CRUD）与设置（`/provider/settings`），凭据经 `ProviderCredentialStore` 存储——Web 开发期为进程内存，桌面模式为 Windows Credential Manager。
- **技能管理**：ZIP 上传、详情、启用/删除与 Agent 门禁，见 `app/services/skill_service.py`。

## 结构

```text
app/
  main.py                  FastAPI 入口、CORS、SQLite 与 WorkspaceRegistry 生命周期；GET /health
  api/routes.py            REST 与 SSE 路由（prefix=/api/v1）
  config/
    model_provider.py      ModelProviderConfig（仅环境变量、fail-closed、safe_summary 无密钥）
    desktop.py             桌面模式配置（数据目录、sidecar 令牌/端口）
    skills.py              技能目录与预算常量
  db/
    database.py            SQLite schema、迁移与初始化（WAL + busy_timeout）
    connection.py          独立连接工厂（供并发验证复用）
  schemas/
    contracts.py           camelCase Pydantic 请求/响应合约（extra="forbid"）
    model_contracts.py     模型/Provider/聊天 DTO（extra="forbid"）
    skill_contracts.py     技能 DTO
    errors.py              稳定错误码（Phase1Error / MODEL_* / SKILL_*）
  security/
    fs.py                  文件系统分类与规范化
    guard.py               WorkspaceGuard 统一路径守卫
    policy.py              策略唯一来源（扩展名白名单、敏感路径、预算常量）
  services/
    phase1.py              真实任务生命周期与 6 步审批写入协议
    changeset.py           确定性 ChangeSet 生成与精确唯一文本替换
    atomic_write.py        临时文件 + os.replace 原子替换 + 内建 UTF-8/哈希验证 + 每文件锁
    chat_service.py        ChatService + LangGraph ChatOrchestrator
    model_orchestrator.py  LangGraph 编排与 create_model_task（模型只提议）
    openai_compatible_provider.py  OpenAI-compatible chat 适配（信任边界/超时/预算/错误分类）
    llm_client.py          build_llm 工厂（trust_env=False / follow_redirects=False / max_retries=0）
    credential_store.py    可替换 Provider 凭据存储（内存 / Windows Credential Manager）
    browse_tokens.py       HMAC-SHA256 短期浏览令牌（绑定 workspace+operation+relative_path）
    event_service.py       SSE 事件生成（重放上限/心跳/tail 续传/最大连接数）
    workspace_registration.py  桌面动态工作区注册（令牌校验 + canonical 校验）
    skill_package.py       ZIP 安全校验与提取（fail-closed）
    skill_service.py       技能 CRUD 与 Agent 门禁
    observability.py       单一日志/指标出口（JSON 格式、关联 ID、redact 拒绝名单、进程内 Metrics）
  workspaces/
    registry.py            服务端工作区注册表（静态配置加载）
tests/                    pytest 用例；每个用例使用隔离临时数据库
pyproject.toml            Python 依赖与 pytest 配置
```

SSE 事件生成在 `app/services/event_service.py`（重放上限 1000、心跳 10s、tail 窗口 30s、最大连接数 50），由 `app/api/routes.py` 通过 `stream_events(...)` 输出。SSE 仅回放 SQLite 中已持久化且按 `sequence` 排序的事件。每帧携带 `id:`（即 `sequence`），支持 `?after_sequence=<n>` 显式续传与浏览器自动重连的 `Last-Event-ID`；`?tail=true` 时回放后保持连接轮询新事件，否则发送 `stream.end` 后关闭。

## 依赖与启动

需要 Python 3.11 或更高版本。推荐使用隔离环境：

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows；macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
```

从 `backend/` 目录启动开发服务：

```bash
uvicorn app.main:app --reload --port 8000
```

`main.py` 会将本地 `backend/` 置于 Python 导入路径前部，避免系统环境中同名 `app` 包影响 `uvicorn app.main:app`。

前端开发模式通过 Vite `/api` 代理访问 `http://127.0.0.1:8000`（见 `frontend/README.md`）。

## 配置与数据

### 运行时数据库

- 默认路径：`<repo>/backend/data/lightcode.db`，由 `main.py` 基于自身位置解析为绝对路径。
- 可使用 `LIGHTCODE_DATABASE_PATH` 指向隔离的临时数据库；相对路径以 `backend/` 为基准解析。
- 根 `.gitignore` 忽略 `backend/data/*.db` 及其 `-shm`/`-wal` 文件。
- 运行时数据（会话、消息、任务、ChangeSet、审批、桌面工作区注册）绝不进入源码历史。

### 工作区注册

- **静态注册**：默认配置文件 `backend/workspaces.json`（含 `rootPath` + `targetFile` 等，含机器特定绝对路径）；也可用 `LIGHTCODE_WORKSPACES_CONFIG` 指向任意 JSON。该文件**已 gitignore，绝不提交**。
- **桌面动态注册**：桌面模式经 `POST /api/v1/desktop/workspaces/register` 注册（per-launch sidecar 令牌校验，canonical/reparse 校验后写入 SQLite `desktop_workspaces`），同一 canonical root 幂等返回既有工作区。
- 仓库内置 `backend/workspaces.example.json` 模板：复制为 `backend/workspaces.json` 后，将每条 `rootPath` 改为本机真实绝对路径（`rootPath` 不得是符号链接/junction 且必须真实存在）。
- 配置形态与启动校验规则见 `../docs/workspace-registration.md`。

### 凭据存储

- Web 开发期：`InMemoryProviderCredentialStore`（进程内存，重启后丢失，绝不落盘）。
- 桌面模式：`WindowsCredentialManagerProviderCredentialStore`（Windows Credential Manager，见 `credential_store.py`）。
- 任何情况下 API Key 不进 SQLite、日志、SSE 或前端持久化。

## REST 路由

```text
GET   /health                                       服务存活探针
GET   /api/v1/registered-workspaces                 注册工作区列表
GET   /api/v1/registered-workspaces/{id}/files      文件树（nodeToken）
GET   /api/v1/registered-workspaces/{id}/file       文件读取（fileToken）
GET   /api/v1/registered-workspaces/{id}/search     内容搜索（query）
POST  /api/v1/desktop/workspaces/register           桌面动态注册（sidecar 令牌）
POST  /api/v1/real-tasks                            创建真实任务
GET   /api/v1/real-tasks/{id}                       任务详情
POST  /api/v1/real-tasks/{id}/approval              审批（decision/changeSetId/revision/diffHash/idempotencyKey）
GET   /api/v1/real-tasks/{id}/events                SSE 事件（续传/tail）
GET   /api/v1/provider/health                       只读健康状态（不发网络请求）
GET   /api/v1/provider/settings                     设置摘要
POST  /api/v1/provider/settings/test                仅测试连接
POST  /api/v1/provider/settings                     测试并保存
DELETE /api/v1/provider/settings                    清除
GET   /api/v1/provider/profiles                     供应商列表
POST  /api/v1/provider/profiles                     添加（连接测试通过才保存）
GET   /api/v1/provider/profiles/{id}                供应商详情
DELETE /api/v1/provider/profiles/{id}               删除供应商
POST  /api/v1/model-tasks                           创建模型任务
GET   /api/v1/model-tasks/{id}                      模型任务详情
GET   /api/v1/workspaces/{id}/chat-sessions         会话列表
POST  /api/v1/workspaces/{id}/chat-sessions         创建会话
GET   /api/v1/chat-sessions/{id}                    会话详情
POST  /api/v1/chat-sessions/{id}/messages           提交消息
PATCH /api/v1/chat-sessions/{id}                    重命名等
DELETE /api/v1/chat-sessions/{id}                   删除会话
GET   /api/v1/chat-sessions/{id}/events             SSE chat 事件
GET   /api/v1/skills                                技能列表
GET   /api/v1/skills/{id}                           技能详情
GET   /api/v1/skills/{id}/document                  技能文档
POST  /api/v1/skills/upload                         ZIP 上传
PATCH /api/v1/skills/{id}/status                    启用/禁用
DELETE /api/v1/skills/{id}                          删除（仅 uploaded）
```

所有 JSON 使用 camelCase。文件树（`/files`）与文件读取（`/file`）不接收自由路径，改用不透明浏览令牌（`browse_tokens`）；`/search` 命中项带回绑定 `operation="read"` 的令牌供前端直接打开。公共 DTO、SSE、日志与错误信息均不含真实根路径；审批请求仅接受 `decision`/`changeSetId`/`revision`/`diffHash`/`idempotencyKey`，Pydantic `extra="forbid"` 拒绝任何 `rootPath`/`filePath`/patch/command。稳定错误码见 `app/schemas/errors.py`。

## 禁止清单（全局）

- 模型写文件、执行命令、调用网络工具、管理包、写 Git 或决定审批；
- 新建/删除/重命名/移动、多文件事务、二进制/非 UTF-8/超限文件的修改；
- Shell、`subprocess`、依赖安装、网络下载与 Git 写操作；
- API Key、密码、token 或其他密钥进入 SQLite、日志、SSE、前端持久化或截图。

## 可观测性

所有日志与指标只经 `app/services/observability.py`，避免多 sink 泄露敏感数据。

### 日志级别

- 由环境变量 `LIGHTCODE_LOG_LEVEL` 控制（默认 `WARNING`）。
- `configure_logging()` 将 `httpx`/`httpcore`/`openai`/`langchain*` 日志器压到 `WARNING`，阻断第三方库在 INFO 打印完整请求 URL（含 provider base URL）的泄露路径。
- 每条记录为单个 JSON 对象，附关联 ID（`correlation_id`）；`exc_info` 文本被脱敏。

### 指标

- 进程内 `Metrics` 单例只聚合数值：任务状态转换、工具调用（名称/类别/耗时）、provider 调用（provider/模型 ID/HTTP 类别/耗时/token）、预算耗尽、并发拒绝、SSE 连接/续传、SQLite busy。
- 指标不含 prompt/response/key/header/完整路径。进程内单例仅对单进程后端有效。

### 敏感数据不变

- 绝不记录：API Key、Authorization/Cookie、完整 prompt/response、原始代码、完整根路径、provider 请求头、未脱敏异常栈、`sk-`/`Bearer` 形状的凭据。
- `redact()` 对 secret/location 键与凭据形状做递归脱敏；`test_model_e2e.py` 断言日志与事件载荷不含 `test-key`/`api.example.test`/`Bearer`/`Authorization`/真实临时路径。

### 失败语义

- `MODEL_BUDGET_EXCEEDED`：输入字节 / 输出 token / 每 task 请求数超预算；输出预算由 `_check_output_budget` 本地强制。
- `MODEL_CONCURRENCY_EXCEEDED`：进程内 `_ModelTaskGate` 已达 `max_concurrent_tasks=1`。
- `APPLY_CONFLICT` / `STALE_BASE`：审批写入前的并发冲突与基线不一致检测。
- `InstrumentedConnection` 拦截 SQLite `locked`/`busy` 并计入 `sqlite.busy` 指标（保留 `PRAGMA busy_timeout` 与上下文协议）。

## 验证

从 `backend/` 目录运行：

```bash
python -m pytest -q
```

当前基线：**303 passed / 2 skipped**（跳过项为沙箱环境 `os.symlink` 静默降级导致不可检测，对应逻辑由 monkeypatch 测试覆盖）。聚焦用例：`test_phase1_*`（真实任务/审批/安全）、`test_model_orchestrator.py` / `test_model_e2e.py`（模型编排/API-mode E2E）、`test_observability.py`（脱敏/指标）、`test_provider_*`（Provider 设置/健康）、`test_skill_*`（技能）、`test_desktop_*` / `test_credential_manager.py`（桌面注册与凭据）。

全量验证还应从 `frontend/` 运行 `npm run test` 与 `npm run build`，从 `electron/` 运行 `npm run test`。
