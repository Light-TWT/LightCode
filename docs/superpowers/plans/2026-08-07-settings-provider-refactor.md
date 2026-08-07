# 多供应商设置页重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `/settings` 重构为 LightCode 暖纸视觉的多供应商设置页：沿用主工作区侧边栏，设置分类仅保留“模型与供应商”与“关于”，供应商列表可搜索，右侧展示配置安全摘要，“添加供应商”通过暖纸弹层完成。

**Architecture:** 前端先重构 `SettingsView.vue` 为“分类栏 + 供应商列表 + 详情区 + 弹层”四区结构，视觉与交互以 `docs/design/settings-providers.html` 为参考；服务合约先保持现有单 Provider API，新增多供应商服务接口由 `ProviderService` 提供，凭据仍然只在提交瞬间存在于前端内存。多供应商后端（DTO、CRUD API、多配置凭据存储）属于独立阶段，必须先冻结契约与测试再动代码。

**Tech Stack:** Vue 3 + TypeScript + Vite（`frontend/`）；FastAPI + Pydantic（`backend/`）；Vitest / pytest；设计规范见 `docs/design/README.md` 与 `docs/superpowers/specs/2026-08-07-multi-provider-settings-design.md`。

---

## 文件结构

- `frontend/src/types/agent.ts`：新增供应商摘要类型（`ProviderSummary`），保持安全视图不变量（无 key / 无完整 baseUrl）。
- `frontend/src/services/provider.service.ts`：新增多供应商读取接口（列表 / 单个安全摘要），保留现有单 Provider 保存 / 测试 / 清除接口。
- `frontend/src/views/SettingsView.vue`：重构为四区结构；API Key 只在提交瞬间存在，提交后清空。
- `frontend/src/views/SettingsView.test.ts`：新增列表选中、搜索过滤、弹层打开/关闭、安全不变量断言。
- `frontend/src/components/`（新增）：`SettingsNav.vue`（分类栏）、`ProviderList.vue`（列表+搜索）、`ProviderDetail.vue`（右侧安全摘要）、`AddProviderModal.vue`（弹层）。
- 后端（阶段 B 前置）：`backend/app/schemas/model_contracts.py`、`backend/app/services/credential_store.py`、`backend/app/api/routes.py` 保持现状，仅在阶段 B 扩展。

---

## 阶段 A：前端设置页重构

### Task 1: 供应商安全摘要类型、服务接口与后端只读端点

**Files:**
- Modify: `backend/app/schemas/model_contracts.py`（新增 `ProviderProfile`）
- Modify: `backend/app/api/routes.py`（新增只读 `GET /provider/profiles`）
- Test: `backend/tests/test_provider_health_api.py`
- Modify: `frontend/src/types/agent.ts`
- Modify: `frontend/src/services/provider.service.ts`
- Test: `frontend/src/services/provider.service.test.ts`

- [ ] **Step 0（后端）: 写失败测试**

在 `backend/tests/test_provider_health_api.py` 新增用例：

- `GET /api/v1/provider/profiles` 返回 200，值为安全摘要数组。
- 配置了运行期凭据时数组含 1 条（`enabled=true`）；未配置时含 1 条 `unconfigured` 摘要或空数组（与 `GET /provider/settings` 的 status 一致）。
- 断言 `JSON.stringify(response.json())` 不包含 `apiKey`、`sk-`、`Bearer` 或完整 `https://` URL（只允许 `baseUrlHost` 域名）。

- [ ] **Step 1（后端）: 运行确认失败**

```bash
cd backend
python -m pytest tests/test_provider_health_api.py -q
```

预期：FAIL —— `ProviderProfile` 未定义 / 端点 404。

- [ ] **Step 2（后端）: 实现只读端点**

`backend/app/schemas/model_contracts.py` 新增（`extra=forbid`、camelCase、安全视图）：

```python
class ProviderProfile(BaseModel):
    id: str
    name: str
    provider: str
    model_id: str
    enabled: bool
    status: Literal["ready", "unconfigured", "degraded", "disabled"]
    base_url_host: str  # 仅域名，不含路径/凭据
```

`backend/app/api/routes.py` 新增：

```python
@router.get("/provider/profiles", response_model=list[ProviderProfile])
def provider_profiles(request: Request) -> list[ProviderProfile]:
    """只读安全摘要列表（当前派生自 env config + 运行期凭据，不发网络请求）。"""
    config: ModelProviderConfig = effective_config(
        request.app.state.env_model_provider, request.app.state.credential_store
    )
    profile = ProviderProfile(
        id="default",
        name=config.provider,
        provider=config.provider,
        model_id=config.model_id,
        enabled=config.status() == "ready",
        status=config.status(),
        base_url_host=config.host_summary(),  # 仅域名
    )
    return [profile] if config.status() != "disabled" else []
```

> 阶段 B 之前不扩展凭据存储与 CRUD；`host_summary()` 需在 `ModelProviderConfig` 上新增仅返回 netloc 的方法（不含路径、不打印 key）。

- [ ] **Step 3（后端）: 运行确认通过**

```bash
python -m pytest tests/test_provider_health_api.py -q
```

预期：PASS，安全断言成立。

- [ ] **Step 4（前端）: 写失败测试**

在 `provider.service.test.ts` 新增用例，断言 `listProviders()`：

- 返回 `ProviderSummary[]`。
- `JSON.stringify(result)` 不匹配 `/apiKey|sk-|Bearer/i`、不含完整 `https://` 地址。
- 单条摘要含：`id`、`name`、`provider`、`modelId`、`enabled`、`status`、`baseUrlHost`。

- [ ] **Step 5（前端）: 运行测试确认失败**

```bash
cd frontend
npx vitest run src/services/provider.service.test.ts
```

预期：FAIL —— `ProviderSummary` 类型与 `listProviders` 不存在。

- [ ] **Step 6（前端）: 在 `types/agent.ts` 新增类型**

```ts
/** 供应商安全摘要 —— 响应绝不含 API Key / 完整 Base URL / Authorization header */
export interface ProviderSummary {
  id: string
  name: string
  provider: string
  modelId: string
  enabled: boolean
  status: 'ready' | 'unconfigured' | 'degraded' | 'disabled'
  baseUrlHost: string
}
```

- [ ] **Step 7（前端）: 在 `provider.service.ts` 新增接口**

```ts
export interface ProviderService {
  // ...既有 getHealth/getSettings/saveSettings/testConnection/clearSettings
  /** 多供应商安全摘要列表（只读，后端 config 派生） */
  listProviders(): Promise<ProviderSummary[]>
}
```

实现调用 `GET /provider/profiles`，响应经运行时 DTO 校验（复用 `requestJson`/`requestJsonValidated`）。

- [ ] **Step 8（前端）: 运行测试确认通过**

```bash
npx vitest run src/services/provider.service.test.ts
```

预期：PASS，且安全断言（无 key、无完整 URL）成立。

- [ ] **Step 9: 提交**

```bash
git add backend/app/config/model_provider.py backend/app/schemas/model_contracts.py backend/app/api/routes.py backend/tests/test_provider_health_api.py frontend/src/types/agent.ts frontend/src/services/provider.service.ts frontend/src/services/provider.service.test.ts
git commit -m "feat: 供应商安全摘要只读端点与前端服务接口"
```

### Task 2: 主侧边栏复用 + 设置分类栏 + 页面骨架

**Files:**
- Create: `frontend/src/components/AppSidebar.vue`（从 `WorkspaceView.vue` 抽取主侧边栏）
- Create: `frontend/src/components/SettingsNav.vue`
- Modify: `frontend/src/views/WorkspaceView.vue`（改用共享 `AppSidebar`）
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] **Step 1: 抽取主侧边栏为共享组件 `AppSidebar.vue`**

- 从 `frontend/src/views/WorkspaceView.vue:360-421` 抽取：品牌区（`L` + LightCode + 折叠箭头）、导航（工作区 / 文件浏览 / 会话，SVG 图标保持原样）、底部设置按钮。
- 以 props 接收 `activeNav` 与 `collapsed`，`emit('toggle', key)` / `emit('toggleCollapse')`；设置按钮由 `router.push('/settings')` 触发。
- **必须以原项目现有实现为准，不得复制 `settings-providers.html` 中的简化字符图标**。
- `WorkspaceView.vue` 切换到使用 `AppSidebar` 后，原 `toggleNav` / `sidebarCollapsed` 状态保留在视图层。

- [ ] **Step 2: 在 `SettingsView.vue` 中引入 `AppSidebar`**

- 设置页左侧渲染 `AppSidebar`（设置按钮高亮，指向 `/settings`），下方为设置分类栏 + 内容区。
- 验证：`WorkspaceView.test.ts` 的侧边栏用例（`nav-btn-*`、`settings-btn`、`sidebar-collapse`）仍通过。

- [ ] **Step 3: 创建 `SettingsNav.vue`**

- 标题“设置”，沿用 `Caveat` 大标题 + `JetBrains Mono` eyebrow（`LIGHTCODE / LOCAL BUILD`）。
- 分类仅两项：`模型与供应商`（默认选中）、`关于`。
- 复用 `docs/design/settings-providers.html` 中 `.settings-nav` 的暖纸样式（`--paper`/`--line`/`--yellow-light`），不复制主侧边栏。
- 通过 `v-model:category` 对外通信；`关于` 暂渲染占位提示“关于内容后续补充”。

- [ ] **Step 4: 改造 `SettingsView.vue` 为三栏布局**

- 页面主体改为左侧 `AppSidebar` + `SettingsNav` + 右侧内容区（供应商列表栏 + 详情区）。
- 顶部保留返回按钮与“LightCode · 设置”标题，保留 `refresh` 能力。
- 从 `ProviderService` 获取 `ProviderSettingsResponse` 与 `ProviderSummary[]`；列表为空时显示暖色空状态。

- [ ] **Step 5: 运行测试**

```bash
npx vitest run src/views/SettingsView.test.ts
```

预期：既有用例不回归；新增断言“设置页渲染 `模型与供应商` 与 `关于` 两个分类”。

### Task 3: 供应商列表与搜索

**Files:**
- Create: `frontend/src/components/ProviderList.vue`
- Test: `frontend/src/views/SettingsView.test.ts`

- [ ] **Step 1: 创建 `ProviderList.vue`**

- 标题“供应商” + 配置数量（`N 个配置`）。
- 搜索框 `⌕`，按 `name` 或 `modelId` 过滤。
- 列表项：缩写图标（取 `name` 前 2 位大写）、名称、`modelId`、状态点（`ready` 绿点，其余黄点）。
- 选中项高亮（浅黄背景 + 铅笔边框）；无匹配显示“没有找到匹配的供应商”。
- 底部固定“＋ 添加供应商”按钮，点击触发 `emit('openAdd')`。

- [ ] **Step 2: 接入 SettingsView**

- `SettingsView` 维护 `selectedId`，默认选中第一条；点击列表项更新详情区。
- 空列表（未配置任何供应商）时详情区展示选择提示空状态。

- [ ] **Step 3: 写测试**

新增用例：

- 点击第二条供应商后，详情区标题切换。
- 搜索框输入不匹配关键字时，列表项隐藏并显示空状态文案。
- 点击“添加供应商”触发 `openAdd` 事件。

- [ ] **Step 4: 运行测试**

```bash
npx vitest run src/views/SettingsView.test.ts
```

### Task 4: 右侧详情区

**Files:**
- Create: `frontend/src/components/ProviderDetail.vue`
- Test: `frontend/src/views/SettingsView.test.ts`

- [ ] **Step 1: 创建 `ProviderDetail.vue`**

- 未选择：显示选择提示空状态（沿用 `settings-providers.html` 的 `.empty-detail` 结构）。
- 已选择：供应商缩写、名称、`modelId`、状态徽章；下方三张摘要卡：
  - 运行期配置：仅后端持有凭据 · 本次会话可用
  - 模型权限：只读检索 · 模型只能提出变更 · 写入必须经过显式审批
  - 安全视图：不展示 API Key、完整 Base URL 或上游原始响应

- [ ] **Step 2: 写测试**

断言：详情区文本不包含 `sk-` 形状密钥、不包含 `https://` 完整地址；状态徽章文案随 `status` 变化（`ready` → “已启用”，其余 → “等待测试”）。

### Task 5: 添加供应商弹层

**Files:**
- Create: `frontend/src/components/AddProviderModal.vue`
- Test: `frontend/src/views/SettingsView.test.ts`

- [ ] **Step 1: 创建 `AddProviderModal.vue`**

- 暖纸弹层：暖白纸张背景、细铅笔边框、暖灰半透明遮罩（`rgba(74,61,45,.34)` + 轻微 blur），不使用黑色背景。
- 供应商协议模板按钮网格：OpenAI / OpenAI Compatible / DeepSeek / Qwen / Kimi / OpenRouter / SiliconFlow / Ollama；选中后自动填入 `配置名称` 与默认 `模型 ID` 提示。
- 表单字段：配置名称、模型 ID、API Key（`type="password"` + `autocomplete="new-password"`）、Base URL、启用开关。
- 底部操作：`测试连接`（蓝色描边）+ `＋ 测试并添加`（黄色主按钮）。
- 交互：点击遮罩 / `Esc` / 关闭按钮关闭弹层。

- [ ] **Step 2: 接入保存逻辑**

- `测试连接` 调用现有 `providerService.testConnection`，成功文案“✓ 连接参数有效”，失败只渲染稳定错误码对应文案（复用 `TEST_ERROR_TEXTS`）。
- `测试并添加` 在当前阶段调用 `providerService.saveSettings` 写入运行期凭据，成功后关闭弹层并刷新列表；`finally` 中清空 `apiKey`。
- 表单校验：`provider`、`baseUrl`、`modelId`、`apiKey` 任一项为空时禁用“测试并添加”。

- [ ] **Step 3: 写测试**

新增用例：

- 打开弹层后 `API Key` 输入框 `type === 'password'`。
- 选择协议模板更新 `配置名称`。
- 提交后 `apiKey` 被清空（断言 `wrapper.vm` 表单值或输入框值为空）。
- 关闭弹层后 DOM 中不存在弹层内容（或隐藏）。

### Task 6: 前端全量验证

- [ ] **Step 1: 运行前端测试**

```bash
cd frontend
npx vitest run
```

- [ ] **Step 2: 类型检查与构建**

```bash
npx vue-tsc -b
npx vite build --emptyOutDir false
```

- [ ] **Step 3: 浏览器手工核对**

对照 `docs/design/settings-providers.html` 检查：两栏布局、暖纸配色、选中态、弹层打开/关闭、搜索过滤、安全摘要文案。

---

## 阶段 B：多供应商后端（契约红线，须另行确认）

> 涉及后端 schema / API 合约变更，属于 AGENTS.md 红线。**在用户明确确认前不得动代码**；以下为契约草案。
> **状态：已完成（2026-08-07，用户确认后实施）**。实现细节：`ProviderCredentialStore` 扩展为多配置
> dict（`get_all()`/`get_named()`/`remove()`，`get()` 保持激活配置语义，ChatService/ModelOrchestrator 无改动）；
> 新增 `ProviderProfileCreate`/`ProviderProfileDeleteResponse` DTO；`/provider/profiles` 支持
> GET 列表 / POST 创建（连接测试通过才保存）/ GET by id / DELETE by id，未保存时回退 env 派生 `default`。

- [x] **Step 1: 冻结多供应商 DTO**

`backend/app/schemas/model_contracts.py` 新增（`extra=forbid`、camelCase、无 key/完整 baseUrl）：

```python
class ProviderProfile(BaseModel):
    id: str
    name: str
    provider: str
    model_id: str
    enabled: bool
    status: Literal["ready", "unconfigured", "degraded", "disabled"]
    base_url_host: str  # 仅域名，不含路径/凭据

class ProviderProfileCreate(BaseModel):
    name: str
    provider: str = "openai-compatible"
    base_url: str
    api_key: str  # 仅请求体；响应与日志绝不回显
    model_id: str
    enabled: bool = True
```

- [x] **Step 2: 扩展凭据存储为多配置**

`backend/app/services/credential_store.py` 将单例改为 `dict[str, ProviderRuntimeCredential]`（按配置 id），仍为进程内存、线程安全、`get_all()` 只返回安全视图；Electron 阶段整体替换为系统密钥库。

- [x] **Step 3: 新增 CRUD 端点**

`backend/app/api/routes.py` 新增：

```text
GET    /provider/profiles           # 安全摘要列表
POST   /provider/profiles           # 创建 + 测试连接，通过才保存
GET    /provider/profiles/{id}      # 单条安全摘要
DELETE /provider/profiles/{id}      # 删除配置
```

- [x] **Step 4: 先写失败测试再实现**

`backend/tests/test_provider_profiles.py`：安全不变量（响应无 key/完整 URL）、创建前连接测试、删除后回落、未知 id 404、`extra=forbid` 拒绝多余字段。

- [x] **Step 5: 后端全量验证**

```bash
cd backend
python -m pytest
```

验证结果：后端全量 **226 passed / 2 skipped**（含阶段 B 新增 11 个 profiles 用例 + 阶段 A 5 个 profiles 用例）；前端 **96 passed / 13 文件** + `vue-tsc -b` + `vite build --emptyOutDir false` 通过。

---

## 自检结论

- 阶段 A 仅新增后端**只读** `GET /provider/profiles`（config 派生、不发网络请求、无 schema 变更、无凭据存储变更），主要工作是前端结构重构，风险面可控。
- 阶段 B 是独立后端工作包（多配置凭据存储 + CRUD），已单独列为红线确认项，不夹带在设置页重构中。
- 所有测试断言保持安全不变量：无 API Key、无完整 Base URL、无 Authorization header、无上游原始响应。
