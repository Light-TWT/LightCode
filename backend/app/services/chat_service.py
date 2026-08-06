"""核心 Agent 更新（阶段 A）：聊天会话服务。

职责：

* 聊天会话与消息的 SQLite 持久化（``chat_sessions`` / ``chat_messages``）。
* 提交一条用户消息：先持久化用户消息，再由 ``ChatOrchestrator``（LangGraph）
  决定是"自由问答"还是"编辑任务"，最后持久化 assistant 消息。
* 编辑任务复用 ``kind='model'`` 任务 + 版本绑定审批 + 原子写入 + 内建验证。

安全边界（与 Phase 1/2 不变量一致）：

* 浏览器只提交 ``workspaceId`` + 标题/消息文本；绝不提交 rootPath/filePath/
  patch/command/key/baseUrl。
* 消息内容不保存 API Key、完整 Provider URL、原始异常诊断或不受控隐私数据。
* 模型只能通过服务端签发的 fileToken 读取文件；模型上下文不含根路径或自由路径。
* 自由问答不生成 ChangeSet；编辑意图由服务端独立校验并生成不可变 ChangeSet。
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request

from app.config.model_provider import ModelProviderConfig, build_runtime_config
from app.schemas.errors import (
    CHAT_BUSY,
    CHAT_EMPTY_MESSAGE,
    CHAT_MESSAGE_TOO_LONG,
    CHAT_MODEL_OUTPUT_INVALID,
    CHAT_SESSION_NOT_FOUND,
    CHAT_SESSION_TITLE_EMPTY,
    MODEL_RESPONSE_INVALID,
    Phase1Error,
)
from app.schemas.model_contracts import (
    ChatMessageResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatSubmitResponse,
)
from app.security.guard import WorkspaceGuard
from app.services.credential_store import ProviderCredentialStore
from app.services.model_orchestrator import (
    ChatOrchestrator,
    append_task_events,
    persist_model_outcome,
)
from app.services.openai_compatible_provider import OpenAICompatibleProvider
from app.workspaces.registry import WorkspaceRegistry

#: 单条用户/assistant 消息长度上限（字符）。
MAX_MESSAGE_CHARS = 8000
#: 发给模型的最近会话消息数（避免上下文无界增长）。
HISTORY_WINDOW = 20

#: 固定文案：失败时只渲染稳定错误码对应的说明，绝不插值服务端自由 message。
_FAILURE_TEXT: dict[str, str] = {
    "MODEL_DISABLED": "模型能力未启用，请在设置中配置 Provider。",
    "MODEL_UNCONFIGURED": "模型 Provider 尚未配置，请在设置中完成配置。",
    "MODEL_TIMEOUT": "模型 Provider 响应超时，请稍后重试。",
    "MODEL_RATE_LIMITED": "模型 Provider 触发限流，请稍后重试。",
    "MODEL_UPSTREAM_ERROR": "无法连接到模型 Provider，请检查配置。",
    "MODEL_RESPONSE_INVALID": "模型响应无法解析，请重试。",
    "MODEL_BUDGET_EXCEEDED": "本次请求超出模型资源预算。",
    "MODEL_EDIT_INVALID": "模型提出的修改不合法，已拒绝。",
    "MODEL_CONCURRENCY_EXCEEDED": "已有任务正在运行，请稍后再试。",
    "CHAT_MODEL_OUTPUT_INVALID": "模型输出不符合协议，请重试。",
    "STALE_BASE": "目标文件已变更，请重新发起任务。",
}

_EDIT_SUMMARY_TEMPLATE = (
    "已根据你的要求生成候选变更集：文件 {target}，新增 {additions} 行、删除 {deletions} 行。"
    "模型只提议，服务端校验后生成不可变变更集；请审阅并决定是否写入。"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure_text(code: str) -> str:
    return _FAILURE_TEXT.get(code, "模型任务处理失败，请重试。")


class _SessionBusy:
    """进程内单会话并发保护：同一会话同时只允许一个编排运行。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy: set[str] = set()

    def try_acquire(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._busy:
                return False
            self._busy.add(session_id)
            return True

    def release(self, session_id: str) -> None:
        with self._lock:
            self._busy.discard(session_id)


_session_busy = _SessionBusy()


def _build_chat_system_prompt(policy_version: str) -> str:
    """聊天流程的协议提示词：不含任何路径，只描述受控工具与输出协议。"""
    return f"""你是 LightCode 的本地编码智能体。你可以自由回答用户关于当前工作区的问题，也可以在用户要求修改代码时提出单文件修改建议。

# 硬性约束（不可违反）
- 你只能读取文件，不能写入、执行命令、访问网络、安装依赖或操作 Git，也不能删除/新建/重命名文件。
- 你永远不能请求真实路径、相对路径、补丁文本、命令或审批决定。
- 文件只能通过服务端签发的 fileToken 读取；fileToken 只能来自 search_files 返回的命中条目，你无法伪造。

# 可用工具（每次只输出一个 JSON 对象）
1) search_files：{{"kind":"tool_request","tool":"search_files","arguments":{{"query":"<搜索词>"}}}}
   在工作区文本中搜索关键词，返回命中条目的 fileToken、文件名与摘要片段。
2) read_file：{{"kind":"tool_request","tool":"read_file","arguments":{{"fileToken":"<search_files 返回的 token>"}}}}
   读取命中文件内容，返回 baseSha256。

# 输出协议
1) 若能直接回答用户问题：{{"kind":"answer","text":"<你的回答>"}}
2) 若需要检索代码：输出 search_files 的 tool_request。
3) 若需要读取某个命中的文件：输出 read_file 的 tool_request。
4) 若用户要求修改代码：先 read_file 获取内容与 baseSha256，再输出 candidate_edit_intent：

{{
  "kind":"candidate_edit_intent",
  "fileToken":"<你读取过的文件 token>",
  "baseSha256":"<read_file 结果中的 baseSha256>",
  "edits":[{{"expectedText":"<当前内容中唯一存在的原文片段>","replacementText":"<替换后的文本>","occurrence":1}}],
  "rationale":"<一句话理由>",
  "plan":["<步骤1>","<步骤2>"]
}}

# 规则
- edits.expectedText 必须在文件当前内容中恰好出现一次；否则服务端拒绝。
- 只能修改单个既有 UTF-8 文本文件；不能多文件、不能二进制文件。
- 回答保持简洁准确；修改前必须先 read_file 获取 baseSha256。
- 输出以 JSON 开始、以 JSON 结束；可用代码围栏包裹，但内容必须是合法 JSON。
- 策略版本：{policy_version}
"""


class ChatService:
    def __init__(
        self,
        db: Any,
        registry: WorkspaceRegistry,
        guard: WorkspaceGuard,
        env_config: ModelProviderConfig,
        credential_store: ProviderCredentialStore,
        *,
        transport: Any = None,
    ) -> None:
        self._db = db
        self._registry = registry
        self._guard = guard
        self._env_config = env_config
        self._credential_store = credential_store
        self._transport = transport

    @classmethod
    def from_request(cls, request: Request) -> "ChatService":
        state = request.app.state
        return cls(
            state.db,
            state.registry,
            state.guard,
            state.env_model_provider,
            state.credential_store,
            transport=getattr(state, "provider_transport", None),
        )

    def _effective_config(self) -> ModelProviderConfig:
        """当前生效的 Provider 配置：运行期凭据 > 环境变量。"""
        credential = self._credential_store.get()
        if credential is None:
            return self._env_config
        return build_runtime_config(self._env_config, credential)

    # --- 会话 ----------------------------------------------------------------

    def list_sessions(self, workspace_id: str) -> list[ChatSessionResponse]:
        rows = self._db.execute(
            "SELECT * FROM chat_sessions WHERE workspace_id = ? ORDER BY updated_at DESC",
            (workspace_id,),
        ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def create_session(self, workspace_id: str, title: str) -> ChatSessionResponse:
        self._guard.workspace(workspace_id)  # registered + enabled, fail-closed
        session_id = f"chat-{uuid.uuid4().hex[:12]}"
        now = _now()
        display_title = title.strip() or "新会话"
        with self._db:
            self._db.execute(
                "INSERT INTO chat_sessions (id, workspace_id, title, status, created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?)",
                (session_id, workspace_id, display_title, now, now),
            )
        return self.get_session(session_id, workspace_id).session

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

    def get_session(
        self, session_id: str, workspace_id: Optional[str] = None
    ) -> ChatSessionDetailResponse:
        row = self._db.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None or (workspace_id and row["workspace_id"] != workspace_id):
            raise Phase1Error(CHAT_SESSION_NOT_FOUND, "会话不存在。", http_status=404)
        messages = self._list_messages(session_id)
        return ChatSessionDetailResponse(
            session=self._row_to_session(row), messages=messages
        )

    def _list_messages(self, session_id: str) -> list[ChatMessageResponse]:
        rows = self._db.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY sequence ASC",
            (session_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def list_messages_after(
        self, session_id: str, after_sequence: int
    ) -> list[ChatMessageResponse]:
        """SSE 续传：返回序号 > after_sequence 的消息。"""
        rows = self._db.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? AND sequence > ? ORDER BY sequence ASC",
            (session_id, after_sequence),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def list_task_events_after(
        self, session_id: str, after_sequence: int
    ) -> list[ChatMessageResponse]:
        """EventSource protocol alias used by the chat SSE stream."""
        return self.list_messages_after(session_id, after_sequence)

    # --- 消息提交 ------------------------------------------------------------

    def submit_message(self, session_id: str, content: str) -> ChatSubmitResponse:
        detail = self.get_session(session_id)
        workspace_id = detail.session.workspaceId
        self._guard.workspace(workspace_id)

        text = content.strip()
        if not text:
            raise Phase1Error(CHAT_EMPTY_MESSAGE, "消息不能为空。")
        if len(text) > MAX_MESSAGE_CHARS:
            raise Phase1Error(
                CHAT_MESSAGE_TOO_LONG, f"消息超过 {MAX_MESSAGE_CHARS} 字符上限。", http_status=413
            )
        if not _session_busy.try_acquire(session_id):
            raise Phase1Error(CHAT_BUSY, "该会话已有消息正在处理，请稍候。", http_status=409)
        try:
            return self._run(session_id, workspace_id, text)
        finally:
            _session_busy.release(session_id)

    def _persist_message(
        self, session_id: str, role: str, content: str, kind: str = "message", task_id: str = ""
    ) -> ChatMessageResponse:
        max_seq = self._db.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM chat_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        message_id = f"msg-{uuid.uuid4().hex[:12]}"
        now = _now()
        with self._db:
            self._db.execute(
                """INSERT INTO chat_messages
                   (id, session_id, sequence, role, content, kind, task_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (message_id, session_id, max_seq + 1, role, content, kind, task_id, now),
            )
            self._db.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id)
            )
        return self._row_to_message(
            self._db.execute(
                "SELECT * FROM chat_messages WHERE id = ?", (message_id,)
            ).fetchone()
        )

    def _run(self, session_id: str, workspace_id: str, text: str) -> ChatSubmitResponse:
        # 1) 持久化用户消息（先落库，保证事件顺序）。
        self._persist_message(session_id, "user", text)

        ws = self._registry.get(workspace_id)
        policy_version = ws.policy_version if ws is not None else "unknown"

        config = self._effective_config()
        status = config.status()
        if status != "ready":
            code = (
                "MODEL_DISABLED"
                if status == "disabled"
                else "MODEL_UNCONFIGURED" if status == "unconfigured" else "MODEL_UPSTREAM_ERROR"
            )
            message = self._persist_message(session_id, "assistant", _failure_text(code), kind="error")
            return ChatSubmitResponse(message=message, taskId="")

        # 2) 构造模型上下文：系统提示 + 最近历史 + 本次消息。
        history = self._list_messages(session_id)
        recent = history[-HISTORY_WINDOW - 1 : -1]  # 不含刚写入的本次 user 消息
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _build_chat_system_prompt(policy_version)}
        ]
        for m in recent:
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": text})

        # 3) 运行聊天编排（预留 task id，仅在编辑意图出现时落库）。
        task_id = f"chat-task-{uuid.uuid4().hex[:12]}"
        orchestrator = ChatOrchestrator(
            self._db, self._registry, self._guard, config, transport=self._transport
        )
        try:
            final = orchestrator.run(
                task_id=task_id,
                workspace_id=workspace_id,
                chat_session_id=session_id,
                messages=messages,
                policy_version=policy_version,
            )
        except Phase1Error as exc:
            final = {"outcome": "failed", "error_code": exc.code, "error_message": exc.message}

        outcome = final.get("outcome")
        if outcome == "answer":
            answer = str(final.get("answer_text") or "")[:MAX_MESSAGE_CHARS]
            if not answer:
                answer = _failure_text(CHAT_MODEL_OUTPUT_INVALID)
            message = self._persist_message(session_id, "assistant", answer)
            return ChatSubmitResponse(message=message, taskId="")

        if outcome == "awaiting_approval" and final.get("generated") is not None:
            generated = final["generated"]
            target_file = str(final.get("target_file") or "")
            now = _now()
            with self._db:
                self._db.execute(
                    """INSERT INTO tasks
                       (id, session_id, workspace_id, title, state, plan_json,
                        tool_calls_json, model_output, changeset_status,
                        verification_status, verification_command, verification_lines_json,
                        kind, target_file, changeset_id, verification_detail, chat_session_id)
                       VALUES (?, ?, ?, ?, 'planning', '[]', '[]', '', 'pending', 'pending',
                               'builtin: utf-8 + sha256 verification', '[]', 'model', ?, '', '', ?)""",
                    (task_id, session_id, workspace_id, text, target_file, session_id),
                )
                append_task_events(
                    self._db,
                    task_id,
                    [("task.created", {"taskId": task_id, "kind": "model"})],
                    now,
                )
            persist_model_outcome(
                self._db,
                task_id=task_id,
                workspace_id=workspace_id,
                target_file=target_file,
                chat_session_id=session_id,
                final=final,
                now=now,
            )
            summary = _EDIT_SUMMARY_TEMPLATE.format(
                target=target_file,
                additions=generated.additions,
                deletions=generated.deletions,
            )
            message = self._persist_message(
                session_id, "assistant", summary, kind="edit_summary", task_id=task_id
            )
            return ChatSubmitResponse(message=message, taskId=task_id)

        # failed
        code = str(final.get("error_code") or MODEL_RESPONSE_INVALID)
        message = self._persist_message(
            session_id, "assistant", _failure_text(code), kind="error"
        )
        return ChatSubmitResponse(message=message, taskId="")

    # --- DTO 映射 ------------------------------------------------------------

    @staticmethod
    def _row_to_session(row: Any) -> ChatSessionResponse:
        return ChatSessionResponse(
            id=row["id"],
            workspaceId=row["workspace_id"],
            title=row["title"],
            status=row["status"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    @staticmethod
    def _row_to_message(row: Any) -> ChatMessageResponse:
        return ChatMessageResponse(
            id=row["id"],
            sessionId=row["session_id"],
            sequence=row["sequence"],
            role=row["role"],
            content=row["content"],
            kind=row["kind"],
            taskId=row["task_id"],
            createdAt=row["created_at"],
        )


__all__ = ["ChatService"]
