import json
import sqlite3
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.schemas.contracts import (
    ChangeSetResponse,
    HistoryApprovalResponse,
    HistoryFileChangeResponse,
    HistoryFileSummaryResponse,
    HistoryPlanStepResponse,
    HistoryTaskDetailResponse,
    HistoryTaskEntryResponse,
    HistoryTestResultResponse,
    HistoryTestSummaryResponse,
    HistoryToolCallResponse,
    PlanStepResponse,
    SessionResponse,
    TaskEventResponse,
    TaskResponse,
    ToolCallDetailResponse,
    ToolCallResponse,
    VerificationResponse,
    WorkspaceEntryResponse,
    WorkspaceFileResponse,
    WorkspaceResponse,
)


class RuntimeService:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    @classmethod
    def from_request(cls, request: Request) -> "RuntimeService":
        return cls(request.app.state.db)

    # --- Workspaces ---

    def list_recent_workspaces(self, limit: int = 5) -> list[WorkspaceEntryResponse]:
        rows = self._db.execute(
            "SELECT * FROM workspaces ORDER BY rowid ASC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_workspace_entry(row) for row in rows]

    def list_workspaces(self) -> list[WorkspaceEntryResponse]:
        rows = self._db.execute("SELECT * FROM workspaces").fetchall()
        return [self._row_to_workspace_entry(row) for row in rows]

    def get_workspace(self, workspace_id: str) -> WorkspaceResponse:
        row = self._db.execute(
            "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
        return WorkspaceResponse(
            id=row["id"],
            rootPath=row["root_path"],
            name=row["name"],
            files=[
                WorkspaceFileResponse(id=f"{workspace_id}-main", name=f"{row['name']}.py", kind="file"),
                WorkspaceFileResponse(id=f"{workspace_id}-test", name=f"test_{row['name']}.py", kind="file"),
            ],
        )

    def list_workspace_sessions(self, workspace_id: str) -> list[SessionResponse]:
        self._require_workspace(workspace_id)
        rows = self._db.execute(
            "SELECT id, title, status FROM sessions WHERE workspace_id = ? ORDER BY rowid ASC",
            (workspace_id,),
        ).fetchall()
        return [SessionResponse(id=row["id"], title=row["title"], status=row["status"]) for row in rows]

    # --- Tasks ---

    def get_current_task(self, session_id: str) -> TaskResponse:
        row = self._db.execute(
            "SELECT * FROM tasks WHERE session_id = ? ORDER BY rowid DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return self._row_to_task(row)

    def approve_changeset(self, task_id: str) -> TaskResponse:
        row = self._db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        # Legacy endpoint only serves Phase 0.5 mock tasks. Real Phase 1 tasks
        # must go through the guarded approval protocol, never this path.
        if row["kind"] != "mock":
            raise HTTPException(
                status_code=405,
                detail="real tasks must be approved via the Phase 1 approval endpoint",
            )
        if row["changeset_status"] != "pending":
            raise HTTPException(status_code=409, detail="Change set is not pending")

        now = datetime.now(timezone.utc).isoformat()

        max_seq = self._db.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM task_events WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]

        self._db.execute(
            "UPDATE tasks SET state = 'completed', changeset_status = 'approved', verification_status = 'passed', verification_lines_json = ? WHERE id = ?",
            (json.dumps(["3 passed in 0.12s"]), task_id),
        )

        new_events = [
            (task_id, max_seq + 1, "changeset.approved", json.dumps({"changesetId": row["id"], "status": "approved"}), now),
            (task_id, max_seq + 2, "verification.started", json.dumps({"command": "pytest test_login.py -v"}), now),
            (task_id, max_seq + 3, "verification.completed", json.dumps({"result": "passed", "detail": "3 passed in 0.12s"}), now),
        ]
        self._db.executemany(
            "INSERT INTO task_events (task_id, sequence, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            new_events,
        )
        self._db.commit()

        updated = self._db.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(updated)

    def list_task_history(self, workspace_id: str) -> list[HistoryTaskEntryResponse]:
        rows = self._db.execute(
            "SELECT * FROM task_history WHERE workspace_id = ? ORDER BY rowid ASC",
            (workspace_id,),
        ).fetchall()
        return [self._row_to_history_entry(row) for row in rows]

    def get_task_detail(self, task_id: str) -> HistoryTaskDetailResponse:
        row = self._db.execute(
            "SELECT * FROM task_history WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        base = {
            "id": row["id"],
            "status": row["status"],
            "title": row["title"],
            "time": row["time"],
            "duration": row["duration"],
            "toolCount": row["tool_count"],
            "summary": row["summary"],
        }
        detail_data = json.loads(row["detail_json"]) if row["detail_json"] else {}
        merged = {**base, **detail_data}
        return HistoryTaskDetailResponse(**merged)

    def list_task_events(self, task_id: str) -> list[TaskEventResponse]:
        return self.list_task_events_after(task_id, after_sequence=0)

    def list_task_events_after(
        self, task_id: str, after_sequence: int
    ) -> list[TaskEventResponse]:
        rows = self._db.execute(
            "SELECT sequence, event_type, payload_json, created_at FROM task_events "
            "WHERE task_id = ? AND sequence > ? ORDER BY sequence ASC",
            (task_id, after_sequence),
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> TaskEventResponse:
        return TaskEventResponse(
            sequence=row["sequence"],
            eventType=row["event_type"],
            payload=json.loads(row["payload_json"]),
            createdAt=row["created_at"],
        )

    # --- Internal ---

    def _require_workspace(self, workspace_id: str) -> None:
        row = self._db.execute(
            "SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")

    @staticmethod
    def _row_to_workspace_entry(row: sqlite3.Row) -> WorkspaceEntryResponse:
        return WorkspaceEntryResponse(
            id=row["id"],
            name=row["name"],
            rootPath=row["root_path"],
            status=row["status"],
            tags=json.loads(row["tags_json"]),
            lastTask=row["last_task"],
            timeAgo=row["time_ago"],
        )

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskResponse:
        plan = json.loads(row["plan_json"]) if "plan_json" in row.keys() else [
            {"id": "read", "label": "读取 login.py 源码", "status": "completed"},
            {"id": "analyse", "label": "分析现有登录接口", "status": "completed"},
            {"id": "diff", "label": "生成输入校验 Diff", "status": "current"},
            {"id": "apply", "label": "写入文件", "status": "upcoming"},
            {"id": "test", "label": "运行相关测试", "status": "upcoming"},
        ]
        tool_calls = json.loads(row["tool_calls_json"]) if "tool_calls_json" in row.keys() else [
            {"id": "tool-read-login", "toolName": "read_file", "target": "login.py", "status": "ok", "duration": "42ms", "detail": ["1  def login(username, password):", "2      if not username or not password:", "3          return {\"error\": \"Missing credentials\"}", "4      user = db.query(username)", "5      return {\"token\": generate_token(user)}"]},
            {"id": "tool-search-tests", "toolName": "search_files", "target": "test_login.py · 3 matches", "status": "ok", "duration": "38ms", "detail": ["test_login_empty_credentials (L12)", "test_login_valid_user (L20)", "test_login_wrong_password (L28)"]},
            {"id": "tool-generate-diff", "toolName": "generate_diff", "target": "login.py · +6 -2 · 等待审批", "status": "pending", "duration": "~120ms", "detail": ["- def login(username, password):", "+ def login(username: str, password: str) -> dict:", "+     if not isinstance(username, str) or len(username) > 64:", "+         return {\"error\": \"Invalid username\"}", "+     username = username.strip().lower()"]},
            {"id": "tool-run-tests", "toolName": "run_test", "target": "test_login.py · 等待写入后执行", "status": "idle", "duration": "—", "detail": ["等待批准修改后运行", "$ pytest test_login.py -v"]},
        ]

        change_set = {
            "id": "changeset-login-validation",
            "status": row["changeset_status"],
            "filePath": "login.py",
            "additions": 6,
            "deletions": 2,
            "before": ["def login(username, password):", "    if not username or not password:", "        return {\"error\": \"Missing credentials\"}", "    user = db.query(username)", "    return {\"token\": generate_token(user)}"],
            "after": ["def login(username: str, password: str) -> dict:", "    if not isinstance(username, str) or len(username) > 64:", "        return {\"error\": \"Invalid username\"}", "    if not isinstance(password, str) or len(password) < 8:", "        return {\"error\": \"Password too short\"}", "    username = username.strip().lower()", "    user = db.query(username)", "    return {\"token\": generate_token(user)}"],
        }

        verification_lines = json.loads(row["verification_lines_json"]) if isinstance(row["verification_lines_json"], str) else []
        verification = {
            "status": row["verification_status"],
            "command": row["verification_command"],
            "lines": verification_lines,
        }

        return TaskResponse(
            id=row["id"],
            sessionId=row["session_id"],
            title=row["title"],
            state=row["state"],
            plan=[PlanStepResponse(**s) for s in plan],
            toolCalls=[ToolCallResponse(
                id=t["id"],
                toolName=t["toolName"],
                target=t["target"],
                status=t["status"],
                duration=t["duration"],
                detail=t["detail"],
                fileSummary=ToolCallDetailResponse(**t["fileSummary"]) if t.get("fileSummary") else None,
            ) for t in tool_calls],
            modelOutput=row["model_output"],
            changeSet=ChangeSetResponse(**change_set),
            verification=VerificationResponse(**verification),
        )

    @staticmethod
    def _row_to_history_entry(row: sqlite3.Row) -> HistoryTaskEntryResponse:
        files = json.loads(row["files_json"]) if row["files_json"] else []
        test_result = json.loads(row["test_result_json"]) if row["test_result_json"] else {"badge": "none", "text": "未运行"}
        return HistoryTaskEntryResponse(
            id=row["id"],
            status=row["status"],
            title=row["title"],
            summary=row["summary"],
            time=row["time"],
            duration=row["duration"],
            toolCount=row["tool_count"],
            files=[HistoryFileSummaryResponse(**f) for f in files],
            testResult=HistoryTestSummaryResponse(**test_result),
        )
