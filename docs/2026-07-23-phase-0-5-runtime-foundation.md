# Phase 0.5 运行时基础实施记录

> **状态：已完成（2026-07-24）**。本文件保留原始任务分解、契约决策和验证路径，复选框用于记录实现完成情况；实际代码结构、运行边界和当前命令以 `AGENTS.md`、`backend/README.md`、`frontend/README.md` 为准。

## 完成摘要

- FastAPI、SQLite、确定性 Mock Runtime、REST API、SSE 事件回放与前端 HTTP/EventSource 服务适配器均已实现。
- 后端当前为 16 个 pytest 用例，前端当前为 37 个 Vitest 用例；前端 `vue-tsc -b && vite build` 已通过。
- SQLite 默认路径已改为基于文件位置的绝对路径；`LIGHTCODE_DATABASE_PATH` 支持临时隔离数据库，审批状态在同一数据库重启后保持。
- 实际代码将种子逻辑保留在 `backend/app/db/database.py`，SSE 路由保留在 `backend/app/api/routes.py`；未单独创建计划草案中的 `db/seed.py` 或 `api/sse.py`。
- 本阶段仍严格禁止真实工作区访问、源码写入、Shell、模型、密钥、Electron、网络下载、依赖安装和 Git 写操作。

**目标：** 用本地 FastAPI 和 SQLite Mock 运行时替换 LightCode 仅前端夹具，在无需访问真实项目目录或模型提供商的情况下，为现有的工作区、任务、历史、审批和有序事件合约提供服务。

**架构：** 后端拥有一个 SQLite 数据库，并暴露与现有前端 TypeScript 合约完全匹配的 camelCase JSON。确定性种子数据集替换前端夹具数据；审批操作更新任务状态并追加持久化事件。FastAPI 通过 SSE 发送持久化的任务事件，前端则在现有服务接口背后将 Mock 服务实现替换为 HTTP 和 EventSource 适配器。

**技术栈：** Python 3.11+, FastAPI, Pydantic, Python `sqlite3`, pytest, httpx/TestClient, Vue 3, TypeScript, Pinia, 原生 `EventSource`。

---

## 范围与非目标

本计划仅实现一个本地确定性 Mock 运行时。它不会打开工作区路径、读写文件、调用 shell、调用模型提供商、接受密钥、启动 Electron，或声称实现了真正的安全策略。未来运行时端点的形状现在就已设计好，以便前端后续可以保留相同的服务合约。

实现必须保留已批准的前端行为：

- Workspace Home 获取最近的和已注册的工作区。
- Agent Workspace 获取当前任务，批准其种子变更集，并接收有序的任务事件。
- Session History 获取摘要和只读详情记录。
- Settings 保持本地 Mock 配置，不请求密钥。

## 合约决策

### 基础 URL 和 JSON

- 开发 API 基础 URL：`http://127.0.0.1:8000/api/v1`。
- 开发前端源：`http://127.0.0.1:5173`。
- 所有 API JSON 使用 camelCase 以匹配 `frontend/src/types/agent.ts`。
- 错误 JSON 始终为 `{"detail": "human-readable message"}`。

### REST 路由

```text
GET  /health
GET  /api/v1/workspaces/recent
GET  /api/v1/workspaces
GET  /api/v1/workspaces/{workspaceId}
GET  /api/v1/workspaces/{workspaceId}/sessions
GET  /api/v1/sessions/{sessionId}/tasks/current
GET  /api/v1/workspaces/{workspaceId}/tasks/history
GET  /api/v1/tasks/{taskId}
POST /api/v1/tasks/{taskId}/changeset/approve
GET  /api/v1/tasks/{taskId}/events
```

`GET /api/v1/tasks/{taskId}/events` 是一个 SSE 流。它按升序 sequence 重放持久化事件，发出一个最终的 `event: stream.end`，然后关闭。在 Phase 0.5 中它故意设计为仅重放模式。

### SQLite 表

```text
workspaces(id TEXT PRIMARY KEY, name TEXT, root_path TEXT, status TEXT,
           tags_json TEXT, last_task TEXT, time_ago TEXT, is_recent INTEGER)

sessions(id TEXT PRIMARY KEY, workspace_id TEXT, title TEXT, status TEXT)

tasks(id TEXT PRIMARY KEY, session_id TEXT, workspace_id TEXT, title TEXT,
      state TEXT, model_output TEXT, changeset_status TEXT,
      verification_status TEXT, verification_command TEXT,
      verification_lines_json TEXT)

task_history(id TEXT PRIMARY KEY, workspace_id TEXT, status TEXT, title TEXT,
             summary TEXT, time TEXT, duration TEXT, tool_count INTEGER,
             files_json TEXT, test_result_json TEXT, detail_json TEXT)

task_events(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, sequence INTEGER,
            event_type TEXT, payload_json TEXT, created_at TEXT,
            UNIQUE(task_id, sequence))
```

计划步骤、工具调用、变更集内容和验证行作为 JSON 嵌入在这个精简的 Mock schema 中。仅在真实运行时查询模式要求时才进行规范化。

## 计划文件结构

```text
backend/
  pyproject.toml
  app/
    __init__.py
    main.py                 FastAPI 应用和 CORS 设置
    api/routes.py           REST 和 SSE 端点声明
    db/database.py          sqlite 连接和 schema 初始化
    db/seed.py              确定性 Phase 0 夹具种子数据
    schemas/contracts.py    Pydantic 请求和响应模型
    services/runtime.py     读操作、审批转换、事件重放
  tests/
    conftest.py
    test_health.py
    test_workspace_api.py
    test_task_api.py
    test_event_stream.py

frontend/src/
  config/runtime.ts         API 基础 URL 配置
  services/http.ts          fetch 和 JSON 错误辅助
  services/workspace.service.ts
  services/task.service.ts
  services/event.service.ts EventSource 包装器
  stores/agent.store.ts
  stores/home.store.ts
  views/AgentWorkspaceView.vue
  views/WorkspaceHomeView.vue
  views/SessionHistoryView.vue
```

## 任务 1：引导一个可测试的本地运行时

**文件：**
- 新建：`backend/pyproject.toml`
- 新建：`backend/app/__init__.py`
- 新建：`backend/app/main.py`
- 新建：`backend/app/db/database.py`
- 新建：`backend/tests/conftest.py`
- 新建：`backend/tests/test_health.py`
- 修改：`AGENTS.md`

- [x] **步骤 1：先更新项目规则到 Phase 0.5**

在写入任何后端文件之前，将 `AGENTS.md` 从 Phase 0 仅前端限制更新为
Phase 0.5 运行时基础限制。明确允许 FastAPI、SQLite、确定性 Mock 运行时、
REST 和 SSE；继续禁止真实文件系统访问、shell 执行、模型提供商、密钥处理和
Electron 工作。

- [x] **步骤 2：编写 health endpoint 测试**

```python
from fastapi.testclient import TestClient


def test_health_reports_local_runtime(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "runtime": "mock"}
```

- [x] **步骤 3：运行 health 测试，验证失败**

运行：`python -m pytest tests/test_health.py -q`

预期：FAIL 因为 `app.main` 不存在。

- [x] **步骤 4：添加后端依赖元数据**

```toml
[project]
name = "lightcode-runtime"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["fastapi>=0.115", "uvicorn[standard]>=0.30"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [x] **步骤 5：添加 FastAPI 应用和测试 fixture**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="LightCode Local Runtime", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "runtime": "mock"}
```

```python
# backend/tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

- [x] **步骤 6：运行聚焦测试**

运行：`python -m pytest tests/test_health.py -q`

预期：`1 passed`。

- [x] **步骤 7：提交引导代码**

```bash
git add AGENTS.md backend
git commit -m "feat: bootstrap local mock runtime"
```

## 任务 2：添加 SQLite 初始化和确定性种子数据

**文件：**
- 新建：`backend/app/db/seed.py`
- 修改：`backend/app/db/database.py`
- 修改：`backend/app/main.py`
- 新建：`backend/tests/test_database.py`

- [x] **步骤 1：编写 schema 和种子隔离测试**

```python
from app.db.database import initialize_database


def test_initialize_database_seeds_current_workspace(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    connection = initialize_database(database_path)

    row = connection.execute(
        "SELECT id, name FROM workspaces WHERE id = ?",
        ("workspace-login-service",),
    ).fetchone()

    assert tuple(row) == ("workspace-login-service", "login-service")


def test_initialize_database_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    initialize_database(database_path)
    connection = initialize_database(database_path)

    count = connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
    assert count == 7
```

- [x] **步骤 2：运行数据库测试，验证失败**

运行：`python -m pytest tests/test_database.py -q`

预期：FAIL 因为 `initialize_database` 不存在。

- [x] **步骤 3：实现标准库 sqlite 初始化器**

`initialize_database(path: Path) -> sqlite3.Connection` 必须：

- 使用 `row_factory = sqlite3.Row` 调用 `sqlite3.connect(path)`；
- 执行合约中的所有 `CREATE TABLE IF NOT EXISTS` 语句；
- 调用 `seed_database(connection)`；
- 提交并返回连接。

`seed_database(connection)` 必须使用 `INSERT OR IGNORE`，并精确播种 `frontend/src/fixtures/agent.fixture.ts` 中已代表的七个工作区条目以及任务/历史 fixture 语义。

- [x] **步骤 4：在启动时初始化应用数据库**

使用 FastAPI lifespan 函数。默认数据库路径为 `backend/data/lightcode.db`，允许 `LIGHTCODE_DATABASE_PATH` 进行测试和本地覆盖，在需要时创建父级 data 目录，并在 `app.state` 中存储连接工厂而非全局请求连接。

- [x] **步骤 5：运行聚焦的后端测试**

运行：`python -m pytest tests/test_database.py tests/test_health.py -q`

预期：`3 passed`。

- [x] **步骤 6：提交 schema 和种子数据**

```bash
git add backend
git commit -m "feat: add seeded sqlite mock runtime"
```

## 任务 3：暴露 Workspace 和 Session REST 合约

**文件：**
- 新建：`backend/app/schemas/contracts.py`
- 新建：`backend/app/api/routes.py`
- 新建：`backend/app/services/runtime.py`
- 修改：`backend/app/main.py`
- 新建：`backend/tests/test_workspace_api.py`

- [x] **步骤 1：编写 API 合约测试**

```python
def test_recent_workspaces_return_camel_case_entries(client) -> None:
    response = client.get("/api/v1/workspaces/recent")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "workspace-login-service"
    assert payload[0]["rootPath"] == "~/workspace/login-service"
    assert payload[0]["status"] == "waiting"


def test_unknown_workspace_returns_not_found(client) -> None:
    response = client.get("/api/v1/workspaces/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found: missing"}


def test_workspace_sessions_match_frontend_contract(client) -> None:
    response = client.get("/api/v1/workspaces/workspace-login-service/sessions")

    assert response.status_code == 200
    assert response.json()[0] == {
        "id": "session-login-validation",
        "title": "登录接口校验",
        "status": "awaiting_approval",
    }
```

- [x] **步骤 2：运行 workspace API 测试，验证失败**

运行：`python -m pytest tests/test_workspace_api.py -q`

预期：FAIL 因为路由未注册，返回 HTTP 404。

- [x] **步骤 3：定义严格的 Pydantic 响应模型**

定义 `WorkspaceEntryResponse`、`WorkspaceResponse` 和 `SessionResponse`，使用与 `frontend/src/types/agent.ts` 中 `WorkspaceEntry`、`Workspace` 和 `Session` 完全匹配的 camelCase 字段。在每个模型上设置 `extra="forbid"`。

- [x] **步骤 4：实现只读 workspace 服务方法**

实现：

```python
list_recent_workspaces() -> list[WorkspaceEntryResponse]
list_workspaces() -> list[WorkspaceEntryResponse]
get_workspace(workspace_id: str) -> WorkspaceResponse
list_workspace_sessions(workspace_id: str) -> list[SessionResponse]
```

仅使用参数化 SQLite 查询。用 `json.loads` 转换存储的 JSON。对未知工作区抛出 `HTTPException(status_code=404, detail=f"Workspace not found: {id}")`。

- [x] **步骤 5：注册四个 workspace 路由**

```python
router = APIRouter(prefix="/api/v1")

@router.get("/workspaces/recent", response_model=list[WorkspaceEntryResponse])
def recent_workspaces(request: Request) -> list[WorkspaceEntryResponse]:
    return RuntimeService.from_request(request).list_recent_workspaces()

@router.get("/workspaces", response_model=list[WorkspaceEntryResponse])
def workspaces(request: Request) -> list[WorkspaceEntryResponse]:
    return RuntimeService.from_request(request).list_workspaces()

@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def workspace(workspace_id: str, request: Request) -> WorkspaceResponse:
    return RuntimeService.from_request(request).get_workspace(workspace_id)

@router.get("/workspaces/{workspace_id}/sessions", response_model=list[SessionResponse])
def workspace_sessions(
    workspace_id: str,
    request: Request,
) -> list[SessionResponse]:
    return RuntimeService.from_request(request).list_workspace_sessions(workspace_id)
```

- [x] **步骤 6：运行聚焦测试**

运行：`python -m pytest tests/test_workspace_api.py -q`

预期：`3 passed`。

- [x] **步骤 7：提交 workspace 合约**

```bash
git add backend
git commit -m "feat: expose workspace runtime contract"
```

## 任务 4：暴露 Task、History、Approval 和 SSE 合约

**文件：**
- 修改：`backend/app/schemas/contracts.py`
- 修改：`backend/app/api/routes.py`
- 修改：`backend/app/services/runtime.py`
- 新建：`backend/tests/test_task_api.py`
- 新建：`backend/tests/test_event_stream.py`

- [x] **步骤 1：编写 task 和 approval 测试**

```python
def test_current_task_is_pending_before_approval(client) -> None:
    response = client.get("/api/v1/sessions/session-login-validation/tasks/current")

    assert response.status_code == 200
    assert response.json()["state"] == "awaiting_approval"
    assert response.json()["changeSet"]["status"] == "pending"
    assert response.json()["verification"]["status"] == "pending"


def test_approve_changeset_updates_task_and_verification(client) -> None:
    response = client.post("/api/v1/tasks/task-login-validation/changeset/approve")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "completed"
    assert payload["changeSet"]["status"] == "approved"
    assert payload["verification"]["status"] == "passed"


def test_unknown_task_returns_not_found(client) -> None:
    response = client.post("/api/v1/tasks/missing/changeset/approve")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found: missing"}
```

- [x] **步骤 2：编写 SSE 排序测试**

```python
def test_task_events_are_replayed_in_sequence(client) -> None:
    response = client.get("/api/v1/tasks/task-login-validation/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: task.event" in response.text
    assert '"sequence":1' in response.text
    assert "event: stream.end" in response.text
```

- [x] **步骤 3：运行 task 测试，验证失败**

运行：`python -m pytest tests/test_task_api.py tests/test_event_stream.py -q`

预期：FAIL 因为 task 路由不存在，返回 HTTP 404。

- [x] **步骤 4：定义与现有前端类型匹配的响应 schema**

为以下内容定义 Pydantic 响应模型：

```text
PlanStepResponse
ToolCallResponse
ChangeSetResponse
VerificationResponse
TaskResponse
HistoryTaskEntryResponse
HistoryTaskDetailResponse
TaskEventResponse(sequence, type, payload, createdAt)
```

`TaskResponse` 必须使用 `state`、`plan`、`toolCalls`、`modelOutput`、`changeSet` 和 `verification` 字段名。`HistoryTaskDetailResponse` 必须包含 `failReason`、`failDetail`、`rejectedCmd` 和 `cancelInfo` 作为可空字段，以便前端无需类型转换即可渲染失败和取消详情。

- [x] **步骤 5：实现确定性 task 操作**

实现：

```python
get_current_task(session_id: str) -> TaskResponse
approve_changeset(task_id: str) -> TaskResponse
list_task_history(workspace_id: str) -> list[HistoryTaskEntryResponse]
get_task_detail(task_id: str) -> HistoryTaskDetailResponse
list_task_events(task_id: str) -> list[TaskEventResponse]
```

`approve_changeset` 必须执行一个 SQLite 事务，该事务：

1. 确认任务存在且处于 `awaiting_approval` 状态并有待处理的变更；
2. 将任务状态更新为 `completed`，变更集状态更新为 `approved`；
3. 写入确定性的已通过验证结果；
4. 在现有事件之后追加 `changeset.approved`、`verification.started` 和 `verification.completed` 事件，带有递增的 sequence 编号；
5. 在返回响应之前提交。

重复调用 approval 必须返回 HTTP 409，内容为：

```json
{"detail":"Change set is not pending"}
```

- [x] **步骤 6：实现路由和 SSE 格式化**

为当前任务、任务历史、任务详情和审批添加 REST 路由。使用 `StreamingResponse` 添加流路由：

```python
def encode_sse(event: TaskEventResponse) -> str:
    data = event.model_dump_json(by_alias=True)
    return f"event: task.event\ndata: {data}\n\n"
```

重放事件后，生成 `event: stream.end\ndata: {}\n\n` 并关闭。

- [x] **步骤 7：运行聚焦的 task 测试**

运行：`python -m pytest tests/test_task_api.py tests/test_event_stream.py -q`

预期：`4 passed`。

- [x] **步骤 8：提交 task 和 event 合约**

```bash
git add backend
git commit -m "feat: add task approval and event contracts"
```

## 任务 5：添加前端 HTTP 和 EventSource 服务适配器

**文件：**
- 新建：`frontend/src/config/runtime.ts`
- 新建：`frontend/src/services/http.ts`
- 新建：`frontend/src/services/event.service.ts`
- 修改：`frontend/src/services/workspace.service.ts`
- 修改：`frontend/src/services/task.service.ts`
- 修改：`frontend/src/stores/agent.store.ts`
- 修改：`frontend/src/stores/home.store.ts`
- 新建：`frontend/src/services/http.test.ts`
- 新建：`frontend/src/services/event.service.test.ts`

- [x] **步骤 1：编写前端适配器测试**

```ts
import { describe, expect, it, vi } from 'vitest'
import { requestJson } from './http'

describe('requestJson', () => {
  it('throws the API detail for a failed response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Workspace not found: missing' }),
      { status: 404, headers: { 'content-type': 'application/json' } },
    )))

    await expect(requestJson('/workspaces/missing')).rejects.toThrow(
      'Workspace not found: missing',
    )
  })
})
```

- [x] **步骤 2：运行适配器测试，验证失败**

运行：`npm run test -- src/services/http.test.ts src/services/event.service.test.ts`

预期：FAIL 因为适配器模块不存在。

- [x] **步骤 3：添加运行时配置和 JSON 辅助函数**

```ts
// frontend/src/config/runtime.ts
export const apiBaseUrl = import.meta.env.VITE_LIGHTCODE_API_BASE_URL
  ?? 'http://127.0.0.1:8000/api/v1'
```

```ts
// frontend/src/services/http.ts
export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? response.statusText)
  }
  return response.json() as Promise<T>
}
```

- [x] **步骤 4：将 Mock 和 HTTP 实现保持在同一接口之后**

将现有导出对象重命名为 `mockWorkspaceService` 和 `mockTaskService`。添加实现相同接口的 `httpWorkspaceService` 和 `httpTaskService`。首先将 workspace 接口改为使用当前路由标识而非隐式单例：

```ts
export interface WorkspaceService {
  getWorkspace(workspaceId: string): Promise<Workspace>
  getSessions(workspaceId: string): Promise<Session[]>
  getRecentWorkspaces(): Promise<WorkspaceEntry[]>
  getAllWorkspaces(): Promise<WorkspaceEntry[]>
}
```

更新 `AgentWorkspaceView` 和 `agent.store.ts`，使 `load(workspaceId: string)` 将路由参数传递给两个 workspace 方法。Mock 实现必须像 HTTP 实现一样拒绝未知工作区 ID。添加一个明确的服务选择模块：

```ts
export const workspaceService = import.meta.env.VITE_LIGHTCODE_RUNTIME === 'api'
  ? httpWorkspaceService
  : mockWorkspaceService
```

对 `taskService` 使用相同的选择模式。默认保持 Mock，直到后端开发命令被记录并运行。

- [x] **步骤 5：添加带显式清理的 EventSource 适配器**

```ts
export function subscribeTaskEvents(
  taskId: string,
  onEvent: (event: TaskEvent) => void,
  onError: (error: Event) => void,
): () => void {
  const source = new EventSource(`${apiBaseUrl}/tasks/${taskId}/events`)
  source.addEventListener('task.event', event => onEvent(JSON.parse(event.data)))
  source.addEventListener('error', onError)
  source.addEventListener('stream.end', () => source.close())
  return () => source.close()
}
```

- [x] **步骤 6：更新 stores，导入所选服务**

将 Pinia stores 中 `mockTaskService` 和 `mockWorkspaceService` 的直接导入替换为所选 `taskService` 和 `workspaceService`。更新 Agent Store 的 `load(workspaceId: string)` action，除了传递路由参数外，不改变视图层行为。Agent Store 仅在 API 模式下订阅，并在新的 load 或 store 销毁时进行清理。

- [x] **步骤 7：运行聚焦的前端测试**

运行：`npm run test -- src/services/http.test.ts src/services/event.service.test.ts src/services/task.service.test.ts src/services/workspace.service.test.ts`

预期：所有选中的测试通过。

- [x] **步骤 8：提交前端适配器**

```bash
git add frontend
git commit -m "feat: add runtime service adapters"
```

## 任务 6：集成本地运行时并验证合约

**文件：**
- 修改：`frontend/vite.config.ts`
- 修改：`frontend/README.md`
- 修改：`backend/README.md`
- 新建：`backend/tests/test_contract_shapes.py`
- 修改：`README.md`

- [x] **步骤 1：编写后端合约形状测试**

```python
def test_current_task_contract_uses_frontend_field_names(client) -> None:
    payload = client.get(
        "/api/v1/sessions/session-login-validation/tasks/current"
    ).json()

    assert set(payload) >= {
        "id", "sessionId", "title", "state", "plan", "toolCalls",
        "modelOutput", "changeSet", "verification",
    }
```

- [x] **步骤 2：运行合约测试，验证字段别名漂移时失败**

运行：`python -m pytest tests/test_contract_shapes.py -q`

预期：Task 4 之后 PASS；否则在继续之前修正响应模型。

- [x] **步骤 3：添加 Vite 开发代理**

```ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:8000',
  },
}
```

当 `VITE_LIGHTCODE_RUNTIME=api` 时，设置 `VITE_LIGHTCODE_API_BASE_URL=/api/v1`，使浏览器请求和 SSE 在开发中使用 Vite 代理。保留直接 URL 回退用于独立 API 测试。

- [x] **步骤 4：文档化确定性的本地启动方式**

后端：

```bash
python -m pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

前端 API 模式：

```bash
VITE_LIGHTCODE_RUNTIME=api VITE_LIGHTCODE_API_BASE_URL=/api/v1 npm run dev
```

Windows PowerShell：

```powershell
$env:VITE_LIGHTCODE_RUNTIME = 'api'
$env:VITE_LIGHTCODE_API_BASE_URL = '/api/v1'
npm run dev
```

- [x] **步骤 5：运行完整验证**

运行：

```bash
cd backend
python -m pytest -q
cd ../frontend
npm run test
npm run build
```

预期：所有后端测试通过，所有前端测试通过，前端生产构建成功且无警告。

- [x] **步骤 6：执行手动集成验证**

1. 以 API 模式启动后端和前端。
2. 打开 Workspace Home，确认最近工作区从 `/api/v1` 加载。
3. 打开 `login-service`，确认当前任务从 `/api/v1` 加载。
4. 批准种子变更集，确认 UI 显示验证通过。
5. 刷新页面，确认审批状态从 SQLite 持久化。
6. 打开 Session History，确认它从 `/api/v1` 加载历史记录和详情记录。
7. 确认没有端点了打开文件、写入源文件、执行命令、读取提供商密钥或从浏览器接受工作区路径。

- [x] **步骤 7：提交运行时集成**

```bash
git add README.md backend frontend
git commit -m "feat: integrate local mock runtime"
```

## 计划自审

### 规格覆盖

- FastAPI API 合约：任务 1、3 和 4。
- SQLite schema 和持久化状态：任务 2。
- 确定性 Mock 运行时和审批转换：任务 4。
- 有序 SSE 重放：任务 4。
- Mock 到 REST/SSE 的前端服务边界：任务 5。
- Phase 0 视图兼容性和手动验收：任务 6。
- 无真实工作区、模型、shell、Electron 或密钥行为：范围章节和手动验证步骤 6.7。

### 一致性检查

REST 负载使用 camelCase 以匹配现有的 TypeScript 接口。审批转换是唯一的修改操作。SSE 重放持久化事件，不模拟实时模型流。在文档记录的本地运行时命令被使用之前，Mock 保持为前端默认模式。
