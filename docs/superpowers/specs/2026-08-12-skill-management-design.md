# LightCode Skill 管理设计规格

**状态：** 已确认，待实施  
**日期：** 2026-08-12  
**范围：** Skill 列表、ZIP 上传与安全识别、详情文档模态层、启用状态、删除与 Agent 使用门禁。

## 1. 目标与范围

为工作区主界面的共享左侧栏新增“技能”入口，提供本机已安装 Skill 的可浏览、上传、识别、查看、启用、禁用与删除能力。

首期支持上传单个 `.zip` 包。服务端识别包内唯一的 `SKILL.md` 并持久化受控副本；上传成功后的 Skill 默认禁用。用户必须先在详情中查看文档，并明确启用后，该 Skill 才能进入 Agent 可用 Skill 集合。

本功能不修改已存在的工作区、文件浏览、会话、设置按钮的图标、顺序、尺寸、样式、折叠语义或行为。只在 `AppSidebar` 的现有导航按钮序列中追加“技能”按钮及其线性书本/技能图标。

## 2. 非目标

- 不支持从浏览器选择任意文件夹、单独上传 `SKILL.md`、多文件上传、拖放目录或远程 URL 导入。
- 不支持 Skill 市场、在线下载、版本自动更新、签名信任链、多用户共享、同步或云存储。
- 不执行 Skill 文档中的 Shell、脚本、安装命令、网络下载、Git 操作或任意资源。
- 不允许 Skill 影响 ChangeSet 审批、文件访问策略、Provider 凭据、工作区注册或 Agent 的系统安全规则。
- 首期不在聊天中提供“运行 Skill”独立命令；仅让已经启用且通过识别的 Skill 成为编排器可选择的受控提示上下文。
- 不删除内置 Skill；删除能力仅适用于用户上传 Skill。

## 3. 架构与边界

### 3.1 权责边界

浏览器负责选择 ZIP、展示受控 API 返回的列表/详情/识别摘要，并提交 `skillId` 与状态切换意图。浏览器不得提交、保存或回显服务端存储路径、解压路径、任意文件路径、文档补丁、模型密钥或自由命令。

FastAPI 是 ZIP 处理、文档读取、元数据解析、持久化、删除和 Agent Skill 查询的唯一边界。所有实际文件系统访问只能使用服务端生成的 `skillId` 解析，不接受客户端路径。SQLite 仅保存结构化元数据、状态和完整性哈希；ZIP 原包与规范化后的 `SKILL.md` 保存在服务端受控 Skill 数据目录，不写入 SQLite。

Skill 文件属于应用管理数据，不属于注册工作区。因此不使用 `WorkspaceGuard` 访问用户上传包；取而代之的是专用的 `SkillPackageGuard`，其规则只服务于固定的应用数据目录。该服务不可用作通用文件浏览器。

### 3.2 存储位置

新增由服务端从模块位置解析的绝对默认目录：`backend/data/skills/`。可通过 `LIGHTCODE_SKILLS_PATH` 覆盖；相对覆盖值相对 `backend/` 解析。目录在服务端启动时创建，必须已被 `.gitignore` 覆盖，且绝不出现在 DTO、日志、SSE 或错误消息中。

每个 Skill 占用一个由服务端 UUID 派生的私有目录：

```text
backend/data/skills/
  skill_<uuid>/
    package.zip
    SKILL.md
```

写入顺序必须是：临时目录内校验与提取完成 -> SQLite 事务插入元数据 -> 原子替换为正式目录。任何步骤失败均清理当前临时目录，且不留下可查询的数据库记录。

## 4. 数据模型与迁移

实施本设计会修改 SQLite schema。实际实施前必须再次获得用户对迁移的明确授权。

在 `backend/app/db/database.py` 的 `SCHEMA_SQL` 新增 `skills` 表，并在 `run_migrations()` 添加幂等迁移。不要新建独立迁移框架，保持当前内联 schema/migration 模式。

```text
skills
  id                TEXT PRIMARY KEY
  name              TEXT NOT NULL
  source            TEXT NOT NULL                 -- builtin | uploaded
  status            TEXT NOT NULL                 -- disabled | enabled
  summary           TEXT NOT NULL DEFAULT ''
  document_sha256   TEXT NOT NULL
  package_sha256    TEXT NOT NULL DEFAULT ''
  package_bytes     INTEGER NOT NULL DEFAULT 0
  document_bytes    INTEGER NOT NULL DEFAULT 0
  resource_count    INTEGER NOT NULL DEFAULT 0
  section_count     INTEGER NOT NULL DEFAULT 0
  created_at        TEXT NOT NULL
  updated_at        TEXT NOT NULL
```

约束：`source` 只能为 `builtin` 或 `uploaded`；`status` 只能为 `disabled` 或 `enabled`；`name` 在 `source='uploaded'` 范围内唯一。首期不持久化模型生成的标签、全文搜索索引、用户笔记或 ZIP 条目名称。`SKILL.md` 原文不进 SQLite，以避免数据库膨胀和未受控的内容复制。

内置 Skill 的来源、文档和摘要由服务端内置注册表派生，只写入或只读映射到 `skills` 元数据；其状态可切换，删除始终拒绝。若内置 Skill 当前由宿主技能系统提供而非仓库文件，首期 API 可将其作为只读列表项返回，不复制宿主路径或原始运行时目录。

## 5. ZIP 安全识别

### 5.1 上传协议

新增 `POST /api/v1/skills/upload`，使用 `multipart/form-data`，字段名固定为 `package`。只允许一个以 `.zip` 结尾的文件；不接受表单中的名称、状态、路径、是否覆盖或任意元数据字段。上传成功返回新建 Skill 的安全摘要，状态固定为 `disabled`。

FastAPI 当前未声明 multipart 解析依赖。实施前必须确认可使用已有运行时依赖；若框架需要新增 `python-multipart`，这属于依赖变更，须在实施计划中显式列出并得到用户批准。不得手写不安全的 multipart 解析器。

### 5.2 限制与拒绝规则

实现时以策略常量固定如下上限，并由测试覆盖：

```text
最大 ZIP 原始大小：5 MiB
最大 ZIP 条目数：64
最大解压后总大小：10 MiB
最大单个解压条目：2 MiB
最大 SKILL.md 大小：256 KiB
最大路径深度：4
```

ZIP 在写盘前先用标准库 `zipfile` 检查中央目录；不信任文件名、声明大小或 MIME。逐项拒绝：

- 绝对路径、驱动器路径、UNC/设备路径、空路径、`.` 或 `..` 路径段。
- 规范化后逃逸目标目录的路径。
- Unix 符号链接、设备文件、目录链接或不能确定为普通文件/目录的外部属性。
- 重复规范化路径、重复 `SKILL.md`、加密条目、损坏压缩包和超过所有预算的包。
- 隐藏的敏感名称或扩展名：`.env`、`.git`、`*.pem`、`*.key`、`id_rsa*`、`credentials*`、`secrets*`。
- 非允许资源类型；首期仅允许 `SKILL.md`、`.md`、`.txt`、`.json`、`.png`、`.jpg`、`.jpeg`、`.webp` 与 `.svg`。资源不会在首期执行或作为 HTML 注入页面。

包内必须有且仅有一个根目录或一级目录内的 `SKILL.md`。`SKILL.md` 必须是常规文件、有效 UTF-8、去除空白后非空、大小不超限，并以第一个 ATX 标题（`# `）作为名称来源。没有合法标题、标题超过 80 个字符、控制字符或 Unicode 规范化后名称冲突均拒绝。

摘要取 `SKILL.md` 首个非标题的非空段落，去除 Markdown 标记后截断至 240 个 Unicode 码点。章节数由二级及以下 Markdown 标题计数。文档、ZIP 的 SHA-256 与资源数量构成识别摘要；这些字段只用于完整性与 UI，不构成信任或安全认证。

### 5.3 原子性与错误处理

识别失败时，API 返回稳定错误码和固定中文文案，不返回 ZIP 路径、解压路径、原始 `zipfile` 异常、条目完整清单或堆栈。成功前不插入 `skills` 行，不保留文件。数据库提交失败后必须删除新 Skill 目录；目录原子替换失败后删除尚未提交的元数据行。

建议新增错误码：

```text
SKILL_PACKAGE_REQUIRED
SKILL_PACKAGE_TYPE_DENIED
SKILL_PACKAGE_SIZE_DENIED
SKILL_PACKAGE_INVALID
SKILL_PACKAGE_STRUCTURE_DENIED
SKILL_PACKAGE_ENTRY_DENIED
SKILL_DOCUMENT_MISSING
SKILL_DOCUMENT_DUPLICATED
SKILL_DOCUMENT_INVALID
SKILL_ALREADY_EXISTS
SKILL_NOT_FOUND
SKILL_STATE_INVALID
SKILL_DELETE_DENIED
SKILL_STORAGE_FAILED
```

## 6. API 契约

所有端点使用 `/api/v1` 与 camelCase JSON；Pydantic 请求模型设置 `extra='forbid'`。响应不包含真实路径、完整 ZIP 内容、密钥、上传调用栈或原始异常。

```text
GET    /api/v1/skills
GET    /api/v1/skills/{skillId}
GET    /api/v1/skills/{skillId}/document
POST   /api/v1/skills/upload
PATCH  /api/v1/skills/{skillId}/status
DELETE /api/v1/skills/{skillId}
```

### 6.1 DTO

```json
{
  "id": "skill_...",
  "name": "receiving-code-review",
  "source": "uploaded",
  "status": "disabled",
  "summary": "在收到代码审查反馈时使用...",
  "documentBytes": 1732,
  "resourceCount": 2,
  "sectionCount": 4,
  "createdAt": "2026-08-12T10:00:00Z",
  "updatedAt": "2026-08-12T10:00:00Z"
}
```

`GET /skills/{skillId}/document` 返回 `{ "id", "name", "source", "status", "content", "documentSha256" }`。内容作为纯文本展示，前端不得使用 `v-html` 渲染。

状态更新请求是唯一允许的 JSON 请求体：

```json
{ "status": "enabled" }
```

只有识别通过的 `disabled` 或 `enabled` Skill 可读详情；不存在的 ID 返回 `SKILL_NOT_FOUND`。删除成功返回 `{ "id", "deleted": true }`。内置 Skill 删除返回 `SKILL_DELETE_DENIED`，状态切换仍允许。

## 7. Agent 使用门禁

服务端新增只读的 `SkillService.list_enabled_for_agent()`。它只返回 `status='enabled'` 的安全内容投影：`id`、`name`、`summary`、受控文档文本、文档哈希。不得返回 ZIP、资源路径、存储目录或任意未识别内容。

`ChatService` / `ModelOrchestrator` 在构建模型上下文时从该服务读取启用 Skill。它们不能按模型输出、聊天文本或浏览器参数选择任意 Skill ID；只能消费服务端已启用集合。Skill 文档是非可信提示输入，必须以明确边界标记嵌入系统上下文，且不能覆盖 LightCode 的系统安全策略、工具 allowlist、预算、审批规则、路径约束或 Provider 配置。

上传成功后默认 `disabled`；禁用或删除 Skill 后，下一次模型请求不再读取它。已经进行中的模型任务使用创建时已持久化/构造的上下文，不因中途切换状态而重写历史任务事件。

## 8. 前端设计与交互

### 8.1 导航和路由

修改 `frontend/src/components/AppSidebar.vue`：在原有工作区、文件浏览、会话按钮之后新增 `skills` 导航项。复用既有 `.nav-btn`、折叠语义、尺寸、颜色、`data-testid` 命名方式与 SVG 描边风格；其他现有项不改动。

新增路由 `/workspace/:workspaceId/skills`，渲染 `SkillsView`。从工作区中点击 Skill 进入该路由；当视图窄于现有移动断点时，继承共享侧栏的响应行为。

### 8.2 管理列表

`SkillsView` 保持工作区暖纸视觉语言与信息密度：标题、搜索框、来源筛选（全部/内置/已上传）、“上传技能”按钮和无嵌套卡片的行式列表。列表行包含线性 Skill 图标、名称、来源、摘要、当前启用状态和稳定尺寸的开关。

行点击打开详情模态层；行内状态开关必须阻止行点击冒泡。上传按钮打开仅接受 `.zip` 的原生文件输入；提交中禁用重复选择，显示固定的“正在识别”状态。成功后刷新/归约列表并自动打开新 Skill 详情，但仍保持 `disabled`；失败只显示安全错误码映射的固定中文提示。

### 8.3 详情模态层

新增 `SkillDetailOverlay.vue`，在 `Teleport to="body"` 下渲染。复用现有 `SettingsOverlay` 的可访问性模式：`role="dialog"`、`aria-modal`、显式标题、打开后焦点进入面板、关闭后焦点回到触发行、关闭按钮/遮罩点击/Escape 关闭、`prefers-reduced-motion` 下无入场动画。

弹窗是居中固定的大面板，尺寸为 `78vw × 76vh`，受 `calc(100vw - 48px)` 与 `calc(100vh - 48px)` 限制。它不包含额外的内部侧边栏、概览标签或识别信息页；打开即显示 `SKILL.md` 内容。正文使用 `<pre>` 或等效纯文本容器保留文档格式，滚动只发生在正文区域。

页脚提供状态开关和删除按钮。禁用 Skill 的开关旁明确显示“启用后可被 Agent 使用”；已启用 Skill 显示“当前可被 Agent 使用”。删除仅对 `source='uploaded'` 显示，并要求在下一轮设计/实施中明确确认交互，不使用浏览器原生 `confirm()`；内置 Skill 不展示删除按钮。

### 8.4 前端分层

新增 `skills.service.ts` 作为 HTTP 服务边界、`skills.store.ts` 作为 Pinia 状态与异步动作边界、`SkillDetailOverlay.vue` 与 `SkillsView.vue` 作为视图层。扩展 `types/agent.ts` 或新增同目录的 Skill 类型文件来定义 API DTO。组件、视图和 store 不直接调用 `fetch`，不解析 ZIP，不保存文档到 `localStorage`，不持有真实路径。

## 9. 后端实现单元

建议新增以下模块，职责保持单一：

```text
backend/app/config/skills.py
  Skill 数据目录与所有 ZIP/文档预算常量。

backend/app/services/skill_package.py
  ZIP 目录校验、路径规范化、资源类型校验、UTF-8 文档验证与元数据提取。

backend/app/services/skill_service.py
  事务边界、受控存储、列表/详情/文档/状态/删除、Agent 安全投影。

backend/app/schemas/skill_contracts.py
  extra=forbid 的请求与响应 DTO。

frontend/src/services/skills.service.ts
frontend/src/stores/skills.store.ts
frontend/src/views/SkillsView.vue
frontend/src/components/SkillDetailOverlay.vue
```

`routes.py` 只声明端点与 DTO，委托 `SkillService`。`SkillPackageGuard` 不通过 HTTP 暴露。服务端日志通过现有 `observability.redact()` 输出聚合事件，仅记录稳定 `skillId`、来源、状态、大小/数量/错误码，不记录原始文档内容、ZIP 条目名、路径或异常文本。

## 10. 测试与验收

### 10.1 后端测试

新增 `backend/tests/test_skill_service.py` 与 `backend/tests/test_skills_api.py`，至少覆盖：

- 正常 ZIP -> 识别唯一 `SKILL.md` -> `disabled` 持久化 -> 文档可读取。
- 有效上传返回的 DTO 不含路径、ZIP 内容和异常文本。
- 非 ZIP、空 ZIP、损坏 ZIP、加密 ZIP、超原始大小、超条目数、超解压预算、超文档预算均 fail-closed。
- 路径穿越、绝对路径、驱动器/UNC 路径、软链接、重复条目、重复 `SKILL.md`、秘密文件名与不允许扩展名被拒绝。
- 无 `SKILL.md`、多个 `SKILL.md`、非 UTF-8、空文档、无标题、标题非法、同名上传被拒绝。
- 上传任一步失败不遗留 `skills` 行或文件目录。
- 只允许 `disabled <-> enabled`；未知状态拒绝；上传后的初始状态不可由请求覆盖。
- 已启用集合只含 enabled 条目；禁用/删除后后续查询不含该 Skill。
- 删除上传 Skill 同时清理其受控目录；删除内置 Skill 被拒绝；重复删除返回 `SKILL_NOT_FOUND`。
- 并发重复上传同一名称时最多一个成功，另一个返回 `SKILL_ALREADY_EXISTS`，无损坏目录。
- 日志、API 响应与失败负载不包含临时目录、受控目录、完整条目名或文档内容。

### 10.2 前端测试

新增服务、store、视图和模态层测试，至少覆盖：

- `AppSidebar` 仅新增 Skill 按钮，原导航按钮 test id、顺序和交互不回归。
- 路由从工作区进入 Skill 管理视图；筛选与搜索只作用于内存中的安全摘要。
- 上传控件限制 `.zip`，提交中禁用，成功后新增默认禁用项并打开详情。
- 详情模态层显示纯文本 MD，不产生 HTML 注入；无内部详情侧栏。
- Escape、遮罩、关闭按钮与焦点归还行为；减少动画偏好。
- 开关调用状态 API，失败回滚并显示固定文案。
- 删除按钮只对已上传 Skill 显示；内置 Skill 不显示。
- 所有 API 响应经运行时契约校验，含未知字段、路径字段或未知状态的响应被拒绝。

### 10.3 全量验证

实施完成后必须依次运行：

```text
backend: pytest
frontend: npm test
frontend: npm run build -- --emptyOutDir false
```

OneDrive 文件锁可能导致清空 `dist` 失败，因此保留当前 `--emptyOutDir false` 约定。不得通过 skip、假成功、关闭断言或放宽安全策略获取绿色结果。

## 11. 实施顺序

1. 取得 SQLite schema 迁移与可能新增 multipart 解析依赖的明确授权。
2. 先编写 ZIP 安全识别与状态机失败测试，再实现 `skills` schema、配置和后端服务。
3. 加入路由与 API 契约测试，验证上传/查询/状态/删除和 Agent enabled 投影。
4. 按现有侧栏与设置层模式实现前端服务、store、路由、Skill 按钮、管理视图和详情模态层。
5. 添加前端聚焦测试，执行后端全量、前端全量、类型检查与构建。
6. 用本机浏览器验证：上传有效 ZIP -> 自动打开文档 -> 默认禁用 -> 手动启用 -> 关闭/重开保持状态 -> 禁用或删除后 Agent 查询不再返回。

## 12. 验收结论

本功能完成的定义是：用户能在不改变现有侧栏导航的前提下，通过新增 Skill 按钮进入管理页；只能上传安全且结构正确的 ZIP；每个合法上传都默认禁用；详情弹窗直接、安全地展示 `SKILL.md`；用户手动启用前，Agent 永远不能获得该 Skill；删除、错误和所有公开输出均不泄露文件系统位置、文档内容之外的受控信息或内部异常。
