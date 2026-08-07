# 会话操作菜单与管理（重命名 / 确认删除 / 列表间距）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工作区左侧会话列表增加三点操作菜单（重命名、确认后永久删除），会话行加大间距与行高，并保持项目现有纸张手绘视觉。

**Architecture:** 后端新增 `PATCH /chat-sessions/{id}`（重命名）与 `DELETE /chat-sessions/{id}?workspaceId=`（级联删除：解除任务关联 → 删消息 → 删会话，事务内），并放行 CORS 的 PATCH/DELETE；前端在 `chat.service.ts` 增加两个方法、`workspace.store.ts` 增加 `renameChatSession`/`deleteChatSession` action，`WorkspaceView.vue` 增加菜单、行内重命名表单与确认对话框。全部按 TDD（红-绿-重构）推进。

**Tech Stack:** Python/FastAPI/SQLite（后端）；Vue 3 / Pinia / Vitest / @vue/test-utils（前端）。

**规格来源：** `docs/superpowers/specs/2026-08-06-chat-session-actions-design.md`（已确认）。
**新增需求：** 每个会话行比现有 `padding: 4px 6px / font-size 12px` 稍微大一点（`8px 10px / 13px`）。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/schemas/errors.py` | 新增稳定错误码 `CHAT_SESSION_TITLE_EMPTY` |
| `backend/app/schemas/model_contracts.py` | 新增 `ChatSessionUpdateRequest`、`ChatSessionDeleteResponse` |
| `backend/app/services/chat_service.py` | 新增 `rename_session`、`delete_session` |
| `backend/app/api/routes.py` | 新增 PATCH/DELETE 路由 |
| `backend/app/main.py` | CORS `allow_methods` 放行 PATCH/DELETE |
| `backend/tests/test_chat_service.py` | 后端会话管理测试 |
| `frontend/src/contracts/real-task.schema.ts` | 新增 `parseChatDeleteResponse` |
| `frontend/src/services/chat.service.ts` | 新增 `renameChatSession`、`deleteChatSession` |
| `frontend/src/services/chat.service.test.ts` | 前端 service 测试 |
| `frontend/src/stores/workspace.store.ts` | 新增 `renameChatSession`、`deleteChatSession` |
| `frontend/src/stores/workspace.store.test.ts` | 前端 store 测试 |
| `frontend/src/views/WorkspaceView.vue` | 菜单 / 行内重命名 / 确认对话框 / 样式 |
| `frontend/src/views/WorkspaceView.test.ts` | 前端视图交互测试 |

---

### Task 1: 后端错误码与请求/响应模型

**Files:**
- Modify: `backend/app/schemas/errors.py`
- Modify: `backend/app/schemas/model_contracts.py`

- [ ] **Step 1: 实现错误码**

在 `backend/app/schemas/errors.py` 的聊天错误码区（`CHAT_BUSY = "CHAT_BUSY"` 之后）追加：

```python
CHAT_SESSION_TITLE_EMPTY = "CHAT_SESSION_TITLE_EMPTY"
```

- [ ] **Step 2: 实现 DTO**

在 `backend/app/schemas/model_contracts.py` 的 `ChatSessionCreateRequest` 之后追加：

```python
class ChatSessionUpdateRequest(BaseModel, extra="forbid"):
    """会话重命名：只允许标题，绝不携带路径/补丁/命令/密钥。"""

    title: str
```

在 `ChatSessionDetailResponse` 之后追加：

```python
class ChatSessionDeleteResponse(BaseModel, extra="forbid", populate_by_name=True):
    ok: bool
```

- [ ] **Step 3: 验证**

Run: `python -m pytest tests/test_chat_service.py -q`（在 `backend/` 目录）
Expected: 全部通过（尚无新用例，确认无回归）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/errors.py backend/app/schemas/model_contracts.py
git commit -m "feat: add chat session rename/delete DTOs and error code"
```

---

### Task 2: 后端 ChatService 重命名与级联删除

**Files:**
- Modify: `backend/app/services/chat_service.py`
- Test: `backend/tests/test_chat_service.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_chat_service.py` 的 `test_session_workspace_mismatch_rejected` 之后追加：

```python
# --- 会话重命名 -------------------------------------------------------------


def test_rename_session_updates_title(env) -> None:
    client, _ = env
    session = _create_session(client, title="旧标题")

    resp = client.patch(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "ws-chat"},
        json={"title": "新标题"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "新标题"
    assert resp.json()["updatedAt"] != session["updatedAt"]

    listed = client.get("/api/v1/workspaces/ws-chat/chat-sessions").json()
    assert listed[0]["title"] == "新标题"


def test_rename_session_rejects_empty_title(env) -> None:
    client, _ = env
    session = _create_session(client)

    resp = client.patch(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "ws-chat"},
        json={"title": "   "},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CHAT_SESSION_TITLE_EMPTY"


def test_rename_session_rejects_forbidden_fields(env) -> None:
    client, _ = env
    session = _create_session(client)

    resp = client.patch(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "ws-chat"},
        json={"title": "x", "rootPath": "C:/x", "command": "rm -rf"},
    )
    assert resp.status_code == 422  # extra="forbid"


def test_rename_missing_session_returns_404(env) -> None:
    client, _ = env
    resp = client.patch(
        "/api/v1/chat-sessions/chat-nope",
        params={"workspaceId": "ws-chat"},
        json={"title": "x"},
    )
    assert resp.status_code == 404


# --- 会话删除 ---------------------------------------------------------------


def test_delete_session_removes_messages_and_rows(env) -> None:
    client, _ = env
    session = _create_session(client)
    # 未配置 Provider：用户消息 + error 消息各落库一条
    client.post(f"/api/v1/chat-sessions/{session['id']}/messages", json={"content": "你好"})

    resp = client.delete(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "ws-chat"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # 会话 404，列表为空，消息已清空
    assert client.get(f"/api/v1/chat-sessions/{session['id']}").status_code == 404
    assert client.get("/api/v1/workspaces/ws-chat/chat-sessions").json() == []
    db = client.app.state.db
    count = db.execute(
        "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session["id"],)
    ).fetchone()[0]
    assert count == 0


def test_delete_session_unlinks_related_tasks(env) -> None:
    client, _ = env
    session = _create_session(client)
    db = client.app.state.db
    with db:
        db.execute(
            """INSERT INTO tasks
               (id, session_id, workspace_id, title, state, plan_json, tool_calls_json,
                model_output, changeset_status, verification_status, verification_command,
                verification_lines_json, kind, target_file, changeset_id,
                verification_detail, chat_session_id)
               VALUES ('t-1', 's-1', 'ws-chat', 'x', 'created', '[]', '[]', '', 'pending',
                       'pending', '', '[]', 'model', '', '', '', ?)""",
            (session["id"],),
        )

    resp = client.delete(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "ws-chat"},
    )
    assert resp.status_code == 200

    row = db.execute(
        "SELECT chat_session_id FROM tasks WHERE id = 't-1'"
    ).fetchone()
    assert row["chat_session_id"] == ""


def test_delete_session_requires_workspace_ownership(env) -> None:
    client, _ = env
    session = _create_session(client)

    resp = client.delete(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "other-ws"},
    )
    assert resp.status_code == 404
    listed = client.get("/api/v1/workspaces/ws-chat/chat-sessions").json()
    assert len(listed) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chat_service.py -q`（在 `backend/` 目录）
Expected: 新用例 FAIL —— PATCH/DELETE 路由不存在（405/404），错误码缺失。

- [ ] **Step 3: 实现 ChatService 方法**

在 `backend/app/services/chat_service.py` 的 `create_session` 之后追加：

```python
    def rename_session(
        self, session_id: str, workspace_id: str, title: str
    ) -> ChatSessionResponse:
        """重命名会话标题；先校验会话归属（404），空白标题拒绝（不回退为新会话）。"""
        self.get_session(session_id, workspace_id)  # 存在性 + 工作区归属校验（404）
        text = title.strip()
        if not text:
            raise Phase1Error(CHAT_SESSION_TITLE_EMPTY, "会话标题不能为空。")
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
                (text, now, session_id),
            )
        return self.get_session(session_id, workspace_id).session

    def delete_session(self, session_id: str, workspace_id: str) -> None:
        """永久删除会话：归属校验 → 解除任务关联 → 删消息 → 删会话（事务）。"""
        self.get_session(session_id, workspace_id)  # 归属校验，不匹配 404
        with self._db:
            self._db.execute(
                "UPDATE tasks SET chat_session_id = '' WHERE chat_session_id = ?",
                (session_id,),
            )
            self._db.execute(
                "DELETE FROM chat_messages WHERE session_id = ?", (session_id,)
            )
            self._db.execute(
                "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
            )
```

同时更新 import：在 `backend/app/services/chat_service.py` 顶部 `from app.schemas.errors import (...)` 中追加 `CHAT_SESSION_TITLE_EMPTY,`（放在 `CHAT_BUSY` 之后，保持分组风格）。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_chat_service.py -q`
Expected: 服务层无语法/导入错误；路由类用例仍失败属预期（Task 3 添加路由后全绿）。若 `pytest` 因导入错误中断，先修复 import 再继续。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chat_service.py
git commit -m "feat: add chat session rename and cascade delete service methods"
```

---

### Task 3: 后端路由与 CORS 放行

**Files:**
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_chat_service.py`

- [ ] **Step 1: 写失败测试（CORS 预检）**

在 `backend/tests/test_chat_service.py` 末尾追加：

```python
def test_cors_preflight_allows_patch_and_delete(env) -> None:
    client, _ = env
    patch = client.options(
        "/api/v1/chat-sessions/chat-x",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert patch.status_code == 200
    assert "PATCH" in patch.headers.get("access-control-allow-methods", "")

    delete = client.options(
        "/api/v1/chat-sessions/chat-x",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert "DELETE" in delete.headers.get("access-control-allow-methods", "")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_chat_service.py -q`
Expected: CORS 预检失败（allow-methods 只有 GET/POST），Task 2 的 PATCH/DELETE 用例仍失败。

- [ ] **Step 3: 实现路由**

在 `backend/app/api/routes.py` 顶部 import（`from app.schemas.model_contracts import (...)`）中追加：

```python
    ChatSessionDeleteResponse,
    ChatSessionUpdateRequest,
```

在 `submit_chat_message` 路由之后、`chat_session_events` 之前追加：

```python
@router.patch("/chat-sessions/{session_id}", response_model=ChatSessionResponse)
def rename_chat_session(
    session_id: str, payload: ChatSessionUpdateRequest, request: Request, workspaceId: str
) -> ChatSessionResponse:
    """Rename a chat session. Request body is limited to ``title`` (extra=forbid);
    workspace ownership is enforced via the required ``workspaceId`` query param."""
    return ChatService.from_request(request).rename_session(
        session_id, workspaceId, payload.title
    )


@router.delete("/chat-sessions/{session_id}", response_model=ChatSessionDeleteResponse)
def delete_chat_session(
    session_id: str, request: Request, workspaceId: str
) -> ChatSessionDeleteResponse:
    """Permanently delete a chat session (workspace ownership required)."""
    ChatService.from_request(request).delete_session(session_id, workspaceId)
    return ChatSessionDeleteResponse(ok=True)
```

- [ ] **Step 4: 放行 CORS**

在 `backend/app/main.py` 修改：

```python
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_chat_service.py -q`
Expected: 全部 PASS（含 Task 2 用例与 CORS 预检）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes.py backend/app/main.py backend/tests/test_chat_service.py
git commit -m "feat: add chat session rename/delete routes and CORS methods"
```

---

### Task 4: 前端契约校验与 service 方法

**Files:**
- Modify: `frontend/src/contracts/real-task.schema.ts`
- Modify: `frontend/src/services/chat.service.ts`
- Test: `frontend/src/services/chat.service.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/src/services/chat.service.test.ts` 的 `it('GET /chat-sessions/{id}?workspaceId=xxx 带回话与消息', ...)` 之后追加：

```ts
it('PATCH /chat-sessions/{id}?workspaceId=xxx 请求体只含 title', async () => {
  const fetchMock = stubFetch({ ...sessionPayload, title: '新标题' })
  const session = await chatService.renameChatSession('chat-abc123', 'ws-1', '新标题')
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toContain('/chat-sessions/chat-abc123?workspaceId=ws-1')
  expect(init.method).toBe('PATCH')
  const body = JSON.parse(init.body as string)
  // 后端 ChatSessionUpdateRequest 为 extra=forbid：只允许 title
  expect(Object.keys(body).sort()).toEqual(['title'])
  expect(session.title).toBe('新标题')
})

it('DELETE /chat-sessions/{id}?workspaceId=xxx 永久删除', async () => {
  const fetchMock = stubFetch({ ok: true })
  const resp = await chatService.deleteChatSession('chat-abc123', 'ws-1')
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toContain('/chat-sessions/chat-abc123?workspaceId=ws-1')
  expect(init.method).toBe('DELETE')
  expect(resp.ok).toBe(true)
})

it('DELETE 响应含 rootPath 时契约校验失败', async () => {
  stubFetch({ ok: true, rootPath: '/etc' })
  await expect(chatService.deleteChatSession('chat-abc123', 'ws-1')).rejects.toBeInstanceOf(
    ContractValidationError,
  )
})
```

- [ ] **Step 2: 运行测试确认失败**

Run（在 `frontend/` 目录）: `npm run test -- src/services/chat.service.test.ts`
Expected: FAIL —— `renameChatSession`/`deleteChatSession` 不存在。

- [ ] **Step 3: 实现契约校验**

在 `frontend/src/contracts/real-task.schema.ts` 的 `parseChatSubmitResponse` 之后追加：

```ts
export function parseChatDeleteResponse(raw: unknown): { ok: boolean } {
  if (!isObject(raw)) throw new ContractValidationError('chat delete 响应不是对象')
  if (typeof raw.ok !== 'boolean') throw new ContractValidationError('chat delete 响应缺少 ok')
  if ('rootPath' in raw || 'filePath' in raw || 'patch' in raw || 'command' in raw) {
    throw new ContractValidationError('chat delete 响应不应包含 rootPath/filePath/patch/command')
  }
  return { ok: raw.ok }
}
```

- [ ] **Step 4: 实现 service 方法**

在 `frontend/src/services/chat.service.ts`：

1. import 追加：

```ts
import { parseChatDeleteResponse, parseChatSession, parseChatSessionDetail, parseChatSubmitResponse } from '@/contracts/real-task.schema'
```

2. 接口追加：

```ts
  /** PATCH /chat-sessions/{id}?workspaceId=xxx —— 请求体只含 title */
  renameChatSession(sessionId: string, workspaceId: string, title: string): Promise<ChatSession>
  /** DELETE /chat-sessions/{id}?workspaceId=xxx（工作区归属校验，永久删除） */
  deleteChatSession(sessionId: string, workspaceId: string): Promise<{ ok: boolean }>
```

3. 实现追加（`submitMessage` 之后）：

```ts
  async renameChatSession(sessionId, workspaceId, title) {
    const raw = await requestJson<unknown>(
      `/chat-sessions/${sessionId}?workspaceId=${encodeURIComponent(workspaceId)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      },
    )
    return parseChatSession(raw)
  },

  async deleteChatSession(sessionId, workspaceId) {
    const raw = await requestJson<unknown>(
      `/chat-sessions/${sessionId}?workspaceId=${encodeURIComponent(workspaceId)}`,
      { method: 'DELETE' },
    )
    return parseChatDeleteResponse(raw)
  },
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- src/services/chat.service.test.ts`
Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/contracts/real-task.schema.ts frontend/src/services/chat.service.ts frontend/src/services/chat.service.test.ts
git commit -m "feat: add chat session rename/delete service methods"
```

---

### Task 5: 前端 store actions

**Files:**
- Modify: `frontend/src/stores/workspace.store.ts`
- Test: `frontend/src/stores/workspace.store.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/src/stores/workspace.store.test.ts`：

1. hoisted `chatMocks` 追加两个 mock：

```ts
  chatMocks: {
    listChatSessions: vi.fn(),
    createChatSession: vi.fn(),
    getChatSession: vi.fn(),
    submitMessage: vi.fn(),
    renameChatSession: vi.fn(),
    deleteChatSession: vi.fn(),
  },
```

2. 第一个 describe 的 `beforeEach` 中追加 reset：

```ts
    chatMocks.renameChatSession.mockReset().mockResolvedValue(chatSession({ title: '新标题' }))
    chatMocks.deleteChatSession.mockReset().mockResolvedValue({ ok: true })
```

3. 在第一个 describe 末尾（`切换会话后旧流事件被丢弃` 之后）追加用例：

```ts
  it('renameChatSession 成功后同步列表标题', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession(), chatSession({ id: 'chat-2', title: '第二个' })]
    chatMocks.renameChatSession.mockResolvedValue(chatSession({ title: '新标题' }))

    const ok = await store.renameChatSession('chat-1', '新标题', 'ws-1')

    expect(ok).toBe(true)
    expect(chatMocks.renameChatSession).toHaveBeenCalledWith('chat-1', 'ws-1', '新标题')
    expect(store.chatSessions[0].title).toBe('新标题')
    expect(store.chatSessions[1].title).toBe('第二个')
  })

  it('renameChatSession 失败保留原标题并返回 false', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession()]
    chatMocks.renameChatSession.mockRejectedValue(new Error('bad'))

    const ok = await store.renameChatSession('chat-1', '新标题', 'ws-1')

    expect(ok).toBe(false)
    expect(store.chatSessions[0].title).toBe('新会话')
    expect(store.error).toBeTruthy()
  })

  it('deleteChatSession 删除当前会话并切换到剩余列表第一项', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession(), chatSession({ id: 'chat-2', title: '第二个' })]
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]
    chatMocks.getChatSession.mockResolvedValue({
      session: chatSession({ id: 'chat-2' }),
      messages: [],
    })

    const ok = await store.deleteChatSession('chat-1', 'ws-1')

    expect(ok).toBe(true)
    expect(chatMocks.deleteChatSession).toHaveBeenCalledWith('chat-1', 'ws-1')
    expect(store.chatSessions.map((s) => s.id)).toEqual(['chat-2'])
    expect(store.currentSessionId).toBe('chat-2')
    const sub = captureChatSubscription()
    expect(sub.sessionId).toBe('chat-2')
    expect(sub.options.tail).toBe(true)
  })

  it('deleteChatSession 删除最后一个会话后清空状态', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession()]
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]

    const ok = await store.deleteChatSession('chat-1', 'ws-1')

    expect(ok).toBe(true)
    expect(store.chatSessions).toHaveLength(0)
    expect(store.currentSessionId).toBeNull()
    expect(store.messages).toHaveLength(0)
  })

  it('deleteChatSession 删除非当前会话不影响当前消息', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession(), chatSession({ id: 'chat-2' })]
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]

    const ok = await store.deleteChatSession('chat-2', 'ws-1')

    expect(ok).toBe(true)
    expect(store.currentSessionId).toBe('chat-1')
    expect(store.messages).toHaveLength(1)
  })

  it('deleteChatSession 失败时保留列表与当前状态', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession()]
    store.currentSessionId = 'chat-1'
    chatMocks.deleteChatSession.mockRejectedValue(new Error('bad'))

    const ok = await store.deleteChatSession('chat-1', 'ws-1')

    expect(ok).toBe(false)
    expect(store.chatSessions).toHaveLength(1)
    expect(store.currentSessionId).toBe('chat-1')
    expect(store.error).toBeTruthy()
  })
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- src/stores/workspace.store.test.ts`
Expected: 新用例 FAIL（action 不存在）。

- [ ] **Step 3: 实现 store actions**

在 `frontend/src/stores/workspace.store.ts` 的 `createChatSession` 之后追加：

```ts
    /** 重命名会话：成功后同步列表中的会话标题 */
    async renameChatSession(
      sessionId: string,
      title: string,
      workspaceId: string,
    ): Promise<boolean> {
      this.error = null
      try {
        const updated = await chatService.renameChatSession(sessionId, workspaceId, title)
        this.chatSessions = this.chatSessions.map((s) =>
          s.id === updated.id ? updated : s,
        )
        return true
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
        return false
      }
    },

    /** 永久删除会话。若删除的是当前会话：关闭旧流，有剩余会话则打开
     *  列表第一项，否则清空状态；删除非当前会话只移除对应行。 */
    async deleteChatSession(sessionId: string, workspaceId: string): Promise<boolean> {
      this.error = null
      try {
        await chatService.deleteChatSession(sessionId, workspaceId)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
        return false
      }
      const wasCurrent = this.currentSessionId === sessionId
      this.chatSessions = this.chatSessions.filter((s) => s.id !== sessionId)
      if (wasCurrent) {
        this._cleanupChatEvents()
        this.currentSessionId = null
        this.messages = []
        this.lastChatSequence = 0
        this.chatConnection = 'idle'
        const next = this.chatSessions[0]
        if (next) {
          await this.openChatSession(next.id, workspaceId)
        }
      }
      return true
    },
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- src/stores/workspace.store.test.ts`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/workspace.store.ts frontend/src/stores/workspace.store.test.ts
git commit -m "feat: add rename/delete chat session store actions"
```

---

### Task 6: WorkspaceView 会话菜单、行内重命名与确认对话框

**Files:**
- Modify: `frontend/src/views/WorkspaceView.vue`
- Test: `frontend/src/views/WorkspaceView.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/src/views/WorkspaceView.test.ts`：

1. hoisted `m.mocks` 追加：

```ts
      renameChatSession: vi.fn(),
      deleteChatSession: vi.fn(),
```

2. `vi.mock('@/services/chat.service', ...)` 追加：

```ts
    renameChatSession: m.mocks.renameChatSession,
    deleteChatSession: m.mocks.deleteChatSession,
```

3. `beforeEach` 追加默认行为：

```ts
    m.mocks.renameChatSession.mockResolvedValue({ ...m.session, title: '新标题' })
    m.mocks.deleteChatSession.mockResolvedValue({ ok: true })
```

4. 在第一个 describe 末尾追加用例：

```ts
  it('三点菜单：点击打开，再次点击关闭，Escape 关闭', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    const more = wrapper.get('[data-testid="session-more"]')
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)

    await more.trigger('click')
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(true)

    await more.trigger('click')
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)

    await more.trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)
  })

  it('重命名：回车提交新标题并同步列表', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')

    const input = wrapper.get('[data-testid="session-rename-input"]')
    expect((input.element as HTMLInputElement).value).toBe('新会话')
    await input.setValue('新标题')
    m.mocks.renameChatSession.mockResolvedValue({ ...m.session, title: '新标题' })
    await wrapper.get('[data-testid="session-rename-form"]').trigger('submit')
    await flushPromises()

    expect(m.mocks.renameChatSession).toHaveBeenCalledWith('chat-1', 'ws-1', '新标题')
    expect(wrapper.find('[data-testid="session-rename-input"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="session-row"]').text()).toContain('新标题')
  })

  it('重命名：Escape 与空白标题不提交', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()

    // Escape 取消
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await wrapper.get('[data-testid="session-rename-input"]').trigger('keydown.esc')
    expect(wrapper.find('[data-testid="session-rename-input"]').exists()).toBe(false)

    // 空白标题回车不提交
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await wrapper.get('[data-testid="session-rename-input"]').setValue('   ')
    await wrapper.get('[data-testid="session-rename-form"]').trigger('submit')
    await flushPromises()
    expect(m.mocks.renameChatSession).not.toHaveBeenCalled()
  })

  it('删除：取消不调用接口，确认后删除并从列表移除', async () => {
    m.mocks.listChatSessions.mockResolvedValue([
      m.session,
      { ...m.session, id: 'chat-2', title: '第二个' },
    ])
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="session-row"]').length).toBe(2)

    // 打开菜单 → 删除 → 取消
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-delete"]').trigger('click')
    expect(wrapper.find('[data-testid="delete-dialog"]').exists()).toBe(true)
    await wrapper.get('[data-testid="delete-cancel"]').trigger('click')
    expect(wrapper.find('[data-testid="delete-dialog"]').exists()).toBe(false)
    expect(m.mocks.deleteChatSession).not.toHaveBeenCalled()

    // 再次删除 → 确认
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-delete"]').trigger('click')
    await wrapper.get('[data-testid="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(m.mocks.deleteChatSession).toHaveBeenCalledWith('chat-1', 'ws-1')
    expect(wrapper.findAll('[data-testid="session-row"]').length).toBe(1)
  })

  it('删除进行中禁用两个对话框按钮', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-delete"]').trigger('click')

    let resolveDelete: (v: { ok: boolean }) => void = () => {}
    m.mocks.deleteChatSession.mockImplementation(
      () => new Promise((r) => { resolveDelete = r }),
    )
    await wrapper.get('[data-testid="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="delete-confirm"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="delete-cancel"]').attributes('disabled')).toBeDefined()

    resolveDelete({ ok: true })
    await flushPromises()
  })
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test -- src/views/WorkspaceView.test.ts`
Expected: 新用例 FAIL（`session-more` 等元素不存在）。

- [ ] **Step 3: 实现组件脚本**

在 `frontend/src/views/WorkspaceView.vue`：

1. import 追加 `nextTick` 与类型 `ChatSession`：

```ts
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
```

在 type import 中追加 `ChatSession`：

```ts
import type {
  ApprovalDecision,
  ChatMessage,
  ChatSession,
  ProviderStatus,
  ProviderSettingsResponse,
  RegisteredFileEntry,
} from '@/types/agent'
```

2. 在 `newSessionTitle` 附近追加状态与函数：

```ts
// 会话操作：菜单、行内重命名与删除确认
const openMenuId = ref<string | null>(null)
const editingSessionId = ref<string | null>(null)
const renameDraft = ref('')
const renaming = ref(false)
const pendingDelete = ref<ChatSession | null>(null)
const deleting = ref(false)
const renameInput = ref<HTMLInputElement | null>(null)

function toggleMenu(sessionId: string) {
  openMenuId.value = openMenuId.value === sessionId ? null : sessionId
}

function closeMenu() {
  openMenuId.value = null
}

function startRename(session: ChatSession) {
  closeMenu()
  editingSessionId.value = session.id
  renameDraft.value = session.title
  nextTick(() => {
    // v-for 内的模板 ref 在 Vue3 中收集为数组，兼容取第一个
    const el = renameInput.value
    const input = Array.isArray(el) ? el[0] : el
    input?.focus()
  })
}

function cancelRename() {
  if (renaming.value) return
  editingSessionId.value = null
  renameDraft.value = ''
}

async function commitRename(sessionId: string) {
  const title = renameDraft.value.trim()
  if (!title) {
    cancelRename()
    return
  }
  renaming.value = true
  try {
    await store.renameChatSession(sessionId, title, workspaceId.value)
  } finally {
    renaming.value = false
    editingSessionId.value = null
    renameDraft.value = ''
  }
}

function requestDelete(session: ChatSession) {
  closeMenu()
  pendingDelete.value = session
}

function cancelDelete() {
  if (deleting.value) return
  pendingDelete.value = null
}

async function confirmDelete() {
  const target = pendingDelete.value
  if (!target || deleting.value) return
  deleting.value = true
  try {
    const wasCurrent = target.id === store.currentSessionId
    const ok = await store.deleteChatSession(target.id, workspaceId.value)
    if (ok && wasCurrent) {
      const next = store.currentSessionId
      if (next) {
        router.push(`/workspace/${workspaceId.value}/session/${next}`)
      } else {
        router.push(`/workspace/${workspaceId.value}`)
      }
    }
  } finally {
    deleting.value = false
    pendingDelete.value = null
  }
}

function onGlobalKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    cancelDelete()
    cancelRename()
    closeMenu()
  }
}

function onGlobalClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.session-item')) {
    closeMenu()
    cancelRename()
  }
}
```

3. 生命周期：在 `onMounted` 末尾追加监听，`onUnmounted` 移除监听并保留 `store.cleanup()`：

```ts
onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown)
  document.addEventListener('click', onGlobalClick)
})

onUnmounted(() => {
  store.cleanup()
  document.removeEventListener('keydown', onGlobalKeydown)
  document.removeEventListener('click', onGlobalClick)
})
```

（现有 `onMounted(async () => {...})` 保持不变；新增独立 `onMounted`/`onUnmounted` 调用。）

4. `toggleNav` 中追加关闭菜单与编辑态：

```ts
function toggleNav(key: NavKey) {
  activeNav.value = activeNav.value === key ? null : key
  // 切换面板时收起旧的预览高亮
  openPreviewName.value = null
  openMenuId.value = null
  editingSessionId.value = null
}
```

- [ ] **Step 4: 实现模板**

替换现有「会话」面板中的 `session-list`（`frontend/src/views/WorkspaceView.vue` L384-L398）：

```vue
          <div class="session-list">
            <div
              v-for="s in store.chatSessions"
              :key="s.id"
              class="session-item"
              :class="{ active: s.id === store.currentSessionId }"
            >
              <button
                v-if="editingSessionId !== s.id"
                type="button"
                class="session-row"
                data-testid="session-row"
                @click="openSession(s.id)"
              >
                <span class="session-title">{{ s.title }}</span>
                <span class="session-time">{{ s.updatedAt }}</span>
              </button>
              <form
                v-else
                class="session-rename"
                data-testid="session-rename-form"
                @submit.prevent="commitRename(s.id)"
              >
                <input
                  ref="renameInput"
                  v-model="renameDraft"
                  data-testid="session-rename-input"
                  class="text-input"
                  type="text"
                  :disabled="renaming"
                  @keydown.esc.prevent="cancelRename"
                  @blur="cancelRename"
                >
              </form>
              <button
                type="button"
                class="more-btn"
                :class="{ open: openMenuId === s.id }"
                data-testid="session-more"
                :aria-expanded="openMenuId === s.id ? 'true' : 'false'"
                aria-label="会话操作"
                @click.stop="toggleMenu(s.id)"
              >⋮</button>
              <div v-if="openMenuId === s.id" class="session-menu" data-testid="session-menu">
                <button type="button" class="menu-item" data-testid="session-rename" @click="startRename(s)">
                  <span class="menu-icon" aria-hidden="true">✎</span>重命名
                </button>
                <button type="button" class="menu-item danger" data-testid="session-delete" @click="requestDelete(s)">
                  <span class="menu-icon" aria-hidden="true">⌫</span>删除会话
                </button>
              </div>
            </div>
            <p v-if="store.chatSessions.length === 0" class="empty-hint">暂无会话，新建一个开始对话</p>
          </div>
```

在 `.ws-page` 根元素末尾（`.columns` 之后、`</div>` 之前）追加确认对话框：

```vue
      <div v-if="pendingDelete" class="dialog-backdrop" data-testid="delete-dialog" @click.self="cancelDelete">
        <div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title">
          <h2 id="delete-dialog-title" class="dialog-title">删除此会话？</h2>
          <p class="dialog-copy">这会永久删除会话「{{ pendingDelete.title }}」及其中的全部消息，且无法恢复。</p>
          <div class="dialog-actions">
            <button type="button" class="dialog-btn" data-testid="delete-cancel" :disabled="deleting" @click="cancelDelete">取消</button>
            <button type="button" class="dialog-btn danger" data-testid="delete-confirm" :disabled="deleting" @click="confirmDelete">
              {{ deleting ? '删除中…' : '删除会话' }}
            </button>
          </div>
        </div>
      </div>
```

- [ ] **Step 5: 实现样式**

在 `frontend/src/views/WorkspaceView.vue` 的 `.session-time` 规则（L669）之后追加（覆盖共享行样式，使其出现在共享规则之后生效）：

```css
/* ===== 会话操作：列表间距、更大行高、菜单与确认框 ===== */
.session-list { gap: 6px; margin-top: 12px; padding-top: 8px; border-top: 1px solid #d8d0c4; }
.session-item {
  position: relative;
  display: flex; align-items: center; gap: 2px;
  border-radius: 4px; border: 1.5px solid transparent;
}
.session-item.active { background: rgba(212,160,23,.2); border-color: #c87020; }
.session-row {
  flex: 1; min-width: 0;
  padding: 8px 10px; font-size: 13px; gap: 8px;
  background: none; border: none; cursor: pointer; text-align: left;
  font-family: inherit; color: #2a2a2a;
  display: flex; align-items: center;
}
.session-item:hover .session-row { background: rgba(0,0,0,.04); }
.session-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.session-time { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #aaa; flex-shrink: 0; }
.more-btn {
  width: 28px; height: 28px; flex-shrink: 0;
  display: grid; place-items: center;
  border: 0; background: none; cursor: pointer;
  font-family: inherit; font-size: 14px; line-height: 1; color: #999;
  opacity: 0; border-radius: 4px;
}
.session-item:hover .more-btn, .more-btn:focus-visible, .more-btn.open { opacity: 1; color: #2a2a2a; }
.more-btn:hover { background: rgba(0,0,0,.05); }
.more-btn:focus-visible { outline: 1.5px solid #c87020; outline-offset: 1px; }
.session-menu {
  position: absolute; right: 0; top: calc(100% + 4px); z-index: 20;
  min-width: 140px;
  background: #f5f0e8; border: 1.5px solid #2a2a2a;
  box-shadow: 3px 3px 0 rgba(0,0,0,.12);
  padding: 4px; display: flex; flex-direction: column; gap: 2px;
}
.menu-item {
  display: flex; align-items: center; gap: 8px;
  border: 0; background: none; cursor: pointer; text-align: left;
  font-family: inherit; font-size: 13px; color: #2a2a2a;
  padding: 7px 10px; border-radius: 4px;
}
.menu-item:hover { background: rgba(0,0,0,.05); }
.menu-item.danger { color: #b83030; }
.menu-item.danger:hover { background: rgba(184,48,48,.08); }
.menu-icon { width: 16px; text-align: center; flex-shrink: 0; }
.session-rename { flex: 1; min-width: 0; padding: 5px 4px; }
.session-rename .text-input { font-size: 13px; padding: 5px 8px; }

/* ===== 删除确认对话框（项目纸张风格） ===== */
.dialog-backdrop {
  position: fixed; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center;
  background: rgba(42,42,42,.18); padding: 16px;
}
.confirm-dialog {
  width: min(100%, 360px);
  background: #f5f0e8; border: 2px solid #2a2a2a;
  box-shadow: 4px 4px 0 rgba(0,0,0,.14);
  padding: 20px 22px;
}
.dialog-title { font-family: 'Caveat', cursive; font-size: 20px; font-weight: 700; color: #1a1a1a; margin: 0 0 8px; }
.dialog-copy { font-size: 13px; line-height: 1.7; color: #444; margin: 0 0 16px; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
.dialog-btn {
  font-family: inherit; font-size: 13px; cursor: pointer;
  border: 1.5px solid #2a2a2a; border-radius: 4px; padding: 6px 14px;
  background: transparent; color: #2a2a2a;
}
.dialog-btn.danger { border-color: #b83030; color: #b83030; }
.dialog-btn.danger:hover { background: rgba(184,48,48,.08); }
.dialog-btn:disabled { opacity: .5; cursor: not-allowed; }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `npm run test -- src/views/WorkspaceView.test.ts src/views/navigation.test.ts src/stores/workspace.store.test.ts src/services/chat.service.test.ts`
Expected: 全部 PASS（含既有导航与会话面板用例；`data-testid="session-row"` 保留在可点击按钮上，导航测试不受影响）。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/WorkspaceView.vue frontend/src/views/WorkspaceView.test.ts
git commit -m "feat: add session action menu, inline rename and delete confirmation"
```

---

### Task 7: 全量验证

**Files:**
- 无（验证与修复）

- [ ] **Step 1: 后端全量测试**

Run（在 `backend/` 目录）: `python -m pytest -q`
Expected: 全部 PASS。

- [ ] **Step 2: 前端类型检查与构建**

Run（在 `frontend/` 目录）:
```bash
npm run typecheck
npm run build
```
Expected: 无类型错误，构建成功。

- [ ] **Step 3: 前端全量测试**

Run: `npm run test`
Expected: 全部 PASS，输出无警告。

- [ ] **Step 4: 手动冒烟（可选但推荐）**

启动后端与前端，打开 `http://localhost:5173`，进入工作区会话面板验证：
- 创建表单与会话列表之间有可见紧凑间隔，会话行更大。
- 悬停会话行显示三点按钮；打开菜单显示「重命名 / 删除会话」。
- 重命名：Enter 保存、Escape 取消、空白标题不提交。
- 删除：确认框出现，取消无副作用；确认后当前会话切换到剩余第一项或回到工作区空态。
- 菜单/确认框颜色、字体、边框均为项目纸张手绘风格（无黑色主题）。

- [ ] **Step 5: 若有修复则提交**

```bash
git add -A
git commit -m "fix: resolve verification issues for session actions"
```

---

## Self-Review

- **规格覆盖**：间距（Task 6 样式 `.session-list`/`.session-row`）、三点菜单（Task 6）、重命名 Enter/Escape/空白（Task 6 + 后端空标题校验 Task 2）、删除确认与禁用（Task 6）、删除后导航（Task 5 store + Task 6 路由跳转）、级联删除数据边界（Task 2 事务）、CORS 放行（Task 3）、错误安全（沿用 `store.error` 与请求体 `extra=forbid`）、前后端测试（Task 2/3/4/5/6）均已覆盖。
- **占位符扫描**：无 TBD/TODO；每个代码步骤含完整代码与预期输出。
- **类型一致性**：`renameChatSession(sessionId, title)` / `deleteChatSession(sessionId, workspaceId)` 在前端 service、store、view 三处签名一致；后端 `rename_session(session_id, title)` / `delete_session(session_id, workspace_id)` 与路由一致；`CHAT_SESSION_TITLE_EMPTY` 在 errors.py、chat_service.py、测试三处一致。
- **已知决策**：删除响应使用 `{"ok": true}` JSON（与现有 `requestJson` 兼容，避免改动 http.ts）；`data-testid="session-row"` 保留在可点击按钮上，既有测试不受影响；`.session-item` 承载 active 高亮。
