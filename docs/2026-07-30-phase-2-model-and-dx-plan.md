# Phase 2：真实模型与开发者体验实施计划

> **状态：已完成（WP5–WP8 / M4–M6 全部落地，2026-08-03）。** 本计划基于 2026-07-30 对 Phase 1 的静态审查，原要求 Phase 2 代码在 Phase 1 收尾门禁完成前不得启动——该门禁（M1+M2+M3）早已闭合。实现证据与权威设计见 `docs/phase2-model-provider-design.md` 与 `AGENTS.md` 状态追踪；本文件保留为 Phase 2 的计划历史记录。

## 1. 第一性原理与阶段结论

LightCode 的本质不是“把模型接到文件系统上”，而是在不可信模型和不可信浏览器存在的前提下，让用户获得可见、可控、可审计的编码协作。

因此：

- **模型是提议者**：它只能提出计划、受限只读工具请求和候选编辑意图。
- **浏览器是请求者**：它只能提交允许的标识符、审批决定、版本、哈希和幂等键。
- **FastAPI 是唯一权威**：只有服务端可访问已注册工作区、执行 Guard 校验、生成 ChangeSet、维护状态、写 SQLite 事件、调用 Provider、接受审批和写文件。
- **用户审批是写入边界**：模型输出、浏览器请求、候选 patch 都不能直接写入文件；只有服务端生成的 immutable ChangeSet 可进入既有版本绑定审批流程。

结论是：**不能直接开始 Provider 接入。** Phase 1 主闭环已经存在，但审查发现 3 项 P0 缺陷，先关闭这些门禁，再启动 Phase 2。

```text
Phase 1R：安全收尾门禁
  -> M1：P0 安全与审批完整性
  -> M2：多进程竞争证明
  -> M3：真实 UX、SSE 与 API-mode E2E
Phase 2：真实模型与开发者体验
  -> M4：默认关闭的 Provider 基础设施
  -> M5：模型只提议、服务端生成 ChangeSet
  -> M6：模型任务 UX、性能、故障与质量门禁
```

## 2. 阶段目标与预期成果

### 2.1 Phase 1R：安全收尾门禁

目标：证明当前的“单文件、审批后写入”闭环在敏感路径、非法审批、重启恢复和多进程竞争下仍保持安全不变量。

预期成果：

1. `.git/**` 和大小写变体无法被列举、搜索、读取、注册为目标或写入。
2. approve 和 reject 同样绑定 `taskId + changeSetId + revision + diffHash + TTL`；未知决策 fail-closed。
3. 两个独立进程竞争同一目标文件时，最多一个任务成功；另一个得到明确领域错误，不发生静默覆盖或 500。
4. 恢复、读取、搜索和写前重检均通过 `WorkspaceGuard`。
5. 浏览器不再提交自由构造的逻辑路径；SSE、任务状态、设置页与安全契约一致。
6. 单元、API 模式 E2E、跨进程并发、故障注入、类型/格式/覆盖率验证可重复运行。

### 2.2 Phase 2：真实模型与开发者体验

目标：接入一个默认关闭的 OpenAI-compatible Provider，让模型在严格服务端约束下提出计划、受限读取请求与单文件候选编辑意图；服务端验证后独立生成 ChangeSet，用户仍通过版本绑定审批决定是否写入。

预期成果：

1. Provider 仅由后端环境变量配置；前端不输入、保存、回显 API Key 或 Provider URL。
2. 模型只能请求计划、`read_file(fileToken)`、受限 `search_files(query)` 和单文件 `candidate_edit_intent`。
3. 模型不能写文件、执行 Shell、调用网络工具、管理包、写 Git、删除/新建/重命名文件、编辑多文件或做审批决定。
4. 任务完整经过 `planning -> reading_workspace -> generating_diff -> awaiting_approval -> applying_change -> running_verification -> terminal`。
5. Provider 超时、限流、故障、预算耗尽、畸形工具调用和 SSE 断线均有稳定、无敏感信息的处理。

## 3. Phase 1 审查结论与前置门禁

### P0-1：敏感路径策略可绕过

**证据**：`backend/app/security/guard.py` 的 `_is_secret()` 只检查 basename。`.git/config` 的 basename 是 `config`，因此不匹配 `.git`；策略还区分大小写。

**影响**：违反 `docs/phase1-safety-contract.md` 的 `.git/**` 拒绝不变量，错误静态配置还可能使 `.git/config` 成为真实变更目标。

**关闭条件**：使用 canonical logical relative path 的每段检查和 `casefold()`，并令 list/read/search/注册/写前重检/恢复复用唯一策略入口。

### P0-2：拒绝审批绕过 ChangeSet 绑定校验

**证据**：`backend/app/services/phase1.py::submit_approval()` 对非 `approve` 决策在校验 task state、ChangeSet 归属、revision、diffHash 和 TTL 前进入 `_reject()`；`ApprovalRequest.decision` 是无约束字符串。

**影响**：未知决策被当作拒绝；跨任务 ChangeSet 可污染其他任务；终态任务可被再次取消。

**关闭条件**：使用 `Literal["approve", "reject"]`；approve/reject 共享审批对象校验；拒绝只能使用经验证的 ChangeSet 实体，幂等键绑定完整请求指纹。

### P0-3：并发模型未被证明安全

**证据**：应用共享 `sqlite3.Connection(check_same_thread=False)`；`atomic_write.py` 的文件锁仅为进程内 `threading.Lock`。

**影响**：多 Uvicorn worker、多个服务进程或重启竞争时，无法证明“最多一个成功写入”。

**关闭条件**：每个请求/执行单元独立 SQLite connection、`BEGIN IMMEDIATE` 事务、持久化写入租约、跨进程竞争与重启恢复测试。

### P1：进入 Provider 前必须关闭的风险

1. 浏览 API 接收浏览器 `path`，与“浏览器不得传 relativePath/filePath”冲突。
2. 恢复路径直接读取文件，绕过 `WorkspaceGuard`。
3. 未知 `policy` 未在注册阶段 fail-closed。
4. 恢复回退任务时会留下 `approvals.outcome='applying'` 悬挂审计记录。
5. 原子替换未定义 metadata、ACL 和替换后父目录持久化边界。
6. 搜索缺目录/结果/字节/时间预算；SSE 缺连接、回放、慢客户端预算。
7. 前端真实 SSE 未传 `tail=true`，事件只追加不归约任务快照，错误被吞掉。
8. 前端 `RealTaskState` 不完整；设置页错误表示测试命令可直接执行。
9. 缺 API-mode E2E、故障注入、运行时 DTO 校验、lint 与 coverage 门禁。

## 4. 工作包、优先级与实现路径

### WP0：冻结收尾契约与先写失败测试

**优先级：P0。阻塞一切 Phase 2 工作。**

**修改**

- `AGENTS.md`
- `docs/phase1-safety-contract.md`
- `docs/workspace-registration.md`
- `backend/app/schemas/contracts.py`
- `frontend/src/types/agent.ts`

**新增或扩展测试**

- `backend/tests/test_guard.py`
- `backend/tests/test_phase1_negative.py`
- `backend/tests/test_phase1_approval.py`
- `backend/tests/test_phase1_safety.py`
- `backend/tests/test_phase1_concurrency.py`
- `frontend/src/services/event.service.test.ts`
- `frontend/src/stores/real.store.test.ts`
- `frontend/src/views/SettingsView.test.ts`

**先写失败用例**

- `.git/config`、`.GIT/CONFIG`、`.env`、密钥文件在列举、读取、搜索、注册目标、审批写入和恢复中都被拒绝。
- reject 的跨任务 ChangeSet、错误 revision、错误 diffHash、过期 ChangeSet、终态任务与未知 decision 不得造成状态污染或文件写入。
- 两独立进程竞争同一 workspace/target file，最多一个写入成功。
- `tail=true` 订阅、事件 reducer、错误状态和 Settings 命令文案。

**验收**：所有门禁测试先失败再通过；文档冻结规则与 API 实际输入一致。

### WP1：文件策略、审批状态机与恢复闭环

**优先级：P0。**

**修改**

- `backend/app/security/policy.py`
- `backend/app/security/guard.py`
- `backend/app/workspaces/registry.py`
- `backend/app/services/phase1.py`
- `backend/app/schemas/contracts.py`
- `backend/app/schemas/errors.py`

**实现路径**

1. 抽取 `is_sensitive_relative_path()`：对 canonical logical path 每段 `casefold()`，拒绝 `.git` 子树和 secret patterns。
2. 注册表只接受白名单 `phase1-single-text-file` policy；错误 JSON 类型与字符串化布尔值 fail-closed。
3. approval 使用严格枚举，并在 decision 分支前统一验证真实任务、状态、ChangeSet 任务/工作区归属、active 状态、revision、diffHash、TTL 与幂等指纹。
4. `_reject()` 只使用经验证的 ChangeSet；不得读取、锁定或写入文件。
5. 恢复哈希读取迁移到 Guard 专用接口；恢复时结算悬挂审批 outcome。

**验收**：P0-1/P0-2、policy、恢复和错误码回归通过；旧 Mock 任务保持只读演示。

### WP2：SQLite 连接模型、持久化写入租约与并发证明

**优先级：P0。数据库 schema 变更属于红线，实施前必须再次获得用户明确确认。**

**修改或新增**

- `backend/app/db/database.py`
- `backend/app/db/connection.py`（新增）
- `backend/app/main.py`
- `backend/app/services/phase1.py`
- `backend/app/services/atomic_write.py`
- `backend/app/services/write_lease.py`（新增）
- `backend/tests/test_phase1_concurrency.py`（新增）
- `backend/tests/test_phase1_recovery.py`

**实现路径**

1. 以 connection factory 替代全局共享 connection；每个请求/执行单元获取独立 SQLite connection，统一 row factory、WAL、busy timeout 与 foreign key。
2. 新增 `write_leases`，对 `(workspace_id, logical_relative_path)` 建唯一约束，记录 task、ChangeSet、获取/到期时间与结算状态。
3. 在 `BEGIN IMMEDIATE` 内完成审批绑定校验、任务 CAS 到 `applying_change`、租约获取、审批记录和事件写入。
4. 只有租约持有者可执行 Guard 重检和原子替换；终态、失败和恢复明确结算租约。
5. SQLite busy、唯一约束和租约冲突映射为稳定领域错误，不返回 500。
6. 定义并测试 metadata/ACL、父目录同步和故障注入边界。

**验收**：两个独立进程、不同连接、不同幂等键竞争同一目标文件时，稳定地最多一个成功；重启恢复不遗留可双写租约。

### WP3：受控浏览令牌、资源预算与事件传输收尾

**优先级：P1。阻塞模型接入。**

**修改或新增**

- `backend/app/api/routes.py`
- `backend/app/security/guard.py`
- `backend/app/services/phase1.py`
- `backend/app/services/browse_tokens.py`（新增）
- `backend/app/services/event_service.py`（新增或提取）
- `frontend/src/services/registered-workspace.service.ts`
- `frontend/src/services/event.service.ts`
- `frontend/src/stores/real.store.ts`
- `frontend/src/types/agent.ts`
- `frontend/src/views/RealWorkspaceView.vue`
- `frontend/src/views/RealTaskView.vue`

**实现路径**

1. 目录列举返回短期有效、工作区/操作绑定的 `nodeToken`/`fileToken`；文件读取和目录导航只回传 token，不再接收自由 path。
2. 搜索命中返回 file token；跨工作区、过期或 token 类型不匹配一律拒绝。
3. 搜索增加 query、扫描文件、总字节、结果数和执行时间上限；SSE 增加回放上限、tail 超时、心跳、最大连接数和断连处理。
4. 真实任务订阅默认 `tail=true`。经 schema 校验的事件通过 reducer 更新 task、步骤、工具、ChangeSet、验证和失败原因。
5. sequence 缺口触发 task 快照重同步；解析、连接和 stream.end 错误均展示可恢复状态。
6. 事件数组使用窗口或按需加载，避免长会话无限内存增长。

**验收**：浏览器请求不包含 relative path；SSE 可持续、可续传、可重同步；大工作区和慢客户端有明确预算与失败语义。

### WP4：质量门禁、运行时 DTO 校验与用户体验收口

**优先级：P1。阻塞模型接入。**

**修改或新增**

- `frontend/src/services/http.ts`
- `frontend/src/contracts/real-task.schema.ts`（新增）
- `frontend/src/stores/real.store.ts`
- `frontend/src/views/RealWorkspaceListView.vue`
- `frontend/src/views/RealWorkspaceView.vue`
- `frontend/src/views/RealTaskView.vue`
- `frontend/src/views/SettingsView.vue`
- `frontend/package.json`
- `frontend/tsconfig*.json`
- `backend/pyproject.toml`
- `backend/tests/test_api_mode_e2e.py`（新增）
- `README.md`
- `frontend/README.md`
- `backend/README.md`

**实现路径**

1. 以 runtime schema/type guard 校验 HTTP 与 SSE DTO；解析失败显示协议不兼容，不泄漏响应全文。
2. 前端状态机补齐 `created`、`planning`、`reading_workspace`、`generating_diff`、`awaiting_approval`、`applying_change`、`running_verification` 与终态；“运行中”只作 UI 派生状态。
3. 将全局 `loading/error` 拆为列表、目录、预览、搜索、创建、审批、SSE 的资源级状态，并用 AbortController 或请求序号防止旧响应覆盖新路由。
4. 监听路由参数，清理旧 SSE、取消旧请求、校验 task/workspace 路由关系。
5. Settings 明确：Phase 1 仅内建验证，外部命令未启用；Provider 是后端配置的下一阶段能力，前端不管理 API Key。
6. 将可点击 article/div/span 改为 button/link；补齐抽屉 dialog/focus 管理与 `aria-live`。
7. 增加 lint、format、typecheck、coverage、测试类型检查、API-mode 和浏览器级 E2E。

**验收**：真实闭环可在 API 模式自动验证：注册工作区无根路径泄露 -> token 浏览/搜索/预览 -> 创建任务 -> SSE 状态 -> 审批或拒绝 -> 刷新/续传；质量门禁通过。

### M3：允许开始 Provider 基础设施的门槛

仅当 WP0-WP4 全部验收后，才允许开始 Phase 2 模型代码。必须同时满足：

- P0 全部关闭；
- 多进程竞争实测；
- token 浏览取代自由路径输入；
- 前端 SSE 与完整状态机可用；
- API-mode E2E、故障注入、lint/typecheck/coverage 有持续证据；
- 文档和设置页不承诺未实现命令执行。

### WP5：默认关闭的 Provider 配置与健康状态

**优先级：Phase 2 P0。**

**修改或新增**

- `backend/app/config/model_provider.py`（新增）
- `backend/app/services/openai_compatible_provider.py`（新增）
- `backend/app/schemas/model_contracts.py`（新增）
- `backend/app/api/routes.py`
- `backend/app/main.py`
- `backend/app/schemas/errors.py`
- `backend/tests/test_model_provider_config.py`（新增）
- `backend/tests/test_model_provider_http.py`（新增）
- `frontend/src/services/provider.service.ts`（新增）
- `frontend/src/views/SettingsView.vue`

**技术方案**

Provider 仅由后端环境变量配置：

```text
LIGHTCODE_MODEL_ENABLED=false
LIGHTCODE_MODEL_PROVIDER=openai-compatible
LIGHTCODE_MODEL_BASE_URL=https://provider.example/v1
LIGHTCODE_MODEL_API_KEY=...
LIGHTCODE_MODEL_ID=...
LIGHTCODE_MODEL_ALLOWED_ORIGINS=https://provider.example
LIGHTCODE_MODEL_CONNECT_TIMEOUT_SECONDS=5
LIGHTCODE_MODEL_READ_TIMEOUT_SECONDS=45
LIGHTCODE_MODEL_TOTAL_TIMEOUT_SECONDS=60
LIGHTCODE_MODEL_MAX_TOOL_ROUNDS=8
LIGHTCODE_MODEL_MAX_INPUT_BYTES=262144
LIGHTCODE_MODEL_MAX_OUTPUT_TOKENS=2048
LIGHTCODE_MODEL_MAX_REQUESTS_PER_TASK=10
LIGHTCODE_MODEL_MAX_CONCURRENT_TASKS=1
```

实现要求：

1. 默认 `LIGHTCODE_MODEL_ENABLED=false`；未配置 key 时状态为 `unconfigured`，不得发网络请求。
2. Provider client 使用 `trust_env=False`、`follow_redirects=False`、精确 origin allowlist 和显式超时；生产默认 HTTPS，本地 HTTP 仅显式开发开关。
3. `GET /api/v1/provider/health` 只返回 `disabled | unconfigured | ready | degraded`、能力和安全摘要；不得返回 key、Authorization、完整 URL、prompt 或原始 response。
4. 前端只展示 provider/model/status/capabilities，不出现 API Key 或 Base URL 编辑，也不得向 localStorage 写入凭据。

**验收**：缺配置、allowlist 失配、重定向、429/5xx、超时、畸形 JSON、预算耗尽均 fail-closed；日志、SQLite、SSE、HTTP 响应和前端 state 无密钥。

### WP6：受限模型编排与候选 ChangeSet

**优先级：Phase 2 P0。数据库 schema 变更属于红线，实施前必须再次获得用户明确确认。**

**修改或新增**

- `backend/app/services/model_orchestrator.py`（新增）
- `backend/app/services/openai_compatible_provider.py`
- `backend/app/services/phase1.py`
- `backend/app/services/changeset.py`
- `backend/app/security/guard.py`
- `backend/app/schemas/model_contracts.py`
- `backend/app/api/routes.py`
- `backend/app/db/database.py`
- `backend/tests/test_model_orchestrator.py`（新增）
- `backend/tests/test_model_tool_policy.py`（新增）

**模型工具调用协议**

模型只允许输出严格结构化消息：

```json
{
  "kind": "tool_request",
  "tool": "read_file",
  "arguments": { "fileToken": "opaque-server-issued-token" }
}
```

```json
{
  "kind": "candidate_edit_intent",
  "fileToken": "opaque-server-issued-token",
  "baseSha256": "sha256:...",
  "edits": [
    {
      "expectedText": "exact existing bounded text",
      "replacementText": "bounded replacement text",
      "occurrence": 1
    }
  ],
  "rationale": "简短说明",
  "plan": ["..."]
}
```

模型不得请求或输出：absolute/relative path、rootPath、write/apply patch、shell/exec、network、npm/pip/pytest、Git、删除、新建、重命名、多文件、ChangeSet hash/revision 或审批决定。

**服务端裁决路径**

1. 浏览器只提交 `workspaceId + title`。
2. 服务端创建任务并进入 `planning`。
3. Provider 提出受限读取请求；服务端验证 token 并通过 Guard 执行，持久化工具事实。
4. 模型提出 candidate edit intent；服务端校验 base hash、精确唯一文本替换、单文件/UTF-8/大小/diff 限制。
5. 服务端在内存中应用意图，独立计算 diff/hash，并持久化 immutable ChangeSet。
6. 仅成功验证后进入 `awaiting_approval`；写入仍完全复用 Phase 1 的版本绑定审批、租约、原子写和内建验证。
7. 模型输出不是事实事件，也不能直接成为 ChangeSet。

**验收**：模型可形成候选 diff，但不能直接写入；恶意工具调用、越权 token、超过轮次、超预算、诱导网络调用和结构化消息异常均安全失败。

### WP7：模型任务 SSE、前端状态机和开发体验

**优先级：Phase 2 P1。**

**修改或新增**

- `frontend/src/types/agent.ts`
- `frontend/src/contracts/real-task.schema.ts`
- `frontend/src/services/real-task.service.ts`
- `frontend/src/services/event.service.ts`
- `frontend/src/stores/real.store.ts`
- `frontend/src/views/RealWorkspaceView.vue`
- `frontend/src/views/RealTaskView.vue`
- `frontend/src/views/SettingsView.vue`
- `frontend/src/stores/real.store.test.ts`
- `frontend/src/views/RealTaskView.test.ts`

**实现路径**

1. Provider 调用、工具读取、候选意图和 ChangeSet 生成都以持久化事件映射到完整任务状态机。
2. 前端对 event 做 schema 校验、sequence 去重、缺口全量同步和连接状态建模。
3. 用户启动模型任务前明确知悉：被 Guard 允许的代码片段会发送至已配置 Provider；UI 仅展示安全摘要。
4. `awaiting_approval` 展示目标文件、ChangeSet revision、diff hash、有效期、策略版本和“不执行外部命令”。
5. Provider degraded 时禁用新模型任务，但保持历史、查看和已有 ChangeSet 审批。

**验收**：模型任务从 planning 到 awaiting approval 的 SSE 生命周期在 API 模式下可复现，断线后可续传，失败状态有可行动且无敏感信息的提示。

### WP8：性能、可观测性与发布门禁

**优先级：Phase 2 P1。**

**修改或新增**

- `backend/app/services/model_orchestrator.py`
- `backend/app/services/event_service.py`
- `backend/app/config/model_provider.py`
- `backend/tests/test_model_e2e.py`（新增）
- `frontend/package.json`
- `backend/pyproject.toml`
- `README.md`
- `AGENTS.md`
- `docs/architecture/lightcode-local-first-agent-design.md`
- `docs/phase2-model-provider-design.md`（新增）

**初始预算**

| 范围 | 初始上限 |
| --- | ---: |
| 单文件读取 | 1 MB |
| 搜索 query | 256 字符 |
| 单次搜索扫描文件 | 5,000 |
| 单次搜索扫描字节 | 20 MB |
| 搜索结果 | 100 |
| 搜索执行时间 | 2 秒 |
| SSE 重放事件 | 1,000 |
| SSE tail | 30 秒 |
| SSE 心跳 | 10-15 秒 |
| 每 task 工具轮数 | 8 |
| 每 task Provider 请求 | 10 |
| 每 task Provider 输入 | 256 KB |
| 每 task Provider 输出 | 2,048 token |
| 并发模型任务 | 1 |

**可观测性**

记录：task/correlation ID、状态转换、工具名称/耗时/类别、provider 名称/模型 ID/HTTP 类别/耗时/token 聚合、预算、SQLite busy、写入租约、SSE 连接与重连指标。

绝不记录：API Key、Authorization/Cookie、完整 prompt/response、原始代码、完整根路径、绝对路径、provider 请求头或未脱敏异常栈。

**验收**：

- API-mode E2E：token 浏览 -> 模型计划/受控读取 -> 候选 ChangeSet -> 审批/拒绝 -> 原子写/内建验证 -> 刷新与 SSE 续传。
- 故障：Provider timeout、429、5xx、畸形 JSON、恶意 tool request、预算耗尽、SQLite busy、SSE 断线。
- 超限有稳定失败语义；无无限扫描、无限 event array 或无限请求循环。
- lint、format、typecheck、coverage、全量测试、API-mode E2E、并发和敏感数据扫描全部通过。

## 5. 里程碑与验收成果

| 里程碑 | 达成条件 |
| --- | --- |
| M1：P0 收口 | 敏感路径、审批绑定、恢复 Guard 与 P0 测试全绿。 |
| M2：竞争安全 | 独立连接、持久化写租约和跨进程同文件竞争实测；最多一个成功。 |
| M3：Phase 1 可验证 UX | token 浏览、SSE tail/reducer/重同步、完整状态机、API-mode E2E、文档/设置页一致。达到后才可接模型。 |
| M4：Provider 基础设施 | 默认关闭、环境变量配置、health、allowlist、超时/预算与零密钥泄露证据。 |
| M5：模型只提议 | 受限工具协议、服务端 ChangeSet 生成、用户审批边界和恶意请求回归通过。 |
| M6：Phase 2 收尾 | 模型 API-mode E2E、性能/故障/并发/安全质量门禁与文档通过。 |

## 6. 风险评估与应对策略

| 风险 | 应对策略 |
| --- | --- |
| Provider 输出非结构化或恶意工具调用 | 仅接受严格 schema；未知类型 fail-closed；服务端重新验证 token、hash、策略和编辑意图。 |
| API Key 泄露到日志、状态或事件 | 仅环境变量；配置对象不序列化 key；捕获日志 sink 测试；SSE/DTO denylist 测试。 |
| 并发审批/多 worker 竞争同一文件 | 独立连接、BEGIN IMMEDIATE、持久化写租约、CAS 和跨进程测试。 |
| Provider 费用或延迟不可控 | 默认关闭、task 预算、并发 1、严格 timeout、轮次/request/token 上限和聚合可观测性。 |
| 模型读取过多源码或敏感信息 | token 化受控文件、Guard、secret policy、输入字节预算、用户启动时明确披露。 |
| SSE 断线或事件漂移 | sequence、runtime schema、reducer、缺口全量同步、连接状态和有限重连。 |
| 文档与实现再次漂移 | 每个里程碑将合约测试、运行说明和风险清单作为验收交付；不以人工演示替代自动化证据。 |

## 7. 刻意不做

Phase 2 首版不实现：

1. 前端输入、持久化、同步、回显 API Key；
2. Shell、subprocess、PowerShell、cmd、pytest、npm、pip、包管理、网络工具或下载；
3. Git 写操作；
4. 删除、新建、重命名、移动、二进制或多文件 ChangeSet；
5. 自动批准、自动修复循环或模型直接写文件；
6. Electron、原生文件夹选择、远程工作区、云同步或多用户协作；
7. 模型列表自动探测、自由 Provider URL 或隐式代理；
8. 在 M3 前接入任意真实模型依赖、端点或网络调用。

## 8. 验证纪律

每个工作包必须遵守：**先写失败测试 -> 最小实现 -> 聚焦验证 -> 完整回归**。最终需运行后端全量 pytest、前端全量 Vitest、前端 typecheck/build，以及新增 API-mode E2E、跨进程并发和故障注入测试。

不得使用 skip、假成功或关闭检查绕过门禁；因环境能力导致的 symlink skip 必须保留 monkeypatch 逻辑级覆盖，并在支持符号链接的环境运行真实文件系统用例。
