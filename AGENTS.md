# LightCode 开发规则

## 项目目标

LightCode 是一个独立实现的、本地优先的可视化编码智能体，面向有基础编程经验的开发者。它不是 MiniCode-Python 或其他编码智能体项目的分支、重写或源码延续。

## 当前阶段

项目处于核心 Agent 更新阶段（阶段 A/B）：单一主工作区 + 安全聊天闭环 + 多供应商设置页。Mock Runtime 与 Mock 前端已移除；产品入口只有一个基于已注册真实工作区的聊天式 Agent 主界面；Provider 可在设置页按多供应商配置管理（列表/搜索/添加/测试并添加/删除，开发期为后端进程内存凭据，Electron 阶段替换为系统密钥库）；聊天会话持久化到 SQLite；模型通过受控检索（`read_file`/`search_files`）回答自由问答或生成单文件候选 ChangeSet，写入仍走显式审批与原子替换。

- 冻结范围、安全不变量、状态机、审批写入协议与错误码以 `docs/phase1-safety-contract.md` 为准；模型 Provider、凭据存储与聊天编排以 `docs/phase2-model-provider-design.md` 与 `docs/architecture/lightcode-local-first-agent-design.md` 为准。
- 真实工作区根路径只来自服务端静态注册表（`LIGHTCODE_WORKSPACES_CONFIG` 或 `backend/workspaces.json`，已 gitignore）；公共 DTO、SSE、日志、错误一律不得返回真实根路径。
- 每次文件访问必须经 `WorkspaceGuard`。ChangeSet 由服务端生成、持久化、版本化；审批绑定 `changeSetId + revision + diffHash`；写前重检基线哈希，冲突返回 `STALE_BASE`；单文件临时文件 + 原子替换 + 内建 UTF-8/哈希验证。
- 浏览器只提交 `workspaceId`、任务标识、会话标识、用户消息、审批决定、`changeSetId`、`revision`、`diffHash`、`idempotencyKey`（Pydantic `extra="forbid"` 拒绝任何 `rootPath`/`filePath`/patch/command/key/baseUrl）。模型任务同样只提交 `workspaceId`+`title`，绝不提交 key/baseUrl/路径/补丁。
- 后端 API 必须保持 `/api/v1` 与 camelCase JSON。
- Provider 凭据仅经本机 FastAPI 设置端点接收，送入可替换的 `ProviderCredentialStore`（开发期内存实现不落盘；Electron 阶段替换为 OS Keychain 适配器）。健康、事件、日志与 API 响应继续执行 secret/location 脱敏，禁止完整 Base URL、key、header、路径与原始上游响应；测试连接限制在配置 allowlist 的 HTTPS origin，`trust_env=False`、`follow_redirects=False`、显式超时、零重试。
- 模型只能"提议"：自由问答直接回答，编辑任务进入计划、受控检索、服务端独立生成的候选 ChangeSet 与显式审批；模型不写文件、不执行命令、不决定审批、不接收根路径或自由文件路径。仍不得实现：Shell/subprocess/包管理/网络下载/Git 写操作、删除/新建/重命名/移动、多文件事务、二进制/非 UTF-8/超限文件修改、Electron、本地文件夹选择、前端密钥持久化（阶段 B 完整文件操作需要先建立新的安全契约与崩溃恢复协议）。

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
frontend/       Vue 应用（HTTP/SSE 服务适配器，无 Mock 分支）
backend/        FastAPI + SQLite：真实工作区安全变更闭环、模型提议、聊天闭环、Provider 运行期设置
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

### 核心 Agent 更新（阶段 A）已交付范围

- FastAPI 是工作区访问、模型出网、审批与写入的唯一边界；不再存在 Mock Runtime 或浏览器提交路径。
- Provider 配置：设置页可编辑（Provider/Base URL/API Key/Model ID），显式"测试并保存"；凭据只进后端进程内存（`InMemoryProviderCredentialStore`），绝不进 SQLite、前端持久化、日志、SSE 或仓库；重启后内存凭据丢失，回落为环境变量配置或 unconfigured。
- 聊天会话与消息持久化到 SQLite（`chat_sessions`/`chat_messages`）；消息不保存 API Key、完整 Provider URL、原始异常诊断或不受控隐私数据。
- 模型检索：`read_file` + `search_files`，均由 WorkspaceGuard、browse token、文件大小/扩展名/敏感路径策略与预算约束；模型上下文不含根路径或自由文件路径。
- 自由问答不生成 ChangeSet；编辑任务复用 `kind='model'` 任务 + 版本绑定审批 + 原子写入 + 内建验证。

### Phase 1 实施前置规则

- 实施前必须先阅读 `docs/phase1-safety-contract.md` 与 `docs/workspace-registration.md`，再更新代码或 API 合约。
- 真实工作区根路径仅来自服务端启动静态配置；浏览器只能提交 `workspaceId`，不能提交本地路径、文件路径、补丁、文件内容或命令。
- Phase 1 仅允许受控只读工具、服务端确定性 ChangeSet、显式版本绑定审批、单个既有 UTF-8 文本文件的原子替换和内建完整性验证。
- 阶段 A 继续禁止：真实模型直接写文件、Electron、Shell/外部命令、依赖安装、网络下载、Git 写操作、删除/新建/重命名/移动、多文件事务与前端密钥持久化。

### Phase 3 桌面端边界契约（进行中）

阶段 3 以 Windows Electron 桌面交付为目标，是一次性围绕既有安全闭环加壳，不重写已通过验证的 FastAPI/SQLite/Vue 逻辑。设计以 `docs/superpowers/specs/2026-08-13-phase-3-windows-desktop-design.md` 与实施计划 `docs/superpowers/plans/2026-08-13-phase-3-windows-desktop-delivery.md` 为准。

- **Electron 不含写入权**：Vue 渲染进程保持沙箱（`contextIsolation` + `sandbox`，禁用 `nodeIntegration`），没有任意 `fs`/`child_process`/原生路径能力；原生目录选择由 Electron 主进程触发，渲染进程只收到安全 DTO。
- **FastAPI 仍是唯一权威**：文件访问、模型出网、目录注册校验、ChangeSet、审批与写入只在后端；sidecar 只监听 `127.0.0.1` 随机回环端口，桌面注册请求需每次启动生成的一次性令牌校验。
- **路径不落外界**：绝对根路径只存在于后端私有实体与进程间可信通道；公共 DTO、SSE、日志、错误、截图与前端状态一律不得包含真实绝对路径。
- **用户数据在安装目录之外**：SQLite、技能包、工作区注册元数据与日志放 Windows 用户数据目录；安装程序只替换不可变程序资源，升级不得删除用户数据。
- **动态注册工作区**：桌面注册不要求 `targetFile`；新目录经 canonical/reparse 校验后进入系统，模型后续通过 `search_files`/`read_file` 决定单个既有 UTF-8 文本文件的候选编辑，仍走显式审批与原子写入。
- **凭据持久化**：Provider API Key 在桌面模式经 Windows Credential Manager 适配器保存（`ProviderCredentialStore` 协议不变），绝不进 SQLite、日志、前端或安装资源。
- 仍不得实现：外部命令/Shell/包管理/网络下载/Git 写操作、删除/新建/重命名/移动、多文件事务、自动审批、自动更新与公开发布签名（先内部测试）。

## 验证

- 每个任务完成后运行对应的后端或前端聚焦测试；所有任务结束后运行后端全量测试、前端全量测试和前端构建。
- 没有当前的测试/构建证据，不得声称页面或运行时功能已完成。
- 不得为了通过验证而引入 `skip`、假成功状态、禁用失败的检查或绕过手段。

## 状态追踪

```text
Skill 管理（上传识别/详情/启用/删除/Agent 门禁）: 完成 (2026-08-12) —— 共享侧边栏新增「技能」入口 + `/workspace/:workspaceId/skills` 管理视图（规格: docs/superpowers/specs/2026-08-12-skill-management-design.md）
  - 后端: `skills` 表（source/status CHECK + uploaded 名称唯一索引, 内联幂等迁移）+ config/skills.py（backend/data/skills/ 默认目录 + ZIP/文档预算常量, LIGHTCODE_SKILLS_PATH 覆盖）+ skill_package.py（纯标准库 ZIP 中央目录校验: 加密/软链/路径穿越/敏感名/后缀/深度/预算全 fail-closed, 只提取 package.zip + SKILL.md）+ skill_service.py（临时目录校验->SQLite 事务->原子替换, 文档读前重检 SHA-256, 删除仅 uploaded 且路径证明在 root 下, 内置删除拒绝）+ 5 个 REST 端点 + 14 个 SKILL_* 稳定错误码
  - Agent 门禁: ChatService/ModelOrchestrator 构建上下文时经 list_enabled_for_agent() 只读投影（id/name/summary/文档/哈希）, format_enabled_skills_for_model 以 <untrusted-skills> 边界标记嵌入, 不持久化进消息/事件/日志; 上传默认 disabled, 禁用/删除后下一次请求即排除
  - 前端: skills.service.ts（multipart 仅 package 字段, 不手设 Content-Type）+ skill.schema.ts 运行时契约校验（拒绝 storagePath/rootPath/未知状态/畸形 id）+ skills.store.ts（本地筛选/上传/乐观状态回滚/删除, 固定中文错误码映射）+ SkillDetailOverlay.vue（Teleport role=dialog, 纯文本 <pre> 渲染 SKILL.md, 无内部侧栏, 页脚内联删除确认, 焦点管理 + reduced-motion）+ SkillsView.vue（行式列表/搜索/来源筛选/上传按钮, 行点击开详情, 开关 stopPropagation）
  - AppSidebar 仅追加技能按钮（data-testid=nav-btn-skills, 位于会话之后）, 原按钮/图标/顺序/折叠语义零改动; SettingsOverlay 未被修改
  - .gitignore 新增 backend/data/skills/; python-multipart>=0.0.20 加入 backend 运行时依赖
  - 验证: 后端全量 280 passed / 2 skipped（技能聚焦 48）; 前端全量 133 passed / 17 files（技能新增 6+8+8+7+2 例）; vue-tsc -b + vite build --emptyOutDir false 通过; 真实服务器 HTTP 冒烟 10/10（上传 disabled->启用->删除 404->未知状态 422, 无路径泄露）; 浏览器 Playwright 验收按用户选择跳过
工作区设置层（Settings Overlay）: 完成 (2026-08-11) —— 工作区侧边栏设置按钮不再跳转 `/settings`，改为在当前工作区上方打开设置层（规格: docs/superpowers/specs/2026-08-11-settings-overlay-design.md）
  - 新增 SettingsOverlay.vue: Teleport 到 body 的模态层容器（role=dialog/aria-modal/aria-labelledby + 78vw×76vh 暖纸面板 + 暖灰遮罩 + Esc/遮罩点击/关闭按钮关闭 + 打开焦点进面板、关闭归还触发按钮 + prefers-reduced-motion 取消过渡）；不承载 Provider 业务状态
  - 新增 SettingsContent.vue: 从 SettingsView 提取全部设置业务（分类/列表/搜索/详情/添加弹层/刷新/清除），独立路由页与设置层共用；showBack 控制独立页「← 返回」入口
  - AppSidebar 设置按钮改 emit openSettings（位置/SVG/data-testid/样式不变）；WorkspaceView 持 settingsOverlayOpen 状态渲染设置层（关闭不路由、不刷新、不重建会话），provider-hint「设置」链接同步改为打开设置层；SettingsView 变薄壳复用 SettingsContent；`/settings` 路由与深链保留
  - AddProviderModal 的 Esc 监听改 capture 阶段 + stopPropagation（弹层打开时 Esc 只关弹层不关设置层）
  - 验证: 前端全量 102 passed / 13 files（新增 6 个设置层用例）; vue-tsc -b + vite build --emptyOutDir false 通过; 后端全量 226 passed / 2 skipped 无回归
多供应商设置页（阶段 A/B）: 完成 (2026-08-07) —— `/settings` 重构为暖纸多供应商配置中心
  - 阶段 A（前端）: AppSidebar 从 WorkspaceView 抽取为共享侧边栏 + SettingsNav/ProviderList/ProviderDetail/AddProviderModal 四组件
    + 设置分类仅「模型与供应商」「关于」+ 供应商列表可搜索 + 右侧安全摘要 + 暖纸添加弹层
  - 阶段 B（后端）: ProviderCredentialStore 扩展为多配置 dict（get() 保持激活配置语义, ChatService/ModelOrchestrator 零改动）
    + ProviderProfile/ProviderProfileCreate/ProviderProfileDeleteResponse DTO（extra=forbid, 无 key/完整 baseUrl）
    + /provider/profiles GET 列表 / POST 创建（连接测试通过才保存, fail-closed）/ GET/DELETE by id; 未保存时回落 env 派生 default
  - 验证: 后端全量 226 passed / 2 skipped; 前端 96 passed / 13 files; vue-tsc -b + vite build --emptyOutDir false 通过
核心 Agent 更新（阶段 A）: 完成 (2026-08-04) —— 单一主工作区 + 聊天闭环 + Provider 运行期设置 + 受控检索
  - Mock Runtime/页面/服务/fixture/种子数据已移除；前端 HTTP-only 化（删除 isApiMode 分支）
  - ProviderCredentialStore（开发期进程内存，Electron 阶段换 OS Keychain）+ 设置 API（GET/测试/测试并保存/清除）
  - chat_sessions/chat_messages + tasks.chat_session_id 迁移；ChatService + ChatOrchestrator（LangGraph answer/tool/intent）
  - 模型检索扩展 read_file + search_files（受控 query/命中/snippet；模型上下文无路径）
  - 验证: 后端全量 202 passed / 2 skipped; 前端 69 passed / 13 files; vue-tsc -b + vite build --emptyOutDir false 通过
前端: 69 测试通过 (13 文件), vue-tsc -b + vite build 通过 (2026-08-04)
Phase 2 审查修复 (2026-08-04): 完成 —— H-01 未知编排异常不再泄露（固定错误投影, 不入 SQLite/API/SSE/UI）+ 模型上下文移除逻辑路径（仅 fileToken/哈希/受控文本）; M-01 真实任务 SSE 持续订阅 tail=true + stream.end 置 closed; M-02 Provider ready-only 新建模型任务门禁（disabled/unconfigured/degraded/未知均禁用, 保留历史/审批）; M-03 失败 UI 错误码→固定中文文案映射（不渲染服务端自由 message）; M-04 health 能力收紧为 read_file（与编排器一致）; M-05 输出 token 预算本地强制（含 usage 缺失的保守字节上限, MODEL_BUDGET_EXCEEDED）; M-06 任务详情路由工作区归属校验（错配清理并跳转真实归属）; L-01 SSE 连接上限加锁原子化（check+increment 同一临界区）。验证: 后端全量 195 passed / 2 skipped, 前端 94 passed / 18 文件, vue-tsc -b + vite build --emptyOutDir false 通过
WP6 前端: 完成 (2026-07-31) —— 新增模型任务创建入口与 UI（RealWorkspaceView 侧栏"创建模型任务"面板 + store.createModelTask + model-task.service 双实现 + parseModelTask 契约校验 + 3 个测试文件 17 例）；复用既有 real-task 任务视图显示模型任务（get_real_task 含 kind='model'）；vite build --emptyOutDir false 通过
WP7 (模型任务 SSE / 前端状态机 / 开发体验): 完成 (2026-08-03) —— 纯前端，无后端改动（复用 WP6 LangGraph 编排 emit 的事件 + WP3 SSE 续传通道）。新增：types/agent.ts 模型生命周期类型(ModelLifecycleStep/ModelLifecycleStage/EventConnection) + MODEL_TASK_EVENT_TYPES；contracts/real-task.schema.ts 新增 parseModelLifecycleEvent（模型事件 payload 防御性校验）；real.store.ts 新增 eventConnection 状态机(connecting/open/reconnecting/closed) + SSE sequence 缺口全量同步(_resync，带 _resyncing 防重入) + modelLifecycle getter（从事件派生有序阶段，最远到达阶段为 current，失败标记 failed）；RealWorkspaceView 强化启动前数据披露(代码片段发往已配置 Provider) + Provider degraded 门禁新建(保留历史/查看/审批)；RealTaskView 增加 kind 徽标 + 模型生命周期时间线 + awaiting_approval 策略版本与"不执行外部命令"说明 + SSE 连接态 + 失败可行动无敏感提示(精确正则拒绝 sk-+20位密钥)；phase1.fixture.ts 新增 modelTaskFixture/modelTaskEventsFixture；real-task.service mock 支持模型任务 id。验证：新增 real.store.test.ts 5 例 + RealTaskView.test.ts 6 例（共 11 例 WP7），前端全量 87 passed / 17 文件，vue-tsc -b + vite build 通过，无回归
后端: 195 测试通过 + 2 skipped (沙箱 symlink 静默降级, 逻辑已由 monkeypatch 测试覆盖) (2026-08-04)
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
- WP8 (性能、可观测性与发布门禁, M6) 已完成 (2026-08-03), **零新增第三方依赖**（stdlib logging + 进程内 Metrics + 既有 pytest/vitest；用户确认不引入 pytest-cov/eslint/prettier/coverage）:
  - 新增 `app/services/observability.py`（单一日志/指标出口）：JSON 格式器 + `correlation_id_var: ContextVar` 关联 ID + `CorrelationFilter`；`redact(obj)` 递归脱敏（secret/location 键 + `sk-`/`Bearer` 形状）；`Metrics` 进程单例（仅聚合数值：任务转换/工具调用/provider 调用/token/预算/并发/SSE/SQLite busy，不含 prompt/response/key/路径）；`configure_logging()` 由 `LIGHTCODE_LOG_LEVEL` 控制（默认 WARNING），并把 `httpx`/`httpcore`/`openai`/`langchain*` 压到 WARNING 阻断第三方 INFO 打印完整请求 URL（含 base URL）的泄露路径。
  - `app/main.py`：lifespan 首行 `configure_logging()`，启动只打印 provider `status`（非 key/url）；新增关联 ID 中间件（线程池同步路由经 `request.state.correlation_id` 重绑）。
  - `app/schemas/errors.py` 增 `MODEL_CONCURRENCY_EXCEEDED`；`app/services/model_orchestrator.py` 增进程内 `_ModelTaskGate`（Phase 1 写租约的 Phase 2 类比，并发 1，无 schema 变更），满闸任务置 `failed` 落 `MODEL_CONCURRENCY_EXCEEDED` 事件；编排器埋点状态转换/工具耗时/候选 diff 生成。
  - `app/services/openai_compatible_provider.py` `chat()`：try/except 内统一记录 `Metrics.provider_call(provider, model, http_category, latency, tokens)` 后重抛；预算超限计入 `MODEL_BUDGET_EXCEEDED`；新增 `_classify_error`（MODEL_*→timeout/rate_limit/upstream/invalid/budget/disabled/error）与 `_extract_tokens`（安全取 token_usage）。
  - `app/services/event_service.py` 连接开/关计 `Metrics.sse_open/close`；`app/api/routes.py` 续传计 `Metrics.sse_resume` 且同步路由首行重绑关联 ID；`app/db/database.py` 新增 `InstrumentedConnection`（拦截 execute/executemany 的 locked/busy→`Metrics.sqlite_busy()`，保留 busy_timeout/WAL/上下文协议，无 schema 变更）。
  - 新增 `tests/test_observability.py`（9 例：redact 拒绝名单/指标无密钥/SSE/并发闸/SQLite busy 仪表化/provider 错误分类）与 `tests/test_model_e2e.py`（4 例 API-mode E2E：happy path→审批→原子写→SSE 续传、恶意工具请求失败、预算耗尽、SSE 续传指标；并断言日志与事件载荷不含 test-key/api.example.test/Bearer/Authorization/真实临时路径）。
  - 验证: 后端全量 **190 passed / 2 skipped**（含 WP8 新增 13）；WP8 聚焦 13/13 通过；前端 WP8 无代码变更，既有 87 测试 + vue-tsc -b + vite build 仍有效。设计文档见 `docs/phase2-model-provider-design.md`，架构 M6 状态见 `docs/architecture/lightcode-local-first-agent-design.md`。
```

## 问题修复记录

- 2026-08-04: Phase 2 审查修复（修复细节与验证见 `docs/phase2-model-provider-design.md` §2/§3.6/§4）。
  - H-01: `model_orchestrator.py` 未知 `Exception` 不再插值 `str(exc)`（固定 `_INTERNAL_ORCHESTRATION_FAILURE`），异常原文不再进入 SQLite/API/SSE/前端；`_build_system_prompt` 移除 `target_file` 逻辑名、read 工具结果移除 `relativePath`，发往 Provider 的上下文仅含 fileToken/baseSha256/受控文本。
  - M-05: `openai_compatible_provider.py` 新增 `_check_output_budget`，响应后本地强制输出预算（completion_tokens 超限或 usage 缺失时按 `max_output_tokens*4` UTF-8 字节保守上限 → `MODEL_BUDGET_EXCEEDED`）。
  - M-04: `model_provider.py` 的 `MODEL_ALLOWED_TOOLS` 收紧为 `("read_file",)`，health 声明与实际编排能力一致。
  - L-01: `event_service.py` 新增 `_connection_lock`，SSE 连接上限的检查/递增/递减与 Metrics 连接计数在同一临界区（跨线程原子）。
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
