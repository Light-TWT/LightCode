"""Phase 2 / WP6: model orchestration (LangGraph state machine).

The orchestrator is the **only** place where a model is allowed to influence a
ChangeSet. It enforces the server-authoritative protocol from
``docs/2026-07-30-phase-2-model-and-dx-plan.md`` §WP6:

    browser -> (workspaceId + title) -> server creates task (planning)
      -> provider proposes a read (tool_request, fileToken only)
      -> server verifies the token via WorkspaceGuard and reads the file
      -> provider proposes a candidate_edit_intent (baseSha256 + exact edits)
      -> server re-reads, validates the base hash, re-applies the edits under
         its own control and persists an immutable ChangeSet
      -> only then does the task enter `awaiting_approval`

The model never sees a path, never writes, never chooses a tool outside the
allowlist, and can never forge the bytes that land on disk. Every fail-closed
branch routes the task to `failed` with a stable machine code.

LangGraph (``langgraph.graph.StateGraph``) models the loop:
    START -> call_model -+-> (tool)   -> adjudicate_tool -> call_model
                         +-> (intent) -> adjudicate_intent -> END
                         +-> (fail)   ------------------------> END
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.config.model_provider import ModelProviderConfig
from app.schemas.errors import (
    INVALID_STATE_TRANSITION,
    MODEL_BUDGET_EXCEEDED,
    MODEL_CONCURRENCY_EXCEEDED,
    MODEL_EDIT_INVALID,
    MODEL_RESPONSE_INVALID,
    STALE_BASE,
    Phase1Error,
)
from app.schemas.model_contracts import (
    CandidateEditIntent,
    ModelTaskResponse,
    ToolRequestMessage,
)
from app.security.guard import WorkspaceGuard
from app.security.policy import CHANGESET_TTL_SECONDS
from app.services.browse_tokens import issue, verify
from app.services.changeset import build_model_change_set, sha256_text
from app.services.observability import Metrics, correlation_id_var, get_logger
from app.services.openai_compatible_provider import OpenAICompatibleProvider
from app.workspaces.registry import WorkspaceRegistry

log = get_logger("lightcode.orchestrator")


class _ModelTaskGate:
    """In-process logical write-lease for model tasks.

    Caps concurrent model tasks at ``max_concurrent_tasks`` (budget table §WP8).
    It is the Phase 2 analogue of the Phase 1 write lease: the server, not the
    model, owns the right to run. A rejected acquisition is recorded as a
    metric and routed to a stable fail-closed code.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0

    def try_acquire(self, max_concurrent: int) -> bool:
        with self._lock:
            if self._active >= max(1, max_concurrent):
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._active > 0:
                self._active -= 1

    def reset(self) -> None:
        """Test isolation only."""
        with self._lock:
            self._active = 0


#: Process-wide gate. Released in a ``finally`` after every orchestration, so a
#: crashed task can never permanently hold the slot.
_gate = _ModelTaskGate()


# Only `read_file` is wired in WP6. `search_files` is reserved for a later cut
# and is rejected if the model requests it (fail-closed, not silently allowed).
_ORCHESTRATOR_TOOLS = ("read_file",)

# Arguments the model must never be able to smuggle through a tool request.
_FORBIDDEN_ARG_KEYS = frozenset(
    {"path", "filePath", "rootPath", "patch", "command", "shell", "content", "baseSha256"}
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_fences(text: str) -> str:
    """Remove a single Markdown code fence if the model wrapped its JSON."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # drop the opening fence line (``` or ```json) and the trailing fence.
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.endswith("```"):
            stripped = stripped[: -3]
        stripped = stripped.strip()
    return stripped


class _OrchState(TypedDict, total=False):
    task_id: str
    workspace_id: str
    target_file: str
    read_token: str
    policy_version: str
    messages: list[dict]
    tool_rounds: int
    pending: Optional[str]
    outcome: Optional[str]
    generated: Any
    error_code: Optional[str]
    error_message: Optional[str]
    candidate: Any
    provider: Any


def _build_system_prompt(read_token: str, target_file: str, policy_version: str) -> str:
    """Server-authoritative protocol prompt.

    It embeds only the logical file name and the server-issued read token — never
    the real root path, never a free-form path. The model can only echo the
    token it was given, so it cannot name or forge a file to read.
    """
    return f"""你是 LightCode 的本地编码智能体（模型侧）。你只能"提议"修改，由服务端校验并生成不可变变更集，最终由用户审批。

# 硬性约束（不可违反）
- 你只能读取文件，不能写入、执行命令、访问网络、安装依赖、操作 Git，也不能删除/新建/重命名文件。
- 你永远不能请求真实路径、相对路径、补丁文本、命令或审批决定。
- 文件只能通过服务端签发的 fileToken 读取，token 由下方给出，你无法伪造。

# 唯一可请求的只读工具
- read_file：参数仅允许 {{"fileToken": "<token>"}}，token 必须是下方给出的那个。

# 你的目标文件（逻辑名，服务端权威）
- 逻辑文件名：{target_file}
- 读取它的 token：{read_token}

# 输出协议（必须严格遵守：每次只输出一个 JSON 对象，不要多余解释）
1) 先发起一次 read_file 读取目标文件，获取其内容与 baseSha256。
2) 基于读取到的内容，输出 candidate_edit_intent，对文件做精确且唯一（exact, unique）的文本替换。

tool_request 格式：
{{"kind":"tool_request","tool":"read_file","arguments":{{"fileToken":"{read_token}"}}}}

candidate_edit_intent 格式：
{{
  "kind":"candidate_edit_intent",
  "fileToken":"{read_token}",
  "baseSha256":"<上一步 read_file 结果中的 baseSha256>",
  "edits":[{{"expectedText":"<文件当前内容中唯一存在的原文片段>","replacementText":"<替换后的文本>","occurrence":1}}],
  "rationale":"<一句话理由>",
  "plan":["<步骤1>","<步骤2>"]
}}

# 规则
- edits.expectedText 必须在文件当前内容中恰好出现一次；否则服务端拒绝。
- baseSha256 必须来自 read_file 的结果，不得自行计算或猜测。
- 每次只能修改单一既有 UTF-8 文本文件；不能多文件、不能二进制文件。
- 输出以 JSON 开始、以 JSON 结束；可用代码围栏包裹，但内容必须是合法 JSON。
- 策略版本：{policy_version}
"""


class ModelOrchestrator:
    """Drives a model task through the read -> candidate -> ChangeSet loop.

    Stateless across tasks except for the injected ``db``/``guard``/``config``;
    per-task data (workspace, token, provider) travels through graph state, so a
    single instance is safe to reuse. A fresh ``OpenAICompatibleProvider`` is
    built per run so each task owns its request budget.
    """

    def __init__(
        self,
        db: Any,
        registry: WorkspaceRegistry,
        guard: WorkspaceGuard,
        config: ModelProviderConfig,
        *,
        transport: Any = None,
    ) -> None:
        self._db = db
        self._registry = registry
        self._guard = guard
        self._config = config
        self._transport = transport
        self._graph = self._build_graph()

    @classmethod
    def from_request(cls, request: Any) -> "ModelOrchestrator":
        state = request.app.state
        return cls(state.db, state.registry, state.guard, state.model_provider)

    # --- Graph construction -------------------------------------------------

    def _build_graph(self) -> Any:
        g = StateGraph(_OrchState)
        g.add_node("call_model", self._node_call_model)
        g.add_node("adjudicate_tool", self._node_adjudicate_tool)
        g.add_node("adjudicate_intent", self._node_adjudicate_intent)
        g.add_edge(START, "call_model")
        g.add_conditional_edges(
            "call_model",
            self._route,
            {
                "adjudicate_tool": "adjudicate_tool",
                "adjudicate_intent": "adjudicate_intent",
                END: END,
            },
        )
        # adjudicate_tool may succeed (loop back) or fail-closed (end). Routing
        # on the `pending` sentinel prevents a failed adjudication from looping
        # back into call_model (which would otherwise burn the request budget).
        g.add_conditional_edges(
            "adjudicate_tool",
            self._route_tool,
            {"call_model": "call_model", END: END},
        )
        g.add_edge("adjudicate_intent", END)
        return g.compile()

    @staticmethod
    def _route(state: _OrchState) -> str:
        pending = state.get("pending")
        if pending == "tool":
            return "adjudicate_tool"
        if pending == "intent":
            return "adjudicate_intent"
        return END

    @staticmethod
    def _route_tool(state: _OrchState) -> str:
        # Success sets pending='call'; any failure sets pending='failed'.
        if state.get("pending") == "call":
            return "call_model"
        return END

    # --- Nodes --------------------------------------------------------------

    def _node_call_model(self, state: _OrchState) -> dict:
        provider: OpenAICompatibleProvider = state["provider"]
        try:
            text = provider.chat(state["messages"])
        except Phase1Error as exc:
            return self._fail(state, exc.code, exc.message)
        messages = state["messages"] + [{"role": "assistant", "content": text}]
        kind, payload = self._parse_model_message(text)
        if kind == "tool":
            return {"messages": messages, "pending": "tool", "candidate": payload}
        if kind == "intent":
            return {"messages": messages, "pending": "intent", "candidate": payload}
        return self._fail(
            state,
            MODEL_RESPONSE_INVALID,
            "模型输出不符合 tool_request / candidate_edit_intent 协议。",
        )

    def _node_adjudicate_tool(self, state: _OrchState) -> dict:
        ws_id = state["workspace_id"]
        target = state["target_file"]
        req = state["candidate"]
        tool = req.get("tool")
        arguments = req.get("arguments") or {}

        # Whitelist + argument policy: the only legal read is the server-issued
        # token; no path/patch/shell/content fields may ever reach the server.
        if tool != "read_file":
            return self._fail(state, MODEL_EDIT_INVALID, f"工具不在允许列表: {tool}")
        if _FORBIDDEN_ARG_KEYS & set(arguments.keys()):
            return self._fail(state, MODEL_EDIT_INVALID, "读取参数包含被禁止的字段")
        token = arguments.get("fileToken")
        if not token:
            return self._fail(state, MODEL_EDIT_INVALID, "tool_request 缺少 fileToken")

        # Verify the token (server-authoritative path resolution). A forged or
        # wrong-operation token fails closed here.
        try:
            relative = verify(token, ws_id, "read")
        except Phase1Error:
            return self._fail(state, MODEL_EDIT_INVALID, "fileToken 校验失败")
        if relative != target:
            return self._fail(state, MODEL_EDIT_INVALID, "fileToken 指向未授权路径")

        # Tool-round budget (independent of the per-task request budget).
        if state.get("tool_rounds", 0) >= self._config.max_tool_rounds:
            Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
            return self._fail(state, MODEL_BUDGET_EXCEEDED, "读取轮次超过上限")

        t0 = time.monotonic()
        content = self._guard.read_text(ws_id, relative)
        read_ms = (time.monotonic() - t0) * 1000
        Metrics.tool_call("read_file", "model_read", read_ms)
        log.info("model tool read", extra={"task_id": state["task_id"], "target": relative, "ms": round(read_ms, 1)})
        base_sha = sha256_text(content)
        tool_result = (
            f"[tool_result read_file]\n"
            f"fileToken: {token}\n"
            f"relativePath: {relative}\n"
            f"baseSha256: {base_sha}\n"
            f"content:\n{content}\n"
        )
        messages = state["messages"] + [{"role": "user", "content": tool_result}]
        return {
            "messages": messages,
            "tool_rounds": state.get("tool_rounds", 0) + 1,
            "pending": "call",
        }

    def _node_adjudicate_intent(self, state: _OrchState) -> dict:
        ws_id = state["workspace_id"]
        target = state["target_file"]
        cand = state["candidate"]

        # The candidate must reference the exact token the server issued for the
        # target file. The model cannot forge a valid token (the secret never
        # leaves the server), so equality is the boundary.
        if cand.get("fileToken") != state["read_token"]:
            return self._fail(
                state, MODEL_EDIT_INVALID, "candidate fileToken 与授权令牌不一致"
            )

        current = self._guard.read_text(ws_id, target)
        current_sha = sha256_text(current)
        if current_sha != cand.get("baseSha256"):
            # The base diverged since the read (or the model guessed a hash).
            return self._fail(
                state, STALE_BASE, "目标文件自读取后已变更 (base hash 不匹配)"
            )

        try:
            t0 = time.monotonic()
            generated = build_model_change_set(
                logical_relative_path=target,
                base_text=current,
                edits=cand["edits"],
                task_id=state["task_id"],
                policy_version=state["policy_version"],
            )
            Metrics.tool_call("generate_diff", "server_generate", (time.monotonic() - t0) * 1000)
        except Phase1Error as exc:
            return self._fail(state, exc.code, exc.message)

        return {"pending": None, "outcome": "awaiting_approval", "generated": generated}

    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _fail(state: _OrchState, code: str, message: str) -> dict:
        return {
            "pending": "failed",
            "outcome": "failed",
            "error_code": code,
            "error_message": message,
            "messages": state.get("messages", []),
            "candidate": state.get("candidate"),
        }

    @staticmethod
    def _parse_model_message(text: str) -> tuple[str, Optional[dict]]:
        """Return ``(kind, payload)``; ``kind`` is 'tool' | 'intent' | 'invalid'."""
        try:
            data = json.loads(_strip_fences(text))
        except (json.JSONDecodeError, ValueError):
            return ("invalid", None)
        if not isinstance(data, dict):
            return ("invalid", None)
        kind = data.get("kind")
        try:
            if kind == "tool_request":
                ToolRequestMessage(**data)
                return ("tool", data)
            if kind == "candidate_edit_intent":
                CandidateEditIntent(**data)
                return ("intent", data)
        except Exception:  # noqa: BLE001 - any schema violation is a protocol error
            return ("invalid", None)
        return ("invalid", None)

    # --- Public API ---------------------------------------------------------

    def create_model_task(self, workspace_id: str, title: str) -> ModelTaskResponse:
        """Create a model task in `planning`, run the orchestration, then persist
        the outcome (awaiting_approval + ChangeSet, or failed)."""
        ws = self._guard.workspace(workspace_id)  # validates registered + enabled
        target = ws.target_file
        policy_version = ws.policy_version
        read_token = issue(workspace_id, "read", target)

        task_id = f"model-task-{uuid.uuid4().hex[:12]}"
        session_id = f"model-session-{task_id}"
        now = _now()

        # 1) Persist the planning task (no ChangeSet yet).
        with self._db:
            self._db.execute(
                "INSERT INTO sessions (id, workspace_id, title, status) VALUES (?, ?, ?, ?)",
                (session_id, workspace_id, title, "planning"),
            )
            self._db.execute(
                """INSERT INTO tasks
                   (id, session_id, workspace_id, title, state, plan_json,
                    tool_calls_json, model_output, changeset_status,
                    verification_status, verification_command, verification_lines_json,
                    kind, target_file, changeset_id, verification_detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    session_id,
                    workspace_id,
                    title,
                    "planning",
                    "[]",
                    "[]",
                    "",
                    "pending",
                    "pending",
                    "builtin: utf-8 + sha256 verification",
                    "[]",
                    "model",
                    target,
                    "",
                    "",
                ),
            )
            self._append_events(
                task_id,
                [("task.created", {"taskId": task_id, "kind": "model"})],
                now,
            )

        # 2) Enforce the model-task concurrency budget (logical write lease).
        log.info("model task planning", extra={"task_id": task_id, "workspace_id": workspace_id})
        if not _gate.try_acquire(self._config.max_concurrent_tasks):
            Metrics.concurrency_rejected()
            Metrics.task_transition("planning", "failed")
            log.warning(
                "model task rejected: concurrency limit",
                extra={"task_id": task_id, "max_concurrent": self._config.max_concurrent_tasks},
            )
            with self._db:
                self._db.execute(
                    """UPDATE tasks
                       SET state = 'failed', changeset_status = 'failed',
                           verification_status = 'failed', verification_detail = ?, model_output = ?
                       WHERE id = ?""",
                    (
                        f"{MODEL_CONCURRENCY_EXCEEDED}: 模型任务并发上限，已拒绝。",
                        "并发上限，未运行模型。",
                        task_id,
                    ),
                )
                self._append_events(
                    task_id,
                    [
                        (
                            "task.failed",
                            {
                                "code": MODEL_CONCURRENCY_EXCEEDED,
                                "message": "模型任务并发上限，已拒绝。",
                            },
                        )
                    ],
                    now,
                )
            return ModelTaskResponse(
                id=task_id,
                workspaceId=workspace_id,
                state="failed",
                changeSetId="",
                detail="模型任务并发上限，已拒绝。",
            )

        # 3) Run the orchestration graph (one provider per task = own budget).
        # The slot is always released, even on a crashed orchestration, so a
        # failed task can never permanently hold the concurrency lease.
        try:
            provider = OpenAICompatibleProvider(self._config, transport=self._transport)
            system_prompt = _build_system_prompt(read_token, target, policy_version)
            initial_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请处理任务：{title}"},
            ]
            state: _OrchState = {
                "task_id": task_id,
                "workspace_id": workspace_id,
                "target_file": target,
                "read_token": read_token,
                "policy_version": policy_version,
                "messages": initial_messages,
                "tool_rounds": 0,
                "pending": None,
                "outcome": None,
                "generated": None,
                "error_code": None,
                "error_message": None,
                "candidate": None,
                "provider": provider,
            }
            try:
                final = self._graph.invoke(state)
            except Phase1Error as exc:
                final = {"outcome": "failed", "error_code": exc.code, "error_message": exc.message}
            except Exception as exc:  # noqa: BLE001 - safety net for any runtime error
                final = {
                    "outcome": "failed",
                    "error_code": MODEL_RESPONSE_INVALID,
                    "error_message": f"编排运行异常：{exc}",
                }
        finally:
            _gate.release()

        # 4) Persist the outcome and return the read-only view.
        change_set_id = self._persist_outcome(task_id, target, final, now)
        state_str = final.get("outcome") or "failed"
        Metrics.task_transition("planning", state_str)
        if state_str == "awaiting_approval":
            detail = "模型已生成候选变更集，等待审批。"
            log.info("model task awaiting approval", extra={"task_id": task_id, "change_set_id": change_set_id})
        else:
            detail = final.get("error_message") or "模型任务失败。"
            log.warning(
                "model task failed",
                extra={"task_id": task_id, "code": final.get("error_code")},
            )
        return ModelTaskResponse(
            id=task_id,
            workspaceId=workspace_id,
            state=state_str,
            changeSetId=change_set_id,
            detail=detail,
        )

    def get_model_task(self, task_id: str) -> ModelTaskResponse:
        task = self._db.execute(
            "SELECT * FROM tasks WHERE id = ? AND kind = 'model'", (task_id,)
        ).fetchone()
        if task is None:
            raise Phase1Error(
                INVALID_STATE_TRANSITION, f"model task not found: {task_id}", http_status=404
            )
        cs_id = task["changeset_id"]
        state = task["state"]
        if state == "awaiting_approval":
            detail = "模型已生成候选变更集，等待审批。"
        elif state == "failed":
            detail = task["verification_detail"] or "模型任务失败。"
        else:
            detail = ""
        return ModelTaskResponse(
            id=task["id"],
            workspaceId=task["workspace_id"],
            state=state,
            changeSetId=cs_id,
            detail=detail,
        )

    # --- Persistence --------------------------------------------------------

    def _persist_outcome(
        self, task_id: str, target_file: str, final: Mapping[str, Any], now: str
    ) -> Optional[str]:
        if final.get("outcome") == "awaiting_approval" and final.get("generated") is not None:
            generated = final["generated"]
            change_set_id = f"cs-{uuid.uuid4().hex[:12]}"
            expires_at = ""
            if CHANGESET_TTL_SECONDS > 0:
                expires_at = (
                    datetime.fromisoformat(now) + timedelta(seconds=CHANGESET_TTL_SECONDS)
                ).isoformat()

            plan = [
                {"id": "plan", "label": "规划变更", "status": "completed"},
                {"id": "read", "label": f"读取 {target_file}", "status": "completed"},
                {"id": "diff", "label": "生成候选变更集", "status": "completed"},
                {"id": "approve", "label": "等待审批", "status": "current"},
                {"id": "apply", "label": "原子写入", "status": "upcoming"},
                {"id": "verify", "label": "内建验证", "status": "upcoming"},
            ]
            tool_calls = [
                {
                    "id": f"{task_id}-read",
                    "toolName": "read_file",
                    "target": target_file,
                    "status": "ok",
                    "duration": "—",
                    "detail": generated.before[:8],
                },
                {
                    "id": f"{task_id}-diff",
                    "toolName": "generate_diff",
                    "target": f"{target_file} · +{generated.additions} -{generated.deletions} · 等待审批",
                    "status": "pending",
                    "duration": "—",
                    "detail": generated.after[-4:],
                },
            ]
            with self._db:
                self._db.execute(
                    """INSERT INTO changesets
                       (id, task_id, workspace_id, revision, logical_relative_path,
                        base_sha256, proposed_sha256, diff_hash, policy_version, status,
                        additions, deletions, before_json, after_json,
                        base_text, proposed_text, created_at, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        change_set_id,
                        task_id,
                        final["workspace_id"],
                        1,
                        generated.logical_relative_path,
                        generated.base_sha256,
                        generated.proposed_sha256,
                        generated.diff_hash,
                        generated.policy_version,
                        "active",
                        generated.additions,
                        generated.deletions,
                        json.dumps(generated.before),
                        json.dumps(generated.after),
                        generated.base_text,
                        generated.proposed_text,
                        now,
                        expires_at,
                    ),
                )
                self._db.execute(
                    """UPDATE tasks
                       SET state = 'awaiting_approval', changeset_status = 'active',
                           target_file = ?, changeset_id = ?, plan_json = ?,
                           tool_calls_json = ?, model_output = ?,
                           verification_status = 'pending',
                           verification_lines_json = '[]', verification_detail = ''
                       WHERE id = ?""",
                    (
                        target_file,
                        change_set_id,
                        json.dumps(plan),
                        json.dumps(tool_calls),
                        "模型已读取目标文件并生成候选变更集，等待审批后原子写入。",
                        task_id,
                    ),
                )
                events: list[tuple[str, dict]] = [("task.planning", {})]
                if final.get("tool_rounds", 0) > 0:
                    events.append(("task.reading_workspace", {"target": target_file}))
                events.append(
                    (
                        "task.generating_diff",
                        {
                            "changeSetId": change_set_id,
                            "additions": generated.additions,
                            "deletions": generated.deletions,
                        },
                    )
                )
                events.append(
                    ("task.awaiting_approval", {"changeSetId": change_set_id, "revision": 1})
                )
                self._append_events(task_id, events, now)
            return change_set_id

        # Failed path.
        code = final.get("error_code") or MODEL_RESPONSE_INVALID
        message = final.get("error_message") or "模型任务失败。"
        with self._db:
            self._db.execute(
                """UPDATE tasks
                   SET state = 'failed', changeset_status = 'failed',
                       verification_status = 'failed',
                       verification_detail = ?, model_output = ?
                   WHERE id = ?""",
                (f"{code}: {message}", message, task_id),
            )
            self._append_events(
                task_id, [("task.failed", {"code": code, "message": message})], now
            )
        return None

    def _append_events(
        self, task_id: str, events: Sequence[tuple[str, dict]], now: str
    ) -> None:
        max_seq = self._db.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM task_events WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        rows = [
            (task_id, max_seq + offset + 1, event_type, json.dumps(payload), now)
            for offset, (event_type, payload) in enumerate(events)
        ]
        self._db.executemany(
            "INSERT INTO task_events (task_id, sequence, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            rows,
        )


__all__ = ["ModelOrchestrator"]
