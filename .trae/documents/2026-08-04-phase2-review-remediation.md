# Phase 2 审查问题修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实施。步骤使用 checkbox（`- [ ]`）跟踪。

**Goal:** 修复 Phase 2 审查发现的敏感信息泄露、模型上下文最小化、Provider 能力/预算、SSE 状态、前端门禁与路由归属、SSE 并发计数问题，同时保持模型仅提议、单文件审批写入与零新增依赖的边界。

**Architecture:** 后端将未知编排异常投影为固定的稳定错误，不再让自由异常文本进入 SQLite、API 或 SSE；Provider 在响应返回后本地强制输出预算。模型调用上下文仅保留 fileToken、哈希和 Guard 允许的文本，公开能力收紧为实际已接通的 `read_file`。前端订阅真实任务时持续 tail，并把模型失败 UI 绑定到错误码映射而非服务端自由文本；路由加载后验证任务工作区归属。SSE 进程内连接上限以锁保护，保持既有进程级语义。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、SQLite、LangChain/LangGraph、pytest、Vue 3、TypeScript、Pinia、Vitest。

---

## 范围与不变量

### 纳入修复

1. H-01：未知编排异常不得将密钥、Provider URL、真实路径或响应片段写入 SQLite、API、SSE 或前端。
2. M-01：真实任务 SSE 默认持续订阅（`tail=true`），`stream.end` 后连接状态必须准确。
3. M-02：只有 Provider health 明确为 `ready` 才允许创建模型任务。
4. M-03：模型任务失败 UI 只展示稳定错误码对应的固定中文提示，不渲染服务端自由 message。
5. M-04：Provider health 仅声明当前实际接通的 `read_file`。
6. M-05：本地强制执行 Provider 输出 token 预算，并对缺失 usage 的响应采用保守字节上限。
7. M-06：任务详情路由必须验证 `:workspaceId` 与 `task.workspaceId` 一致。
8. L-01：以线程锁保护 SSE 连接上限的检查、增减与读取。
9. 路径最小化：模型 system prompt 和工具结果不发送逻辑相对路径；前端披露准确说明仅发送 Guard 允许的目标文件代码片段。

### 明确不纳入

- 不新增数据库表、列、迁移或持久化租约。
- 不引入第三方依赖。
- 不实现模型侧 `search_files`；本次按已确认决策收紧对外声明为 `read_file`。
- 不改变 Phase 1 审批、原子写、ChangeSet、WorkspaceGuard、browse token 或跨进程文件写入闭环。
- 不解决多 worker 的 Metrics 聚合与模型任务跨进程并发闸；它们是权威设计已声明的 Phase 2 进程级限制，不是本次范围。
- 不执行 Shell、外部命令、包管理、网络下载、Git 写操作或模型直接写文件。

## 当前状态分析

| 问题 | 当前根因 | 修复位置 |
| --- | --- | --- |
| 异常泄露 | `ModelOrchestrator` 对 `Exception` 使用 `str(exc)`，随后持久化并产生 `task.failed` | `backend/app/services/model_orchestrator.py` |
| 输出预算 | `OpenAICompatibleProvider.chat()` 只把 `max_tokens` 交给上游，响应后不校验 usage 或内容大小 | `backend/app/services/openai_compatible_provider.py` |
| 路径最小化 | system prompt 的“逻辑文件名”和 read 工具结果的 `relativePath` 被发送至 Provider | `backend/app/services/model_orchestrator.py` |
| 能力失真 | health 的 `MODEL_ALLOWED_TOOLS` 有 `search_files`，编排器只允许 `read_file` | `backend/app/config/model_provider.py` |
| SSE 生命周期 | `real.store` 未传 `tail: true`；event service 收到 `stream.end` 只关闭 EventSource | `frontend/src/stores/real.store.ts`、`frontend/src/services/event.service.ts` |
| UI 错误直出 | `RealTaskView` 直接使用 `task.failed.payload.message` | `frontend/src/views/RealTaskView.vue` |
| Provider 门禁 | 创建按钮仅在 `degraded` 时禁用 | `frontend/src/views/RealWorkspaceView.vue` |
| 路由归属 | `RealTaskView` 按 taskId 加载但不比对 workspaceId | `frontend/src/views/RealTaskView.vue` |
| SSE 竞态 | `_active_connections` 的检查、加减不在同一锁内 | `backend/app/services/event_service.py` |

## 文件变更清单

### 后端生产代码

- 修改：`backend/app/services/model_orchestrator.py`
  - 引入固定内部编排失败消息常量。
  - 未知异常只使用固定错误码与固定消息；不插值异常内容。
  - 从 `_build_system_prompt()` 和 read 工具结果删除逻辑相对路径。
- 修改：`backend/app/services/openai_compatible_provider.py`
  - 计算本次有效输出预算。
  - 对已报告 completion tokens 超预算 fail-closed。
  - usage 缺失或不可解析时，以 UTF-8 字节长度进行保守预算检查。
- 修改：`backend/app/config/model_provider.py`
  - 把 `MODEL_ALLOWED_TOOLS` 收紧为 `("read_file",)`。
- 修改：`backend/app/services/event_service.py`
  - 使用 `threading.Lock` 保护连接计数和 Metrics 连接计数的状态转换。

### 后端测试

- 修改：`backend/tests/test_model_orchestrator.py`
  - 覆盖未知异常不泄露至创建响应、任务表、SSE payload。
  - 覆盖 Provider 请求 messages 不包含逻辑相对路径。
  - 调整健康能力测试或编排未授权工具断言，使 `search_files` 不再是“已声明能力”。
- 修改：`backend/tests/test_model_provider_http.py`
  - 覆盖已报告 completion token 超预算、usage 缺失时超字节预算。
- 修改：`backend/tests/test_event_service.py`
  - 使用两个线程和 barrier 稳定复现同一时刻的 acquire；断言连接上限严格生效且最终计数归零。
- 修改：`backend/tests/test_provider_health_api.py`
  - 断言 health 的 `capabilities.tools == ["read_file"]`。

### 前端生产代码

- 修改：`frontend/src/services/event.service.ts`
  - 扩展订阅选项，支持可选的 `onEnd` 回调。
  - 在 `stream.end` 时关闭 EventSource 后调用 `onEnd`。
- 修改：`frontend/src/stores/real.store.ts`
  - 真实任务订阅传递 `tail: true`。
  - 将 `onEnd` 映射为 `eventConnection = 'closed'`，仅在订阅仍属于当前任务且未由 cleanup/新订阅替换时更新。
- 修改：`frontend/src/views/RealTaskView.vue`
  - 定义受控错误码到固定中文提示的映射及兜底提示。
  - 失败区域只展示错误码和映射后的固定提示，不读取或渲染 `payload.message`。
  - `loadTask()` 完成后校验任务的 workspaceId；不一致时 cleanup、resetTask、设置固定路由归属错误并跳转到 `/real/<task.workspaceId>/task/<task.id>`。
- 修改：`frontend/src/views/RealWorkspaceView.vue`
  - 用 `providerReady` 替代仅 `providerDegraded` 的新建门禁。
  - 未 ready 时始终禁用创建；分别为 disabled、unconfigured、degraded、健康检查失败显示固定状态提示。
  - 继续允许已有任务的查看与审批。
  - 文字只披露 Guard 允许的目标文件代码片段会发送到 Provider，不声称或暗示会发送路径。

### 前端测试

- 修改：`frontend/src/services/event.service.test.ts`
  - 断言 `stream.end` 关闭连接并调用 onEnd。
- 修改：`frontend/src/stores/real.store.test.ts`
  - 断言 store 订阅参数含 `tail: true`。
  - 注入 stream-end 回调后断言连接状态为 `closed`。
- 修改：`frontend/src/views/RealTaskView.test.ts`
  - 注入含 Bearer、sk-、Authorization、绝对路径的失败 message；断言页面只显示固定错误码提示且不包含原字符串。
  - 构造 URL workspace 与任务 workspace 不一致，断言关闭订阅、跳转到任务实际所属工作区，并且不保留错误上下文任务。
- 修改：`frontend/src/views/RealWorkspaceView.test.ts`（从现有 `RealTaskView.test.ts` 中拆出该视图的测试，避免一个测试文件同时承载两个视图）
  - 覆盖 ready 启用。
  - 覆盖 disabled、unconfigured、degraded、health 请求失败均禁用，且真实任务创建按钮不受影响。

## 实施任务

### Task 1：先固定后端安全失败投影与模型上下文最小化

**Files:**
- Modify: `backend/tests/test_model_orchestrator.py`
- Modify: `backend/app/services/model_orchestrator.py`

- [ ] **Step 1: 添加未知异常泄露的失败回归测试**

在 `test_model_orchestrator.py` 中定义敏感测试字符串并将图调用替换为抛错：

```python
leak = "Authorization: Bearer secret-value; key=sk-abcdefghijklmnopqrstuvwxyz; root=C:\\private\\project"
orchestrator._graph = SimpleNamespace(invoke=lambda _state: (_ for _ in ()).throw(RuntimeError(leak)))
response = orchestrator.create_model_task("ws-1", "测试未知异常")
row = env["db"].execute(
    "SELECT verification_detail, model_output FROM tasks WHERE id = ?", (response.id,)
).fetchone()
events = env["db"].execute(
    "SELECT payload_json FROM task_events WHERE task_id = ?", (response.id,)
).fetchall()
serialized = "\n".join([response.detail, row["verification_detail"], row["model_output"], *(r["payload_json"] for r in events)])
assert response.state == "failed"
assert "MODEL_RESPONSE_INVALID" in serialized
assert "secret-value" not in serialized
assert "sk-abcdefghijklmnopqrstuvwxyz" not in serialized
assert "C:\\private\\project" not in serialized
assert "Authorization" not in serialized
```

- [ ] **Step 2: 运行该单测并确认当前失败**

运行：

```powershell
python -m pytest tests/test_model_orchestrator.py -k unknown_exception -q
```

预期：失败，序列化结果包含 `secret-value` 或绝对路径。

- [ ] **Step 3: 添加模型请求上下文最小化失败测试**

在现有 MockTransport handler 中捕获两次请求的 `messages`，创建 targetFile 为 `customers/acme/internal_notes.txt` 的工作区任务，并断言：

```python
serialized_messages = json.dumps(captured_messages, ensure_ascii=False)
assert "customers/acme/internal_notes.txt" not in serialized_messages
assert "relativePath:" not in serialized_messages
assert "fileToken:" in serialized_messages
assert "baseSha256:" in serialized_messages
```

- [ ] **Step 4: 运行该单测并确认当前失败**

运行：

```powershell
python -m pytest tests/test_model_orchestrator.py -k "unknown_exception or logical_path" -q
```

预期：两个用例失败；前者含自由异常，后者含逻辑路径。

- [ ] **Step 5: 实现固定内部失败投影**

在 `model_orchestrator.py` 定义并使用固定消息：

```python
_INTERNAL_ORCHESTRATION_FAILURE = "模型编排发生内部错误，已安全终止。"

except Exception:
    final = {
        "outcome": "failed",
        "error_code": MODEL_RESPONSE_INVALID,
        "error_message": _INTERNAL_ORCHESTRATION_FAILURE,
    }
```

不得记录、持久化、返回或事件化原始 `Exception` 文本。保持现有 `Phase1Error` 的稳定 code/message 路径不变。

- [ ] **Step 6: 从模型上下文移除逻辑路径**

修改 `_build_system_prompt()`：删除 `target_file` 参数、逻辑文件名段落和所有“路径”语义；仅向模型提供 fileToken 和协议约束。修改调用方为：

```python
system_prompt = _build_system_prompt(read_token, policy_version)
```

修改 read tool result 为：

```python
tool_result = (
    f"[tool_result read_file]\n"
    f"fileToken: {token}\n"
    f"baseSha256: {base_sha}\n"
    f"content:\n{content}\n"
)
```

不改服务端内部 `target_file`、ChangeSet、计划、事件和用户审查中已有的路径记录；它们不属于发往 Provider 的模型上下文。

- [ ] **Step 7: 运行聚焦测试并确认通过**

运行：

```powershell
python -m pytest tests/test_model_orchestrator.py -q
```

预期：全部通过；新用例证明未知异常和逻辑路径不会离开后端受控边界。

### Task 2：强制 Provider 输出预算

**Files:**
- Modify: `backend/tests/test_model_provider_http.py`
- Modify: `backend/app/services/openai_compatible_provider.py`

- [ ] **Step 1: 添加已报告 completion tokens 超限的失败测试**

使用 `LIGHTCODE_MODEL_MAX_OUTPUT_TOKENS="1"`，MockTransport 返回：

```python
httpx.Response(
    200,
    json={
        "choices": [{"message": {"role": "assistant", "content": "one two three four"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 4},
    },
)
```

断言：

```python
with pytest.raises(Phase1Error) as exc:
    provider.chat(MESSAGES)
assert exc.value.code == MODEL_BUDGET_EXCEEDED
```

- [ ] **Step 2: 添加 usage 缺失时的保守字节预算失败测试**

用 max output tokens 为 1 的配置，返回无 `usage` 且内容 UTF-8 字节长度大于 `max_output_tokens * 4` 的文本：

```python
content = "x" * 5
```

断言同样返回 `MODEL_BUDGET_EXCEEDED`。本计划固定保守折算为每 token 最多 4 UTF-8 字节；没有可信 usage 时，超过 `effective_max_output_tokens * 4` 的内容一律拒绝。

- [ ] **Step 3: 运行测试并确认当前失败**

运行：

```powershell
python -m pytest tests/test_model_provider_http.py -k "output or usage" -q
```

预期：失败，当前 `chat()` 返回内容。

- [ ] **Step 4: 在 Provider 中加入响应后输出预算检查**

在 `OpenAICompatibleProvider` 添加私有方法：

```python
def _check_output_budget(
    self,
    content: str,
    completion_tokens: int,
    max_output_tokens: int,
) -> None:
    if completion_tokens > 0 and completion_tokens > max_output_tokens:
        Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
        raise Phase1Error(
            MODEL_BUDGET_EXCEEDED,
            "Provider 响应超出单任务输出预算。",
            http_status=502,
        )
    if completion_tokens == 0 and len(content.encode("utf-8")) > max_output_tokens * 4:
        Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
        raise Phase1Error(
            MODEL_BUDGET_EXCEEDED,
            "Provider 响应超出单任务输出预算。",
            http_status=502,
        )
```

在 `chat()` 中计算：

```python
effective_max_output_tokens = max_output_tokens or self._config.max_output_tokens
```

将该值同时用于请求 body 和 `_check_output_budget()`。在确认 `content` 非空后、记录 success metric 前执行检查。若预算失败，沿用现有 `except Phase1Error` 路径记录 `provider.call:budget`，不得记录内容。

- [ ] **Step 5: 运行 Provider 聚焦测试**

运行：

```powershell
python -m pytest tests/test_model_provider_http.py -q
```

预期：全部通过；包括现有 timeout、429、5xx、密钥隔离和新输出预算用例。

### Task 3：收紧健康能力声明为实际可用工具

**Files:**
- Modify: `backend/app/config/model_provider.py`
- Modify: `backend/tests/test_provider_health_api.py`
- Modify: `backend/tests/test_model_orchestrator.py`

- [ ] **Step 1: 添加 health 能力失败测试**

在 `test_provider_health_api.py` 的 ready health 测试中精确断言：

```python
assert response.json()["capabilities"]["tools"] == ["read_file"]
```

- [ ] **Step 2: 运行测试并确认当前失败**

运行：

```powershell
python -m pytest tests/test_provider_health_api.py -q
```

预期：失败，当前响应还包含 `search_files`。

- [ ] **Step 3: 收紧公共能力常量**

在 `model_provider.py` 改为：

```python
MODEL_ALLOWED_TOOLS = ("read_file",)
```

不改变编排器现有 `tool != "read_file"` fail-closed 逻辑。保留模型请求 `search_files` 返回 `MODEL_EDIT_INVALID` 的负向测试，证明未声明的工具仍不能扩大读取面。

- [ ] **Step 4: 运行后端能力相关测试**

运行：

```powershell
python -m pytest tests/test_provider_health_api.py tests/test_model_orchestrator.py -q
```

预期：全部通过；health 与执行侧都只承认 `read_file`。

### Task 4：让 SSE 连接计数的进程内上限成为原子操作

**Files:**
- Modify: `backend/tests/test_event_service.py`
- Modify: `backend/app/services/event_service.py`

- [ ] **Step 1: 添加线程竞争失败测试**

在测试内重置模块计数并设置上限为 1。用 `threading.Barrier(2)` 让两个线程同时调用 `acquire_connection()`，每个成功线程等待主线程释放再调用 `release_connection()`。断言：

```python
assert success_count == 1
assert rejected_count == 1
assert event_service.active_connections() == 0
```

- [ ] **Step 2: 运行测试并确认当前实现不具备原子性**

运行：

```powershell
python -m pytest tests/test_event_service.py -k concurrent_connection_limit -q
```

预期：当前无锁实现无法提供可靠原子上限；测试应通过受控 barrier/monkeypatch 在检查与递增之间制造交错，而非依赖偶然线程调度。

- [ ] **Step 3: 用锁保护计数和指标状态转换**

在模块级增加：

```python
import threading

_connection_lock = threading.Lock()
```

将 acquire 改为：

```python
def acquire_connection() -> None:
    global _active_connections
    with _connection_lock:
        if _active_connections >= SSE_MAX_CONNECTIONS:
            raise RuntimeError("sse connection limit reached")
        _active_connections += 1
        Metrics.sse_open()
```

将 release 改为：

```python
def release_connection() -> None:
    global _active_connections
    with _connection_lock:
        if _active_connections > 0:
            _active_connections -= 1
            Metrics.sse_close()
```

将 `active_connections()` 也放在相同锁中。仅在确实有已获取连接时调用 `Metrics.sse_close()`，避免重复 release 使 gauge 漂移。

- [ ] **Step 4: 运行 SSE 服务测试**

运行：

```powershell
python -m pytest tests/test_event_service.py tests/test_observability.py -q
```

预期：全部通过；连接上限、release 和 metrics gauge 均不回归。

### Task 5：修正前端 SSE 持续订阅与连接结束状态

**Files:**
- Modify: `frontend/src/services/event.service.ts`
- Modify: `frontend/src/services/event.service.test.ts`
- Modify: `frontend/src/stores/real.store.ts`
- Modify: `frontend/src/stores/real.store.test.ts`

- [ ] **Step 1: 添加 event service 的 stream.end 回调失败测试**

将订阅 options 扩展为：

```ts
export interface SubscribeOptions {
  afterSequence?: number
  tail?: boolean
  onEnd?: () => void
}
```

测试捕获 `stream.end` listener，手动调用后断言：

```ts
expect(close).toHaveBeenCalledTimes(1)
expect(onEnd).toHaveBeenCalledTimes(1)
```

- [ ] **Step 2: 添加 store 的 tail 参数和 closed 状态失败测试**

在 mock `subscribeRealTaskEvents` 中捕获第四个参数与 `onEnd`：

```ts
expect(capturedOptions).toMatchObject({ afterSequence: 0, tail: true })
capturedOptions?.onEnd?.()
expect(store.eventConnection).toBe('closed')
```

- [ ] **Step 3: 运行前端聚焦测试并确认当前失败**

运行：

```powershell
npm run test -- --run src/services/event.service.test.ts src/stores/real.store.test.ts
```

预期：失败，store 不传 `tail`，订阅无 `onEnd`。

- [ ] **Step 4: 实现 stream.end 状态回调与持续订阅**

在 `event.service.ts` 改造 `stream.end` listener：

```ts
source.addEventListener('stream.end', () => {
  source.close()
  options?.onEnd?.()
})
```

在 `real.store.ts` 订阅 options 使用：

```ts
{
  afterSequence: this.lastSequence,
  tail: true,
  onEnd: () => {
    if (this.task?.id === taskId) {
      this.eventConnection = 'closed'
    }
  },
}
```

保留 error 回调的 `reconnecting` 语义。`onEnd` 只表示后端正常结束（包括 tail timeout），不得把它当作网络错误重试。

- [ ] **Step 5: 运行前端聚焦测试**

运行：

```powershell
npm run test -- --run src/services/event.service.test.ts src/stores/real.store.test.ts
```

预期：全部通过；真实任务 URL 始终含 `tail=true`，stream 正常结束时 UI 连接徽标显示“已关闭”。

### Task 6：前端 fail-closed Provider 门禁与无自由错误文本展示

**Files:**
- Modify: `frontend/src/views/RealWorkspaceView.vue`
- Modify: `frontend/src/views/RealTaskView.vue`
- Modify: `frontend/src/views/RealTaskView.test.ts`
- Create: `frontend/src/views/RealWorkspaceView.test.ts`

- [ ] **Step 1: 添加 Provider 全状态门禁失败测试**

把当前 `RealWorkspaceView` 相关测试迁入新文件。健康 mock 的 status 类型扩展为 `ProviderStatus | null`。针对 `disabled`、`unconfigured`、`degraded` 和 getHealth reject 分别断言：

```ts
expect(wrapper.get('[data-testid="create-model-task-btn"]').attributes('disabled')).toBeDefined()
expect(wrapper.get('[data-testid="create-task-btn"]').attributes('disabled')).toBeUndefined()
```

ready 场景仍断言模型任务按钮未禁用。对每个非 ready 状态断言存在对应固定提示，但不渲染 key、base URL 或服务器错误原文。

- [ ] **Step 2: 添加失败 message 不直出测试**

在 `RealTaskView.test.ts` 使用：

```ts
const unsafeMessage = 'Authorization: Bearer secret-value; sk-abcdefghijklmnopqrstuvwxyz; C:\\private\\project'
```

将它放进 `task.failed.payload.message`，断言：

```ts
const detail = wrapper.get('[data-testid="model-fail-detail"]').text()
expect(detail).toContain('MODEL_RESPONSE_INVALID')
expect(detail).toContain('模型输出或编排结果无效')
expect(detail).not.toContain('secret-value')
expect(detail).not.toContain('sk-abcdefghijklmnopqrstuvwxyz')
expect(detail).not.toContain('C:\\private\\project')
expect(detail).not.toContain('Authorization')
```

- [ ] **Step 3: 运行视图测试并确认当前失败**

运行：

```powershell
npm run test -- --run src/views/RealTaskView.test.ts
```

预期：失败，现有按钮允许 disabled/unconfigured，失败区域显示自由 message。

- [ ] **Step 4: 实现 Provider ready-only 门禁与准确披露**

在 `RealWorkspaceView.vue` 使用：

```ts
const providerReady = computed(() => providerStatus.value === 'ready')
const providerStatusMessage = computed(() => {
  if (providerStatus.value === 'disabled') return '模型能力未启用，不能创建模型任务。'
  if (providerStatus.value === 'unconfigured') return '模型 Provider 尚未完成后端配置，不能创建模型任务。'
  if (providerStatus.value === 'degraded') return 'Provider 配置未满足安全要求，不能创建模型任务。'
  if (providerStatus.value === null) return '无法确认 Provider 状态，已安全禁用创建模型任务。'
  return ''
})
```

模型创建按钮禁用条件为：

```vue
:disabled="store.submitting || !modelTaskTitle.trim() || !providerReady"
```

状态提示仅在 `!providerReady` 时展示。把披露文案固定为“Guard 允许的目标文件代码片段将发送至已配置的 Provider”，不提及或暗示发送路径。

- [ ] **Step 5: 实现错误码到固定 UI 文案的映射**

在 `RealTaskView.vue` 定义：

```ts
const modelFailureMessages: Record<string, string> = {
  MODEL_DISABLED: '模型能力未启用。',
  MODEL_UNCONFIGURED: '后端未完成模型 Provider 配置。',
  MODEL_TIMEOUT: '模型 Provider 响应超时。',
  MODEL_RATE_LIMITED: '模型 Provider 当前限流。',
  MODEL_UPSTREAM_ERROR: '模型 Provider 服务暂不可用。',
  MODEL_RESPONSE_INVALID: '模型输出或编排结果无效，任务已安全终止。',
  MODEL_BUDGET_EXCEEDED: '模型任务超出已配置资源预算。',
  MODEL_CONCURRENCY_EXCEEDED: '模型任务并发上限已满。',
  MODEL_EDIT_INVALID: '模型请求不符合受限编辑协议。',
  STALE_BASE: '目标文件已发生外部变更，候选变更已失效。',
}
```

让 `modelFailed` 只读取 code 并投影固定文案：

```ts
const code = String(ev.payload.code ?? '')
return {
  code: code || 'MODEL_RESPONSE_INVALID',
  message: modelFailureMessages[code] ?? '模型任务失败，未展示服务端错误详情。',
}
```

模板保持 `modelFailed.message`，但它不再来源于 `payload.message`。

- [ ] **Step 6: 运行视图聚焦测试**

运行：

```powershell
npm run test -- --run src/views/RealTaskView.test.ts src/views/RealWorkspaceView.test.ts
```

预期：全部通过；仅 ready 能创建模型任务，失败提示不含服务端自由文本。

### Task 7：校验任务详情路由工作区归属

**Files:**
- Modify: `frontend/src/views/RealTaskView.vue`
- Modify: `frontend/src/views/RealTaskView.test.ts`

- [ ] **Step 1: 添加跨工作区 taskId 路由失败测试**

让 `realTaskService.getRealTask()` 返回 `workspaceId: 'workspace-a'` 的任务，但路由为 `/real/workspace-b/task/<task-id>`。断言：

```ts
await flushPromises()
expect(router.currentRoute.value.fullPath).toBe(`/real/workspace-a/task/${modelTaskFixture.id}`)
expect(useRealStore().task).toBeNull()
expect(useRealStore().eventConnection).toBe('idle')
```

- [ ] **Step 2: 运行测试并确认当前失败**

运行：

```powershell
npm run test -- --run src/views/RealTaskView.test.ts -t "跨工作区"
```

预期：失败，当前页面会加载 task A，但仍保留 workspace B 路由。

- [ ] **Step 3: 实现加载后的归属校验与安全跳转**

将 mounted hook 改为异步函数：

```ts
onMounted(async () => {
  if (store.task?.id !== taskId.value) {
    await store.loadTask(taskId.value)
  }
  const loadedTask = store.task
  if (!loadedTask || loadedTask.workspaceId === workspaceId.value) return
  const destination = `/real/${loadedTask.workspaceId}/task/${loadedTask.id}`
  store.resetTask()
  await router.replace(destination)
})
```

不在浏览器显示跨工作区任务详情。`resetTask()` 会关闭旧 SSE 并重置事件和连接状态；目标路由重新挂载后按真实 workspace 加载。

- [ ] **Step 4: 运行视图测试**

运行：

```powershell
npm run test -- --run src/views/RealTaskView.test.ts
```

预期：全部通过；同工作区加载不受影响，错配路由自动进入真实归属路由。

### Task 8：全量回归、类型检查、构建与泄露复核

**Files:**
- 不新增生产文件。
- 如任何测试失败，仅修改其直接对应实现或测试；不得通过 skip、假成功、关闭检查或放宽安全断言绕过。

- [ ] **Step 1: 运行后端 Phase 2 聚焦回归**

运行：

```powershell
python -m pytest tests/test_model_provider_http.py tests/test_model_orchestrator.py tests/test_provider_health_api.py tests/test_event_service.py tests/test_observability.py tests/test_model_e2e.py -q
```

预期：全部通过。

- [ ] **Step 2: 运行后端全量测试**

运行：

```powershell
python -m pytest -q
```

预期：所有非既有沙箱 symlink 用例通过；保留既有 2 个合理 skipped，不新增 skip。

- [ ] **Step 3: 运行前端全量测试**

运行：

```powershell
npm run test
```

预期：全部通过。

- [ ] **Step 4: 运行前端类型检查与构建**

运行：

```powershell
npm run typecheck
npm run build -- --emptyOutDir false
```

预期：`vue-tsc -b` 与 Vite build 均通过。保留 `--emptyOutDir false`，避免 OneDrive 文件锁导致无关失败。

- [ ] **Step 5: 运行变更完整性检查**

运行：

```powershell
git diff --check
git status --short
```

预期：无空白错误；只包含本计划涉及的源代码、测试和按需同步的既有设计说明修改。不得提交 Git。

## 验收标准

1. 任意未知编排异常中的 `Bearer`、`sk-`、Provider host、绝对路径均不会出现于 HTTP 响应、SQLite 任务字段、SSE event payload 或前端失败 UI。
2. Provider 实际返回 completion token 数超过上限，或 usage 缺失且响应超过 `effectiveMaxOutputTokens * 4` UTF-8 字节时，任务以 `MODEL_BUDGET_EXCEEDED` fail-closed。
3. 真实任务 SSE URL 含 `tail=true`；服务端正常 `stream.end` 后 UI 状态为 `closed`，而非误报 `open`。
4. 仅 Provider health 为 `ready` 时能创建模型任务；其他状态和 health 请求失败均安全禁用，既有真实任务与审批不受影响。
5. 模型失败 UI 不渲染服务端 `payload.message`；只显示错误码和固定、可行动的安全提示。
6. health 工具列表严格为 `["read_file"]`，模型请求 `search_files` 仍 fail-closed。
7. 发往 Provider 的 system prompt 和 read tool result 不含逻辑相对路径；仍包含 server-issued fileToken、baseSha256 和 Guard 受控读取的内容。
8. 错配的 `/real/:workspaceId/task/:taskId` 路由不会显示跨工作区任务，而会清理本地状态并重定向至真实归属路由。
9. 同时竞争 SSE 连接上限时，成功连接数不会超过 `SSE_MAX_CONNECTIONS`，计数与 Metrics gauge 能恢复到 0。
10. 后端全量 pytest、前端 Vitest、前端 typecheck 和 build 均有本次运行证据。

## 文档同步决策

代码与测试稳定后，更新既有 `docs/phase2-model-provider-design.md`：

- 将模型工具描述从 `read_file / search_files` 收紧为当前实现的 `read_file`。
- 明确模型侧上下文只含 fileToken、哈希和 Guard 允许的文本，不含工作区根路径或逻辑相对路径。
- 保留“进程内 Metrics 与并发闸为已知限制”的现有表述，不引入跨进程方案。

不创建新文档，不修改 `AGENTS.md`，除非最终验证结果需要更新其中的测试数量或日期证据。
