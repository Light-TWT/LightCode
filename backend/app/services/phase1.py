"""Phase 1 real-change service.

Owns the real (non-mock) task lifecycle:

    created -> planning -> reading_workspace -> generating_diff -> awaiting_approval

The read-only tools (`list_files`, `read_file`, `search_files`) and the create
flow both route every filesystem access through `WorkspaceGuard`, so no browser
input ever reaches the filesystem unchecked. Approval / atomic write / built-in
verification (states `applying_change` -> `running_verification` -> terminal) are
implemented in T5 and layered on top of this module.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.schemas.contracts import (
    ApprovalRequest,
    PlanStepResponse,
    RealChangeSetResponse,
    RealTaskResponse,
    RegisteredWorkspaceResponse,
    ToolCallResponse,
    VerificationResponse,
)
from app.schemas.errors import (
    APPLY_OUTCOME_UNKNOWN,
    APPROVAL_ALREADY_PROCESSED,
    CHANGESET_EXPIRED,
    CHANGESET_NOT_ACTIVE,
    CHANGESET_REVISION_MISMATCH,
    FILE_TYPE_DENIED,
    INVALID_STATE_TRANSITION,
    STALE_BASE,
    USER_REJECTED,
    VERIFICATION_FAILED,
    Phase1Error,
)
from app.services.atomic_write import (
    atomic_replace,
    file_lock,
    sha256_text,
    verify_written,
)
from app.services.changeset import generate_change_set
from app.security.guard import WorkspaceGuard
from app.security.policy import CHANGESET_TTL_SECONDS, MAX_DIFF_LINES
from app.workspaces.registry import WorkspaceRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


class Phase1Service:
    def __init__(
        self,
        db: sqlite3.Connection,
        registry: WorkspaceRegistry,
        guard: WorkspaceGuard,
    ) -> None:
        self._db = db
        self._registry = registry
        self._guard = guard

    @classmethod
    def from_request(cls, request: Request) -> "Phase1Service":
        state = request.app.state
        return cls(state.db, state.registry, state.guard)

    # --- Registered workspaces (public view, no root path) ---

    def list_registered_workspaces(self) -> list[RegisteredWorkspaceResponse]:
        return [
            RegisteredWorkspaceResponse(
                id=ws.id,
                displayName=ws.display_name,
                enabled=ws.enabled,
                capabilities=ws.capabilities,
                policyVersion=ws.policy_version,
            )
            for ws in self._registry.list_workspaces()
        ]

    # --- Read-only controlled tools ---

    def list_files(self, workspace_id: str, path: str = "") -> list[dict]:
        return self._guard.list_files(workspace_id, path)

    def read_file(self, workspace_id: str, path: str) -> dict:
        content = self._guard.read_text(workspace_id, path)
        return {"relativePath": path, "content": content}

    def search_files(self, workspace_id: str, query: str) -> list[dict]:
        return self._guard.search_files(workspace_id, query)

    # --- Real task lifecycle ---

    def create_real_task(
        self, workspace_id: str, title: str, template_id: str = "append-marker"
    ) -> RealTaskResponse:
        # workspace() enforces registered + enabled and raises stable Phase1Error.
        ws = self._guard.workspace(workspace_id)

        task_id = f"real-task-{uuid.uuid4().hex[:12]}"
        session_id = f"real-session-{task_id}"
        change_set_id = f"cs-{uuid.uuid4().hex[:12]}"
        now = _now()
        expires_at = ""
        if CHANGESET_TTL_SECONDS > 0:
            expires_at = (
                datetime.fromisoformat(now) + timedelta(seconds=CHANGESET_TTL_SECONDS)
            ).isoformat()

        # reading_workspace: read the server-configured target file via the guard.
        base_text = self._guard.read_text(workspace_id, ws.target_file)

        # generating_diff: deterministic server-side transform.
        try:
            generated = generate_change_set(
                logical_relative_path=ws.target_file,
                base_text=base_text,
                task_id=task_id,
                policy_version=ws.policy_version,
                template_id=template_id,
            )
        except ValueError as exc:
            raise Phase1Error(INVALID_STATE_TRANSITION, str(exc)) from exc

        # File policy: reject ChangeSets whose diff exceeds the line limit
        # (contract §文件拒绝). The limit is a policy constant, not client input.
        if generated.additions + generated.deletions > MAX_DIFF_LINES:
            raise Phase1Error(
                FILE_TYPE_DENIED, "change set exceeds the maximum diff line limit"
            )

        plan = [
            {"id": "plan", "label": "规划变更", "status": "completed"},
            {"id": "read", "label": f"读取 {ws.target_file}", "status": "completed"},
            {"id": "diff", "label": "生成 ChangeSet", "status": "completed"},
            {"id": "approve", "label": "等待审批", "status": "current"},
            {"id": "apply", "label": "原子写入", "status": "upcoming"},
            {"id": "verify", "label": "内建验证", "status": "upcoming"},
        ]
        tool_calls = [
            {
                "id": f"{task_id}-read",
                "toolName": "read_file",
                "target": ws.target_file,
                "status": "ok",
                "duration": "—",
                "detail": generated.before[:8],
            },
            {
                "id": f"{task_id}-diff",
                "toolName": "generate_diff",
                "target": f"{ws.target_file} · +{generated.additions} -{generated.deletions} · 等待审批",
                "status": "pending",
                "duration": "—",
                "detail": generated.after[-4:],
            },
        ]

        with self._db:  # transaction: all-or-nothing
            self._db.execute(
                "INSERT INTO sessions (id, workspace_id, title, status) VALUES (?, ?, ?, ?)",
                (session_id, workspace_id, title, "awaiting_approval"),
            )
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
                    workspace_id,
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
                    "awaiting_approval",
                    json.dumps(plan),
                    json.dumps(tool_calls),
                    "已读取目标文件并生成 ChangeSet，等待审批后原子写入并执行内建验证。",
                    "active",
                    "pending",
                    "builtin: utf-8 + sha256 verification",
                    json.dumps(["等待审批后运行内建验证"]),
                    "real",
                    ws.target_file,
                    change_set_id,
                    "",
                ),
            )
            self._append_events(
                task_id,
                [
                    ("task.created", {"taskId": task_id, "kind": "real"}),
                    ("task.planning", {"template": template_id}),
                    ("task.reading_workspace", {"target": ws.target_file}),
                    (
                        "task.generating_diff",
                        {
                            "changeSetId": change_set_id,
                            "additions": generated.additions,
                            "deletions": generated.deletions,
                        },
                    ),
                    ("task.awaiting_approval", {"changeSetId": change_set_id, "revision": 1}),
                ],
                now,
            )

        return self.get_real_task(task_id)

    def get_real_task(self, task_id: str) -> RealTaskResponse:
        task = self._db.execute(
            "SELECT * FROM tasks WHERE id = ? AND kind = 'real'", (task_id,)
        ).fetchone()
        if task is None:
            raise Phase1Error(
                INVALID_STATE_TRANSITION, f"real task not found: {task_id}", http_status=404
            )
        return self._row_to_real_task(task)

    # --- Approval + atomic write + built-in verification (T5) ---

    def submit_approval(self, task_id: str, approval: ApprovalRequest) -> RealTaskResponse:
        """Execute the审批与写入协议 (safety-contract §审批与写入协议).

        Ordering: validate -> record approval + applying_change (txn) -> lock +
        re-check baseline -> atomic replace -> built-in verify -> persist terminal
        state (txn). Network retries with the same idempotencyKey yield exactly one
        apply attempt.
        """
        task = self._db.execute(
            "SELECT * FROM tasks WHERE id = ? AND kind = 'real'", (task_id,)
        ).fetchone()
        if task is None:
            raise Phase1Error(
                INVALID_STATE_TRANSITION, f"real task not found: {task_id}", http_status=404
            )

        # Idempotency: a replayed request must not produce a second apply attempt.
        existing = self._db.execute(
            "SELECT * FROM approvals WHERE idempotency_key = ?",
            (approval.idempotencyKey,),
        ).fetchone()
        if existing is not None:
            if (
                existing["task_id"] != task_id
                or existing["changeset_id"] != approval.changeSetId
            ):
                raise Phase1Error(
                    APPROVAL_ALREADY_PROCESSED,
                    "idempotency key already used for a different request",
                )
            return self.get_real_task(task_id)

        # Rejection path: no file access at all.
        if approval.decision != "approve":
            return self._reject(task, approval)

        # Step 1: validate state, change set, revision, hash.
        if task["state"] != "awaiting_approval":
            raise Phase1Error(
                INVALID_STATE_TRANSITION,
                f"task is not awaiting approval (state={task['state']})",
            )
        cs = self._db.execute(
            "SELECT * FROM changesets WHERE id = ?", (approval.changeSetId,)
        ).fetchone()
        if cs is None or cs["task_id"] != task_id:
            raise Phase1Error(CHANGESET_NOT_ACTIVE, "change set not found for task")
        if cs["status"] != "active":
            raise Phase1Error(CHANGESET_NOT_ACTIVE, "change set is not active")
        if cs["revision"] != approval.revision:
            raise Phase1Error(CHANGESET_REVISION_MISMATCH, "revision mismatch")
        if cs["diff_hash"] != approval.diffHash:
            raise Phase1Error(CHANGESET_REVISION_MISMATCH, "diff hash mismatch")
        # Validity window (contract §审批与写入协议 step 1 "校验...有效期").
        if cs["expires_at"]:
            expires_dt = datetime.fromisoformat(cs["expires_at"])
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if _now_dt() > expires_dt:
                raise Phase1Error(
                    CHANGESET_EXPIRED, "change set has expired; create a fresh task"
                )

        ws = self._guard.workspace(task["workspace_id"])
        now = _now()

        # Step 2: record approval + move to applying_change in one transaction.
        with self._db:
            self._db.execute(
                """INSERT INTO approvals
                   (changeset_id, task_id, decision, revision, diff_hash,
                    idempotency_key, outcome, detail, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval.changeSetId,
                    task_id,
                    "approve",
                    approval.revision,
                    approval.diffHash,
                    approval.idempotencyKey,
                    "applying",
                    "",
                    now,
                ),
            )
            self._db.execute(
                "UPDATE tasks SET state = 'applying_change' WHERE id = ?", (task_id,)
            )
            self._append_events(
                task_id,
                [("task.applying_change", {"changeSetId": approval.changeSetId})],
                now,
            )

        # Steps 3-5: locked, re-checked, atomic write + built-in verification.
        target = self._guard.resolve(task["workspace_id"], ws.target_file)
        lock = file_lock(target)
        with lock:
            try:
                self._require_baseline(task["workspace_id"], ws.target_file, cs["base_sha256"])
            except Phase1Error as exc:
                return self._fail(task, approval.changeSetId, exc.code, exc.message)

            try:
                atomic_replace(target, cs["proposed_text"])
            except Exception as exc:  # noqa: BLE001
                # Failure before/at replace: original stays at baseline content.
                return self._fail(
                    task, approval.changeSetId, APPLY_OUTCOME_UNKNOWN, f"atomic replace failed: {exc}"
                )

            ok, message = verify_written(target, cs["proposed_sha256"])
            if not ok:
                # Attempt recovery to baseline while the process is still alive.
                return self._recover_or_unknown(
                    task, approval.changeSetId, ws.target_file, cs, message
                )

        # Step 6: persist success terminal state.
        return self._complete(task, approval.changeSetId)

    # --- Internal helpers ---

    def _require_baseline(self, workspace_id: str, target_file: str, base_sha256: str) -> None:
        """Re-validate path policy + file identity + current baseline hash.

        Raises STALE_BASE if the on-disk content diverged from the approved base.
        """
        current_text = self._guard.read_text(workspace_id, target_file)
        if sha256_text(current_text) != base_sha256:
            raise Phase1Error(STALE_BASE, "target changed since change set was generated")

    def _reject(self, task: sqlite3.Row, approval: ApprovalRequest) -> RealTaskResponse:
        now = _now()
        with self._db:
            self._db.execute(
                """INSERT INTO approvals
                   (changeset_id, task_id, decision, revision, diff_hash,
                    idempotency_key, outcome, detail, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval.changeSetId,
                    task["id"],
                    "reject",
                    approval.revision,
                    approval.diffHash,
                    approval.idempotencyKey,
                    "rejected",
                    USER_REJECTED,
                    now,
                ),
            )
            self._db.execute(
                "UPDATE tasks SET state = 'cancelled', changeset_status = 'rejected' WHERE id = ?",
                (task["id"],),
            )
            self._db.execute(
                "UPDATE changesets SET status = 'rejected' WHERE id = ?",
                (approval.changeSetId,),
            )
            self._append_events(
                task["id"],
                [("task.cancelled", {"reason": USER_REJECTED})],
                now,
            )
        return self.get_real_task(task["id"])

    def _fail(
        self, task: sqlite3.Row, change_set_id: str, code: str, message: str
    ) -> RealTaskResponse:
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE approvals SET outcome = 'failed', detail = ? WHERE idempotency_key IN "
                "(SELECT idempotency_key FROM approvals WHERE task_id = ? ORDER BY id DESC LIMIT 1)",
                (code, task["id"]),
            )
            self._db.execute(
                "UPDATE tasks SET state = 'failed', changeset_status = 'failed', "
                "verification_status = 'failed', verification_detail = ? WHERE id = ?",
                (f"{code}: {message}", task["id"]),
            )
            self._db.execute(
                "UPDATE changesets SET status = 'failed' WHERE id = ?", (change_set_id,)
            )
            self._append_events(
                task["id"],
                [("task.failed", {"code": code, "message": message})],
                now,
            )
        return self.get_real_task(task["id"])

    def _recover_or_unknown(
        self,
        task: sqlite3.Row,
        change_set_id: str,
        target_file: str,
        cs: sqlite3.Row,
        verify_message: str,
    ) -> RealTaskResponse:
        """Verification failed after write: try to restore the exact baseline.

        Restoration uses the persisted `base_text` and is confirmed by re-reading
        and re-hashing. If restoration cannot be confirmed, the outcome is marked
        APPLY_OUTCOME_UNKNOWN and further automatic writes are blocked.
        """
        target = self._guard.resolve(task["workspace_id"], target_file)
        try:
            atomic_replace(target, cs["base_text"])
            restored_hash = sha256_text(
                self._guard.read_text(task["workspace_id"], target_file)
            )
            if restored_hash != cs["base_sha256"]:
                return self._fail(
                    task, change_set_id, APPLY_OUTCOME_UNKNOWN,
                    f"verification failed and restore unconfirmed: {verify_message}",
                )
        except Exception as exc:  # noqa: BLE001
            return self._fail(
                task, change_set_id, APPLY_OUTCOME_UNKNOWN,
                f"verification failed and restore errored: {exc}",
            )
        return self._fail(
            task, change_set_id, VERIFICATION_FAILED,
            f"verification failed, baseline restored: {verify_message}",
        )

    def _complete(self, task: sqlite3.Row, change_set_id: str) -> RealTaskResponse:
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE approvals SET outcome = 'applied' WHERE idempotency_key IN "
                "(SELECT idempotency_key FROM approvals WHERE task_id = ? ORDER BY id DESC LIMIT 1)",
                (task["id"],),
            )
            self._db.execute(
                "UPDATE tasks SET state = 'completed', changeset_status = 'applied', "
                "verification_status = 'passed', verification_detail = ?, "
                "verification_lines_json = ? WHERE id = ?",
                (
                    "utf-8 ok; content hash matches proposed",
                    json.dumps(["utf-8 校验通过", "内容哈希与 proposed 一致", "原子替换成功"]),
                    task["id"],
                ),
            )
            self._db.execute(
                "UPDATE changesets SET status = 'applied' WHERE id = ?", (change_set_id,)
            )
            self._append_events(
                task["id"],
                [
                    ("task.running_verification", {"changeSetId": change_set_id}),
                    ("task.verification_completed", {"result": "passed"}),
                    ("task.completed", {"changeSetId": change_set_id}),
                ],
                now,
            )
        return self.get_real_task(task["id"])

    def _append_events(
        self, task_id: str, events: list[tuple[str, dict]], now: str
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

    def _load_change_set(self, change_set_id: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT * FROM changesets WHERE id = ?", (change_set_id,)
        ).fetchone()
        if row is None:
            raise Phase1Error(CHANGESET_NOT_ACTIVE, "change set not found")
        return row

    # --- Startup crash recovery (contract §失败和恢复承诺) ---

    def _safe_sha256(self, path: Path) -> str | None:
        """Hash the on-disk target file, or None if it is missing/unreadable."""
        try:
            return sha256_text(path.read_text(encoding="utf-8", newline=""))
        except (OSError, UnicodeDecodeError):
            return None

    def recover_incomplete_tasks(self) -> dict[str, int]:
        """Reconcile real tasks left in `applying_change` by a crashed process.

        For each stuck task, compare the on-disk target hash with the persisted
        ChangeSet to decide the outcome:
          - equals proposed_sha256 -> apply succeeded; mark `completed`.
          - equals base_sha256     -> nothing was written; reset to
            `awaiting_approval` for safe re-approval.
          - otherwise              -> unknown; block further auto-write with
            `APPLY_OUTCOME_UNKNOWN` (requires manual inspection).
        """
        rows = self._db.execute(
            "SELECT * FROM tasks WHERE kind = 'real' AND state = 'applying_change'"
        ).fetchall()
        summary = {"completed": 0, "reset": 0, "unknown": 0}
        for task in rows:
            cs = self._load_change_set(task["changeset_id"])
            target = self._guard.resolve(task["workspace_id"], task["target_file"])
            current_hash = self._safe_sha256(target)
            now = _now()
            if current_hash == cs["proposed_sha256"]:
                # Write landed but the terminal state was not persisted. The
                # built-in hash verification is implicitly satisfied.
                self._complete(task, cs["id"])
                summary["completed"] += 1
            elif current_hash == cs["base_sha256"]:
                # Nothing was written; safe to return to awaiting_approval.
                with self._db:
                    self._db.execute(
                        "UPDATE tasks SET state = 'awaiting_approval' WHERE id = ?",
                        (task["id"],),
                    )
                    self._append_events(
                        task["id"],
                        [("task.recovered", {"reason": "baseline intact; reset for re-approval"})],
                        now,
                    )
                summary["reset"] += 1
            else:
                # Diverged from both known states: outcome is unknown.
                self._fail(
                    task,
                    cs["id"],
                    APPLY_OUTCOME_UNKNOWN,
                    "process crashed during apply; on-disk hash is unknown",
                )
                summary["unknown"] += 1
        return summary

    def _row_to_real_task(self, task: sqlite3.Row) -> RealTaskResponse:
        change_set = None
        if task["changeset_id"]:
            cs = self._db.execute(
                "SELECT * FROM changesets WHERE id = ?", (task["changeset_id"],)
            ).fetchone()
            if cs is not None:
                change_set = RealChangeSetResponse(
                    changeSetId=cs["id"],
                    revision=cs["revision"],
                    diffHash=cs["diff_hash"],
                    baseSha256=cs["base_sha256"],
                    proposedSha256=cs["proposed_sha256"],
                    logicalRelativePath=cs["logical_relative_path"],
                    status=cs["status"],
                    policyVersion=cs["policy_version"],
                    additions=cs["additions"],
                    deletions=cs["deletions"],
                    before=json.loads(cs["before_json"]),
                    after=json.loads(cs["after_json"]),
                    expiresAt=cs["expires_at"] if "expires_at" in cs.keys() else None,
                )

        plan = json.loads(task["plan_json"]) if task["plan_json"] else []
        tool_calls = json.loads(task["tool_calls_json"]) if task["tool_calls_json"] else []
        verification = VerificationResponse(
            status=task["verification_status"],
            command=task["verification_command"],
            lines=json.loads(task["verification_lines_json"])
            if task["verification_lines_json"]
            else [],
        )
        created_at = self._db.execute(
            "SELECT COALESCE(MIN(created_at), '') FROM task_events WHERE task_id = ?",
            (task["id"],),
        ).fetchone()[0]

        return RealTaskResponse(
            id=task["id"],
            workspaceId=task["workspace_id"],
            sessionId=task["session_id"],
            kind=task["kind"],
            state=task["state"],
            title=task["title"],
            targetFile=task["target_file"],
            changeSet=change_set,
            plan=[PlanStepResponse(**s) for s in plan],
            toolCalls=[
                ToolCallResponse(
                    id=t["id"],
                    toolName=t["toolName"],
                    target=t["target"],
                    status=t["status"],
                    duration=t["duration"],
                    detail=t["detail"],
                )
                for t in tool_calls
            ],
            verification=verification,
            createdAt=created_at,
        )
