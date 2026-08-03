# LightCode 开发规则

## 项目目标

LightCode 是一个独立实现的、本地优先的可视化编码智能体，面向有基础编程经验的开发者。它不是 MiniCode-Python 或其他编码智能体项目的分支、重写或源码延续。

## 当前阶段

项目处于阶段 1：安全变更 MVP（后端 T1-T7/T9 与前端 T8 均已完成，处于收尾验证阶段）。Phase 0.5 Mock Runtime 保留为 legacy，仅供读取与演示。

- 冻结范围、安全不变量、状态机、审批写入协议与错误码以 `docs/phase1-safety-contract.md` 为准；产品总体行为以 `docs/architecture/lightcode-local-first-agent-design.md` 为准。
- 真实工作区根路径只来自服务端静态注册表（`LIGHTCODE_WORKSPACES_CONFIG` 或 `backend/workspaces.json`，已 gitignore）；公共 DTO、SSE、日志、错误一律不得返回真实根路径。
- 每次文件访问必须经 `WorkspaceGuard`。ChangeSet 由服务端生成、持久化、版本化；审批绑定 `changeSetId + revision + diffHash`；写前重检基线哈希，冲突返回 `STALE_BASE`；单文件临时文件 + 原子替换 + 内建 UTF-8/哈希验证。
- 浏览器只提交 `workspaceId`、任务标识、审批决定、`changeSetId`、`revision`、`diffHash`、`idempotencyKey`（Pydantic `extra="forbid"` 拒绝任何 `rootPath`/`filePath`/patch/command）。
- 后端 API 必须保持 `/api/v1` 与 camelCase JSON。
- 仍不得实现：真实模型/提供商 Key/密钥管理、Shell/subprocess/包管理/网络下载/Git 写操作、删除/新建/重命名/移动、多文件事务、二进制/非 UTF-8/超限文件修改、Electron、本地文件夹选择。
- Phase 0.5 允许的能力（FastAPI、SQLite、确定性 Mock Runtime、REST、SSE、前端 HTTP/EventSource 适配器）继续保留，Mock 与真实闭环隔离。

## 必读文件

在设计或实现工作之前，请阅读：

- `docs/architecture/lightcode-local-first-agent-design.md`
- `docs/2026-07-23-phase-0-5-runtime-foundation.md`
- `docs/2026-07-30-phase-2-model-and-dx-plan.md`
- `docs/design/README.md`
- `docs/design/` 下相关的 HTML 原型文件

## 源码独立性

- 不得复制 MiniCode-Python 或其他编码智能体项目的源代码、测试、名称或文档。
- 根据 LightCode 自身记录的需求来设计和实现。
- 将架构决策和实现证据保留在此仓库中。

## 目录结构

```text
frontend/       Vue 应用和 Mock/HTTP/SSE 服务适配器
backend/        阶段 0.5 的 FastAPI 和 SQLite Mock Runtime
electron/       为后续桌面 shell 保留
docs/architecture/ 产品架构与决策
docs/design/       已批准的 HTML 视觉原型与 UI 备注
scripts/        开发与验证脚本
```

## 前端规则

- 使用 Vue 组件、Vue Router、Pinia 存储、类型化夹具和服务接口。不得将视觉原型整体粘贴到应用视图中。
- 将 `docs/design/` 中的 HTML 文件视为视觉和交互参考，而非运行时代码。
- 完整差异仅保留在右侧审查抽屉中。执行流只显示紧凑的差异摘要。
- 当变更集等待审批时，底部栏显示审查和拒绝操作，而非新任务输入框。

## 运行时规则

### Phase 0.5 已完成范围

- FastAPI 仅暴露确定性 Mock 数据和审批状态迁移；不得宣称或模拟真实项目文件访问、源码写入、终端执行或模型调用。
- SSE 只回放 SQLite 中已持久化的有序事件；不得伪造持续模型流。
- 提供商 API Key 不得进入 SQLite、事件、前端状态、日志或截图。
- Phase 0.5 的任务分解与实现记录见 `docs/2026-07-23-phase-0-5-runtime-foundation.md`；当前实现以源码和 README 为准。

### Phase 1 实施前置规则

- 实施前必须先阅读 `docs/phase1-safety-contract.md` 与 `docs/workspace-registration.md`，再更新代码或 API 合约。
- 真实工作区根路径仅来自服务端启动静态配置；浏览器只能提交 `workspaceId`，不能提交本地路径、文件路径、补丁、文件内容或命令。
- Phase 1 仅允许受控只读工具、服务端确定性 ChangeSet、显式版本绑定审批、单个既有 UTF-8 文本文件的原子替换和内建完整性验证。
- Phase 1 继续禁止真实模型、Electron、Shell/外部命令、依赖安装、网络下载、Git 写操作和密钥处理。

## 验证

- 每个任务完成后运行对应的后端或前端聚焦测试；所有任务结束后运行后端全量测试、前端全量测试和前端构建。
- 没有当前的测试/构建证据，不得声称页面或运行时功能已完成。
- 不得为了通过验证而引入 `skip`、假成功状态、禁用失败的检查或绕过手段。

## 状态追踪

```text
前端: 87 测试通过 (17 文件), vue-tsc -b + vite build 通过 (2026-08-03)
WP6 前端: 完成 (2026-07-31) —— 新增模型任务创建入口与 UI（RealWorkspaceView 侧栏"创建模型任务"面板 + store.createModelTask + model-task.service 双实现 + parseModelTask 契约校验 + 3 个测试文件 17 例）；复用既有 real-task 任务视图显示模型任务（get_real_task 含 kind='model'）；vite build --emptyOutDir false 通过
WP7 (模型任务 SSE / 前端状态机 / 开发体验): 完成 (2026-08-03) —— 纯前端，无后端改动（复用 WP6 LangGraph 编排 emit 的事件 + WP3 SSE 续传通道）。新增：types/agent.ts 模型生命周期类型(ModelLifecycleStep/ModelLifecycleStage/EventConnection) + MODEL_TASK_EVENT_TYPES；contracts/real-task.schema.ts 新增 parseModelLifecycleEvent（模型事件 payload 防御性校验）；real.store.ts 新增 eventConnection 状态机(connecting/open/reconnecting/closed) + SSE sequence 缺口全量同步(_resync，带 _resyncing 防重入) + modelLifecycle getter（从事件派生有序阶段，最远到达阶段为 current，失败标记 failed）；RealWorkspaceView 强化启动前数据披露(代码片段发往已配置 Provider) + Provider degraded 门禁新建(保留历史/查看/审批)；RealTaskView 增加 kind 徽标 + 模型生命周期时间线 + awaiting_approval 策略版本与"不执行外部命令"说明 + SSE 连接态 + 失败可行动无敏感提示(精确正则拒绝 sk-+20位密钥)；phase1.fixture.ts 新增 modelTaskFixture/modelTaskEventsFixture；real-task.service mock 支持模型任务 id。验证：新增 real.store.test.ts 5 例 + RealTaskView.test.ts 6 例（共 11 例 WP7），前端全量 87 passed / 17 文件，vue-tsc -b + vite build 通过，无回归
后端: 117 测试通过 + 2 skipped (沙箱 symlink 静默降级, 逻辑已由 monkeypatch 测试覆盖) (2026-07-30)
Phase 0.5 收尾: DB 路径绝对化 + Git 跟踪移除已完成; API 模式持久化验证通过 (临时 DB 审批持久化, 新库回到 awaiting_approval)
Phase 1 后端: T1-T7 + T9 完成; API 模式 HTTP 全闭环验证 16/16 通过
  (注册工作区无根路径泄露 -> 创建真实任务 awaiting_approval -> 审批原子写 + 内建验证 completed
   -> 磁盘文件确实变更且基线保留 -> 幂等重放不重复写 -> 重启持久化 completed
   -> 新库回到 awaiting_approval -> STALE_BASE 失败且外部改动保留)
Phase 1 前端 (T8): 完成; 8 个 Phase 1 端点全部有对应 UI
  (/real 注册工作区列表 -> /real/:id 文件树/预览/搜索/建任务 -> /real/:id/task/:taskId 计划/diff/审批/SSE)
  服务层 mock+http 双实现按 VITE_LIGHTCODE_RUNTIME 切换; 审批请求体测试断言严格等于 extra=forbid 契约; 响应无 rootPath
  端到端演示验证通过 (registered-workspaces 代理连通, 审批后磁盘文件真实变更)
Phase 1R (安全收尾门禁, WP0-WP4 = M1+M2+M3): 全部完成 (2026-07-30)
  WP0: 先写失败测试 (P0-1/2/3 门禁用例) 已完成并转绿
  WP1 (M1 P0-1/2): policy.casefold 敏感路径逐段拒绝 (.git/** .env 大小写变体);
    ApprovalRequest.decision=Literal["approve","reject"] 未知决策 422 fail-closed;
    审批绑定校验前置 decision 分支; registry policy 白名单 fail-closed;
    APPLY_CONFLICT 稳定错误码
  WP2 (M2 P0-3): 多进程文件级原子条件 UPDATE 作跨进程 CAS (无 schema 变更, 规避红线);
    提交后再写文件; test_phase1_concurrency 证明两独立连接/进程同文件最多一个写入
  M3 (WP3+WP4): 已完成 — browse_tokens (HMAC-SHA256 短期 TTL, 绑定 workspace+operation+relative_path,
    取代浏览器自由路径) + event_service (SSE 重放上限/心跳/tail 续传/最大连接数) +
    前端 token 面包屑导航 (不持有自由路径) + runtime DTO schema 校验 (ContractValidationError,
    拒绝含 rootPath 的 workspace / 未知 task state) + API-mode E2E (test_api_mode_e2e 全闭环) +
    质量门禁 (vue-tsc -b + vite build --emptyOutDir false 通过)
  3 个 P0 缺陷 (P0-1 敏感路径绕过 / P0-2 审批绑定绕过 / P0-3 并发未证安全) 全部关闭; M1+M2+M3 全绿

### Phase 2 (WP5 默认关闭的 Provider 配置与健康状态, 2026-07-31)

- WP5 完成 (后端 + 前端), 严格 default-off + fail-closed, 零 Phase 1 闭环风险, 无 DB schema 变更:
  - 后端: `app/config/model_provider.py` (ModelProviderConfig frozen dataclass, 环境变量加载, 状态 disabled|unconfigured|ready|degraded, secret 不进 repr/str/summary) +
    `app/services/openai_compatible_provider.py` (OpenAICompatibleProvider.chat: trust_env=False, follow_redirects=False, 显式超时, 每任务请求预算, 稳定错误码) +
    `app/schemas/model_contracts.py` (ProviderHealth/Capabilities/Security, extra=forbid, camelCase, 无 key/baseUrl/authorization) +
    `app/api/routes.py` 新增 `GET /api/v1/provider/health` (只读 config 派生, 不发网络请求) +
    `app/main.py` lifespan 载入 `app.state.model_provider` (仅打印 status, 不打印 key/url) +
    `app/schemas/errors.py` 新增 7 个 MODEL_* 稳定错误码
  - 修复 Phase 1 缺陷: `guard.list_files` 返回 base-relative `relativePath` 导致 browse-token (从 ROOT 签发) 二级目录导航解析错路径; 改为 `entry.relative_to(root)` 根相对路径 (2 个失败测试先写后转绿)
  - 前端: `types/agent.ts` 新增 Provider* 类型; `services/provider.service.ts` (mock+http 双实现, 按 isApiMode 切换); `views/SettingsView.vue` 模型页新增「Provider 健康状态」只读卡片 (状态/能力/安全, 不暴露 key/baseUrl); 对应测试
  - WP5 健康卡片微调 (2026-07-31): 补全 maxInputBytes(格式化 KB/MB)/maxOutputTokens/followRedirects/trustEnvProxies 字段; 新增「数据源: 后端 API/前端 Mock」标识与「刷新」按钮 (spinner); SettingsView 测试增 2 例 (全字段渲染 + 刷新调用次数)
  - 演示验证 (2026-07-31): 后端以 LIGHTCODE_MODEL_ENABLED=true + https base_url + 放行 origin 启动, `/api/v1/provider/health` 返回 ready 且字段完整、无 key/baseUrl; 前端 VITE_LIGHTCODE_RUNTIME=api 经 vite 代理拉取一致数据; 全链路跑通
  - 验证: 后端 pytest 165 passed / 2 skipped (基线 117+2, WP5 增 48: config 19 + http 17 + health 10 + guard 2); 前端 vitest 69 passed (基线 64, WP5 增 5), vue-tsc -b + vite build --emptyOutDir false 通过
- LangChain 改造 (2026-07-31, 用户指令: 优先用成熟企业级库而非自研): 新增 `app/services/llm_client.py` (ChatOpenAI 工厂 + 加固 httpx(trust_env=False/follow_redirects=False/max_retries=0/显式超时) + 错误码映射 MODEL_*); `openai_compatible_provider.py` 改为委托该工厂 (保留 chat() 语义/预算计数/稳定错误码, 畸形响应归入 MODEL_RESPONSE_INVALID); WP5 http 17 + config 19 + health 10 全绿, 全量 165 passed/2 skipped 无回归。
- WP6 (受限模型编排与候选 ChangeSet) 已完成 (2026-07-31): 默认无 schema 变更, 复用 tasks/changesets/task_events。新增 `app/services/model_orchestrator.py` (LangGraph StateGraph: call_model→adjudicate_tool→adjudicate_intent→END; 复用共享 llm_client 工厂 + OpenAICompatibleProvider; browse_tokens.verify 校验 fileToken; Guard 只读读取; changeset.build_model_change_set 生成不可变 ChangeSet 并持久化; 预算/轮次双重约束; fail-closed)。新增 `app/schemas/model_contracts.py` WP6 DTO (EditOp/ToolRequestMessage/CandidateEditIntent/ModelTaskCreateRequest/ModelTaskResponse, extra="forbid", 无 rootPath); `errors.py` 增 MODEL_EDIT_INVALID; `changeset.py` 增 WP6 精确唯一文本替换变换。路由: POST/GET `/api/v1/model-tasks`; `phase1.submit_approval/get_real_task/recover_incomplete_tasks` 的 kind 过滤扩展为 `('real','model')`, 模型任务复用 Phase 1 版本绑定审批 + 原子写 + 内建验证 (已测: 审批后磁盘文件真实变更)。验证: 新增 `tests/test_model_orchestrator.py` 12 例全绿 (read→candidate→awaiting_approval 且编排期不写盘; fail-closed: 伪造 token/MODEL_EDIT_INVALID、错误 baseSha256/STALE_BASE、超轮次/MODEL_BUDGET_EXCEEDED、畸形输出/MODEL_RESPONSE_INVALID、 forbidden 字段、未授权工具; 代码围栏解析; API 默认关闭/MODEL_DISABLED、API happy path、extra=forbid 拒绝 rootPath); 全量后端 177 passed / 2 skipped 无回归。前端模型任务创建 UI 已完成 (见上方"WP6 前端"): RealWorkspaceView "创建模型任务"面板 + store.createModelTask + model-task.service 双实现 (POST /api/v1/model-tasks 仅 workspaceId+title, 经 parseModelTask 校验, 拒绝含 rootPath 的畸形 DTO) + 3 个测试文件 17 例全绿; 复用既有 real-task 任务视图显示模型任务。
- 依赖策略 (2026-07-31, 用户指令): WP6 起优先用 LangChain/LangGraph 辅助实现（尤其编排层 / 工具协议），但须保持 fail-closed、默认关闭、零密钥泄露等不变量；依赖加锁版本、隔离到编排层，不得进入前端或凭据路径；WP5 自研最小 httpx 客户端保留（不为 80 行换重型依赖）。
```

## 问题修复记录

- 2026-07-24: Phase 1 (仅后端) 实现。新增 `app/workspaces/registry.py` (静态注册表, 从 `LIGHTCODE_WORKSPACES_CONFIG` 或 `backend/workspaces.json` 加载, 配置含 `rootPath`+`targetFile`, 已 gitignore)、`app/security/fs.py` + `guard.py` (WorkspaceGuard 统一路径守卫)、`app/schemas/errors.py` (稳定错误码)、`app/services/changeset.py` (确定性 append-marker 变换)、`app/services/atomic_write.py` (临时文件 + `os.replace` 原子替换 + 内建 UTF-8/哈希验证 + 每文件锁)、`app/services/phase1.py` (真实任务生命周期 + 6 步审批写入协议)。DB 迁移: `tasks` 增列 `kind`/`target_file`/`changeset_id`/`verification_detail` (旧 Mock 任务默认 `kind='mock'`), 新增 `changesets`/`approvals` 表 (含 `base_text`/`proposed_text` 以保证精确原子写)。新增端点 `/registered-workspaces*`、`/real-tasks*`。真实任务事件复用既有 `task_events` + SSE 端点。
- 2026-07-24: 修复 `guard.read_text` 默认通用换行转换 (CRLF->LF) 导致 `baseSha256` 与磁盘原始字节哈希不一致、可能误判 STALE_BASE 或静默改写行尾。改为 `read_text(newline="")` 保留原始换行。
- 2026-07-24: 修复 SQLite 默认路径为相对路径导致从 backend/ 启动落到 backend/backend/data/lightcode.db 且被 Git 跟踪。`main.py` lifespan 与 `database.py` 无参回退均改为基于文件位置的绝对路径 (`<repo>/backend/data/lightcode.db`)；env 覆盖 `LIGHTCODE_DATABASE_PATH` 的相对路径解析到 backend/ 目录。已从 Git 索引移除该 DB 并在 `.gitignore` 忽略 `backend/data/*.db` 与 `backend/backend/data/*.db`。
- 2026-07-24: 重写 backend README，补充 Phase 0.5 启动方式、`LIGHTCODE_DATABASE_PATH` 临时数据库用法与 Mock Runtime 边界。
- 2026-07-23: 修复历史任务 `detail_json` 空对象导致的 Pydantic ValidationError。`get_task_detail()` 改为合并行字段与 `detail_json` 额外字段；为 8 条历史任务填充 plan、toolCalls、files、approval、test 及失败/取消字段。
- 2026-07-23: SSE 接入 `agent.store.ts`。API 模式下监听 `changeset.approved`、`verification.started`、`verification.completed`；切换工作区或组件卸载时关闭 EventSource。
- 2026-07-23: 配置 Vite 代理：`server.proxy['/api'] -> http://127.0.0.1:8000`。
- 2026-07-27: 模块 0（高危缺陷修复）。`security/guard.py::_resolve_under` 修正 symlink/junction 检查顺序——原实现先 `resolve()` 再对**已解析路径**调 `is_link_or_reparse`，链接被跟随因而检查失效；改为在 `resolve()` 之前逐父段（含工作区根）检查 reparse point。`services/runtime.py::approve_changeset` 增加 `kind != 'mock'` 显式过滤，真实任务经 legacy Mock 审批端点返回 405。新增 monkeypatch 逻辑级测试覆盖中间段/父目录/根链接三种绕过场景（沙箱 `os.symlink` 静默降级，真实文件系统用例改为不可检测时 skip）。
- 2026-07-27: 模块 1（契约能力补全）。`changesets` 增 `expires_at` 列，`create_real_task` 按 `CHANGESET_TTL_SECONDS`（策略常量，默认 3600s）写入，`submit_approval` 过期返回 `CHANGESET_EXPIRED` 且不写文件。新建 `security/policy.py` 为唯一策略来源（迁入 `MAX_FILE_BYTES`/`SECRET_GLOB`，新增 `ALLOWED_EXTENSIONS` 扩展名白名单 + `MAX_DIFF_LINES` + `is_allowed_extension()`）；`guard.py` 加扩展名拒绝与 `search_files` 大小/扩展名跳过；`phase1.py` 校验 diff 行数超限。`phase1.py::recover_incomplete_tasks()` 启动扫描 `applying_change` 真实任务并按当前文件哈希判定 completed/reset/unknown（`APPLY_OUTCOME_UNKNOWN` 阻断自动续写），`main.py` lifespan 调用。`runtime.py` + `routes.py` 升级 SSE 支持 `?after_sequence=` + `Last-Event-ID` 续传 + `tail` 轮询，每帧带 `id:`；新增 `/real-tasks/{id}/events`。
- 2026-07-27: 模块 2（配置与文档对齐）。新增 `backend/workspaces.example.json` 模板（机器特定 `rootPath` 由使用者复制为 `workspaces.json` 后填真实绝对路径，后者已被 .gitignore 忽略）；`db/database.py::initialize_database` 启用 WAL + `busy_timeout=5000` 提升并发读与降低写锁竞态。WP1 简化偏差（无迁移目录、无 `apply_attempts` 表）明文记录于"Phase 1 计划偏差与决策"小节。
- 2026-07-27: 模块 3（前端 Phase 1 真实闭环 T8）。类型层 `types/agent.ts` 新增 RealTask/RealChangeSet/RegisteredWorkspace/RegisteredFileEntry/WorkspaceSearchHit/ApprovalInput 等，与 `backend/app/schemas/contracts.py` 严格对齐（无 rootPath）。新建 `services/registered-workspace.service.ts` 与 `services/real-task.service.ts`（mock+http 双实现按 `isApiMode` 切换）；`event.service.ts` 增 `subscribeRealTaskEvents`（`after_sequence`/`tail`/`Last-Event-ID` 续传）。新建 `stores/real.store.ts`（idempotencyKey 用 `crypto.randomUUID()`，事件按 sequence 去重）。新建视图 RealWorkspaceListView/RealWorkspaceView/RealTaskView 与路由 `/real`、`/real/:id`、`/real/:id/task/:taskId`；主页加"真实工作区"入口。修复两处存量缺陷：AgentWorkspaceView 拒绝按钮缺失 `@click`（补 `rejectCurrentChangeSet` action + 已拒绝态 UI）；SettingsView 运行时模式硬编码 Mock 改按 `isApiMode` 动态显示。新增/扩充 5 个测试文件（服务契约断言、RealViews 10 用例）。环境注意：vite build 清空 dist 会被 OneDrive 文件锁中断，用 `--emptyOutDir false` 规避。
- 2026-07-30 (Phase 1R M3, WP3+WP4): 后端新建 `app/services/browse_tokens.py`（HMAC-SHA256 签名、TTL 默认 30s、绑定 `(workspace_id, operation, relative_path)` 不透明令牌，fail-closed 拒绝畸形/签名不符/workspace 不符/operation 不符/过期），`app/services/event_service.py`（SSE_REPLAY_CAP=1000 / TAIL_TIMEOUT=30 / HEARTBEAT=10 / POLL=0.5 / MAX_CONNECTIONS=50，连接计数 + 重放/心跳/错误帧生成）。`schemas/contracts.py` 增 `BrowseFileEntry/BrowseFileContent/BrowseSearchHit`（含 token）；`schemas/errors.py` 增 `BROWSE_TOKEN_INVALID/EXPIRED`；`api/routes.py` 移除内联 SSE 逻辑改用 `stream_events`，文件树/读/搜全面 token 化（secret/link 条目发空 token 可见不可开）。测试新增 `test_browse_tokens.py`、`test_event_service.py`、`test_api_mode_e2e.py`；改写 browse/negative/safety 用例为 token 模型。前端：`types/agent.ts` + fixture 增 `token`；`registered-workspace.service.ts` 改收 `nodeToken`/`fileToken`，`real.store.ts` 用面包屑 token 栈取代自由路径；新增 `contracts/real-task.schema.ts`（运行时 DTO 校验，拒绝 rootPath/未知 state）+ 测试；`http.ts` 增 `requestJsonValidated`；`event.service.ts` 接 `parseTaskEvent` 与 `stream.error`；`SettingsView` 修正为"无外部命令/仅内建验证"。后端 117 passed/2 skipped，前端 64 passed/64，vue-tsc -b + vite build (--emptyOutDir false) 通过。
- 2026-07-23: 修复 `uvicorn app.main:app` 的同名 `app` 包解析冲突；`main.py` 顶部将本地 `backend/` 插入 `sys.path` 首位。

## Phase 1 计划偏差与决策

以下决策偏离原始 Phase 1 计划（WP1 工作包）但经评估对 MVP 安全等价或更强，明文记录以避免后续误判为遗漏：

- **不使用独立迁移目录**：原 WP1 计划设想版本化 migration 目录。实际采用 `db/database.py` 内联 `SCHEMA_SQL` + 幂等 `run_migrations`（`ALTER TABLE ADD COLUMN ... DEFAULT`）回补旧库列。`changesets` 的 `expires_at` 列已在 `run_migrations` 中按目标表检查，避免重复加列报 `duplicate column`。理由：MVP 阶段 schema 演进可控，内联方案确定性更强、无需 Alembic 类外部依赖。
- **不实现 `apply_attempts` 独立表**：原 WP1 计划设想独立的尝试计数表。实际幂等性与重试边界由 `approvals` 表的 `UNIQUE(idempotency_key)` 约束 + 6 步审批协议的 `revision`/`diffHash` 绑定共同保证；每次审批尝试已落 `approvals` 行（含 `decision`/`outcome`/`detail`），无需另计数表。理由：现有结构已覆盖"重复提交不重复写"与"失败可查"，独立计数表在 MVP 规模下不增加安全价值。
- **WAL + busy_timeout**：`initialize_database` 连接后立即 `PRAGMA journal_mode=WAL` 与 `PRAGMA busy_timeout=5000`，属对 schema/迁移语义透明的引擎级调优，不进计划原稿但作为显式决策记录。

## 安全

未来运行时必须执行工作区隔离、显式差异审批、命令策略和密钥脱敏。Phase 0.5 不得伪造文件系统访问或安全声明；Phase 1 的真实文件能力必须严格遵守 `docs/phase1-safety-contract.md`。
