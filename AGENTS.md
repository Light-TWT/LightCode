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
前端: 60 测试通过 (12 文件), vue-tsc -b + vite build 通过 (2026-07-27)
后端: 94 测试通过 + 2 skipped (沙箱 symlink 静默降级, 逻辑已由 monkeypatch 测试覆盖) (2026-07-27)
Phase 0.5 收尾: DB 路径绝对化 + Git 跟踪移除已完成; API 模式持久化验证通过 (临时 DB 审批持久化, 新库回到 awaiting_approval)
Phase 1 后端: T1-T7 + T9 完成; API 模式 HTTP 全闭环验证 16/16 通过
  (注册工作区无根路径泄露 -> 创建真实任务 awaiting_approval -> 审批原子写 + 内建验证 completed
   -> 磁盘文件确实变更且基线保留 -> 幂等重放不重复写 -> 重启持久化 completed
   -> 新库回到 awaiting_approval -> STALE_BASE 失败且外部改动保留)
Phase 1 前端 (T8): 完成; 8 个 Phase 1 端点全部有对应 UI
  (/real 注册工作区列表 -> /real/:id 文件树/预览/搜索/建任务 -> /real/:id/task/:taskId 计划/diff/审批/SSE)
  服务层 mock+http 双实现按 VITE_LIGHTCODE_RUNTIME 切换; 审批请求体测试断言严格等于 extra=forbid 契约; 响应无 rootPath
  端到端演示验证通过 (registered-workspaces 代理连通, 审批后磁盘文件真实变更)
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
- 2026-07-23: 修复 `uvicorn app.main:app` 的同名 `app` 包解析冲突；`main.py` 顶部将本地 `backend/` 插入 `sys.path` 首位。

## Phase 1 计划偏差与决策

以下决策偏离原始 Phase 1 计划（WP1 工作包）但经评估对 MVP 安全等价或更强，明文记录以避免后续误判为遗漏：

- **不使用独立迁移目录**：原 WP1 计划设想版本化 migration 目录。实际采用 `db/database.py` 内联 `SCHEMA_SQL` + 幂等 `run_migrations`（`ALTER TABLE ADD COLUMN ... DEFAULT`）回补旧库列。`changesets` 的 `expires_at` 列已在 `run_migrations` 中按目标表检查，避免重复加列报 `duplicate column`。理由：MVP 阶段 schema 演进可控，内联方案确定性更强、无需 Alembic 类外部依赖。
- **不实现 `apply_attempts` 独立表**：原 WP1 计划设想独立的尝试计数表。实际幂等性与重试边界由 `approvals` 表的 `UNIQUE(idempotency_key)` 约束 + 6 步审批协议的 `revision`/`diffHash` 绑定共同保证；每次审批尝试已落 `approvals` 行（含 `decision`/`outcome`/`detail`），无需另计数表。理由：现有结构已覆盖"重复提交不重复写"与"失败可查"，独立计数表在 MVP 规模下不增加安全价值。
- **WAL + busy_timeout**：`initialize_database` 连接后立即 `PRAGMA journal_mode=WAL` 与 `PRAGMA busy_timeout=5000`，属对 schema/迁移语义透明的引擎级调优，不进计划原稿但作为显式决策记录。

## 安全

未来运行时必须执行工作区隔离、显式差异审批、命令策略和密钥脱敏。Phase 0.5 不得伪造文件系统访问或安全声明；Phase 1 的真实文件能力必须严格遵守 `docs/phase1-safety-contract.md`。
