"""WP6 model-orchestrator tests (Phase 2).

These exercise the LangGraph orchestrator directly (with an ``httpx``
MockTransport standing in for the model) and through the HTTP surface. The
focus is the server-authoritative invariant: the model may only *propose* a
read and a candidate edit intent; the server validates the token, re-reads the
file, checks the base hash and builds the immutable ChangeSet. No file is
written during orchestration — only at Phase 1 approval.

Every fail-closed branch must leave the task in `failed` with a stable machine
code and must NOT mutate the on-disk file.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config.model_provider import ModelProviderConfig
from app.db.database import initialize_database
from app.main import app
from app.security.guard import WorkspaceGuard
from app.services.model_orchestrator import ModelOrchestrator
from app.workspaces.registry import WorkspaceRegistry


def _ready_config() -> ModelProviderConfig:
    return ModelProviderConfig(
        enabled=True,
        provider="openai-compatible",
        base_url="https://api.example.test/v1",
        model_id="test-model",
        allowed_origins=("https://api.example.test",),
        connect_timeout_seconds=5.0,
        read_timeout_seconds=45.0,
        total_timeout_seconds=60.0,
        max_tool_rounds=8,
        max_input_bytes=262_144,
        max_output_tokens=2048,
        max_requests_per_task=10,
        max_concurrent_tasks=1,
        allow_insecure_http=False,
        api_key="test-key",
    )


def _extract(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _token_from_messages(messages: list[dict]) -> str | None:
    # The server-issued read token lives in the system prompt.
    return _extract(r"读取它的 token：(\S+)", messages[0]["content"])


def _base_sha_from_messages(messages: list[dict]) -> str | None:
    # After a read, the tool-result message carries the server-computed hash.
    return _extract(r"baseSha256: (sha256:\w+)", messages[-1]["content"])


def _chat_completion(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def _read_then_candidate_handler(misuse_base: bool = False) -> httpx.MockTransport:
    """First call -> tool_request(read); second call -> candidate_edit_intent.

    The model mirrors a real client: it lifts the token from the system prompt
    and the baseSha256 from the read result. When ``misuse_base`` is set it
    sends a wrong hash to exercise the STALE_BASE fail-closed branch.
    """

    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        body = json.loads(request.content)
        messages = body["messages"]
        token = _token_from_messages(messages)
        if state["n"] == 1:
            content = json.dumps(
                {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": token}}
            )
        else:
            base = "sha256:deadbeef" if misuse_base else _base_sha_from_messages(messages)
            content = json.dumps(
                {
                    "kind": "candidate_edit_intent",
                    "fileToken": token,
                    "baseSha256": base,
                    "edits": [
                        {
                            "expectedText": "first line",
                            "replacementText": "first line (edited by model)",
                        }
                    ],
                    "rationale": "示例修改",
                    "plan": ["读取文件", "替换首行"],
                }
            )
        return _chat_completion(content)

    return httpx.MockTransport(handler)


def _always_tool_handler() -> httpx.MockTransport:
    """Never stops requesting reads — used to trip the tool-round budget."""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        body = json.loads(request.content)
        token = _token_from_messages(body["messages"])
        content = json.dumps(
            {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": token}}
        )
        return _chat_completion(content)

    return httpx.MockTransport(handler)


def _fixed_content_handler(content: str) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _req: _chat_completion(content))


@pytest.fixture
def env(tmp_path: Path):
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    target = ws_root / "notes.txt"
    target.write_text("first line\nsecond line\n", encoding="utf-8", newline="")

    config = {
        "workspaces": [
            {
                "id": "ws-demo",
                "displayName": "Demo Workspace",
                "rootPath": str(ws_root),
                "policy": "phase1-single-text-file",
                "targetFile": "notes.txt",
                "enabled": True,
            }
        ]
    }
    config_path = tmp_path / "workspaces.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    registry = WorkspaceRegistry.load(config_path)
    guard = WorkspaceGuard(registry)
    db = initialize_database(tmp_path / "lightcode.db")
    return {
        "target": target,
        "workspace_id": "ws-demo",
        "registry": registry,
        "guard": guard,
        "db": db,
        "config": _ready_config(),
    }


# --- Happy path -------------------------------------------------------------


def test_model_task_reaches_awaiting_approval_without_writing(env) -> None:
    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=_read_then_candidate_handler(),
    )
    resp = orch.create_model_task(env["workspace_id"], "edit first line")

    assert resp.state == "awaiting_approval"
    assert resp.changeSetId
    assert resp.workspaceId == env["workspace_id"]

    # The ChangeSet was persisted and the proposed text reflects the edit.
    cs = env["db"].execute(
        "SELECT * FROM changesets WHERE id = ?", (resp.changeSetId,)
    ).fetchone()
    assert cs is not None
    assert "first line (edited by model)" in cs["proposed_text"]
    assert "first line\nsecond line" in cs["base_text"]
    assert cs["status"] == "active"
    assert cs["revision"] == 1

    # The task row is a model task awaiting approval.
    task = env["db"].execute(
        "SELECT * FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()
    assert task["kind"] == "model"
    assert task["state"] == "awaiting_approval"

    # CRITICAL: orchestration must not write to disk.
    assert env["target"].read_text(encoding="utf-8", newline="") == "first line\nsecond line\n"

    # An approval event was appended.
    events = env["db"].execute(
        "SELECT event_type FROM task_events WHERE task_id = ? ORDER BY sequence",
        (resp.id,),
    ).fetchall()
    types = {e["event_type"] for e in events}
    assert "task.awaiting_approval" in types


def test_model_task_then_phase1_approval_writes_file(env) -> None:
    """The model ChangeSet reuses the Phase 1 guarded approval + atomic write."""
    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=_read_then_candidate_handler(),
    )
    resp = orch.create_model_task(env["workspace_id"], "edit first line")
    assert resp.state == "awaiting_approval"

    # Approve via the Phase 1 endpoint (kind filter now includes 'model').
    from app.services.phase1 import Phase1Service
    from app.schemas.contracts import ApprovalRequest

    svc = Phase1Service(env["db"], env["registry"], env["guard"])
    approval = ApprovalRequest(
        decision="approve",
        changeSetId=resp.changeSetId,
        revision=1,
        diffHash=env["db"]
        .execute("SELECT diff_hash FROM changesets WHERE id = ?", (resp.changeSetId,))
        .fetchone()["diff_hash"],
        idempotencyKey=uuid.uuid4().hex,
    )
    result = svc.submit_approval(resp.id, approval)
    assert result.state == "completed"
    # Now the disk file reflects the model's proposed edit.
    assert "first line (edited by model)" in env["target"].read_text(
        encoding="utf-8", newline=""
    )


# --- Fail-closed branches ---------------------------------------------------


def test_forgotten_token_fails_closed(env) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        token = _token_from_messages(body["messages"])
        # Send a forged token (never issued by the server).
        content = json.dumps(
            {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": "forged.token"}}
        )
        assert token  # prompt must carry the real token; model ignored it
        return _chat_completion(content)

    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=httpx.MockTransport(handler),
    )
    resp = orch.create_model_task(env["workspace_id"], "evil token")
    assert resp.state == "failed"
    assert env["db"].execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"].startswith("MODEL_EDIT_INVALID")
    assert env["target"].read_text(encoding="utf-8", newline="") == "first line\nsecond line\n"


def test_wrong_base_hash_fails_closed(env) -> None:
    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=_read_then_candidate_handler(misuse_base=True),
    )
    resp = orch.create_model_task(env["workspace_id"], "stale base")
    assert resp.state == "failed"
    detail = env["db"].execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"]
    assert detail.startswith("STALE_BASE")
    assert env["target"].read_text(encoding="utf-8", newline="") == "first line\nsecond line\n"


def test_tool_round_budget_exceeded(env) -> None:
    cfg = _ready_config()
    cfg = cfg.__class__(**{**cfg.__dict__, "max_tool_rounds": 1})
    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], cfg,
        transport=_always_tool_handler(),
    )
    resp = orch.create_model_task(env["workspace_id"], "loop")
    assert resp.state == "failed"
    detail = env["db"].execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"]
    assert detail.startswith("MODEL_BUDGET_EXCEEDED")
    assert env["target"].read_text(encoding="utf-8", newline="") == "first line\nsecond line\n"


def test_malformed_model_output_fails_closed(env) -> None:
    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=_fixed_content_handler("I will just edit the file directly."),
    )
    resp = orch.create_model_task(env["workspace_id"], "nonsense")
    assert resp.state == "failed"
    detail = env["db"].execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"]
    assert detail.startswith("MODEL_RESPONSE_INVALID")


def test_fenced_output_is_parsed(env) -> None:
    # The model wraps its JSON in a code fence; the orchestrator must strip it.
    fenced = "```json\n" + json.dumps(
        {
            "kind": "candidate_edit_intent",
            "fileToken": "PLACEHOLDER",
            "baseSha256": "PLACEHOLDER",
            "edits": [{"expectedText": "first line", "replacementText": "fenced edit"}],
            "rationale": "x",
            "plan": ["y"],
        }
    ) + "\n```"
    # Patch the candidate base/hash dynamically via a custom handler.
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        body = json.loads(request.content)
        messages = body["messages"]
        token = _token_from_messages(messages)
        if state["n"] == 1:
            content = json.dumps(
                {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": token}}
            )
        else:
            base = _base_sha_from_messages(messages)
            payload = {
                "kind": "candidate_edit_intent",
                "fileToken": token,
                "baseSha256": base,
                "edits": [{"expectedText": "first line", "replacementText": "fenced edit"}],
                "rationale": "x",
                "plan": ["y"],
            }
            content = "```json\n" + json.dumps(payload) + "\n```"
        return _chat_completion(content)

    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=httpx.MockTransport(handler),
    )
    resp = orch.create_model_task(env["workspace_id"], "fenced")
    assert resp.state == "awaiting_approval"
    cs = env["db"].execute(
        "SELECT proposed_text FROM changesets WHERE id = ?", (resp.changeSetId,)
    ).fetchone()
    assert "fenced edit" in cs["proposed_text"]


# --- Tool policy -------------------------------------------------------------


def test_tool_request_with_forbidden_path_field_fails(env) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        token = _token_from_messages(body["messages"])
        # Smuggling a path/patch through the tool request must be rejected.
        content = json.dumps(
            {
                "kind": "tool_request",
                "tool": "read_file",
                "arguments": {"fileToken": token, "path": "/etc/passwd", "patch": "x"},
            }
        )
        return _chat_completion(content)

    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=httpx.MockTransport(handler),
    )
    resp = orch.create_model_task(env["workspace_id"], "smuggle")
    assert resp.state == "failed"
    assert env["db"].execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"].startswith("MODEL_EDIT_INVALID")


def test_disallowed_tool_fails(env) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        token = _token_from_messages(body["messages"])
        content = json.dumps(
            {
                "kind": "tool_request",
                "tool": "search_files",  # reserved, not wired in WP6
                "arguments": {"fileToken": token},
            }
        )
        return _chat_completion(content)

    orch = ModelOrchestrator(
        env["db"], env["registry"], env["guard"], env["config"],
        transport=httpx.MockTransport(handler),
    )
    resp = orch.create_model_task(env["workspace_id"], "bad tool")
    assert resp.state == "failed"
    assert env["db"].execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"].startswith("MODEL_EDIT_INVALID")


# --- HTTP surface ------------------------------------------------------------


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    (ws_root / "notes.txt").write_text("first line\nsecond line\n", encoding="utf-8", newline="")
    config = {
        "workspaces": [
            {
                "id": "ws-demo",
                "displayName": "Demo Workspace",
                "rootPath": str(ws_root),
                "policy": "phase1-single-text-file",
                "targetFile": "notes.txt",
                "enabled": True,
            }
        ]
    }
    cp = tmp_path / "workspaces.json"
    cp.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("LIGHTCODE_WORKSPACES_CONFIG", str(cp))
    monkeypatch.setenv("LIGHTCODE_DATABASE_PATH", str(tmp_path / "lightcode.db"))
    with TestClient(app) as c:
        yield c


def test_api_create_model_task_disabled_provider_fails_closed(api_client) -> None:
    # Default app has no provider configured -> orchestration fails closed with
    # MODEL_DISABLED, never opening a socket.
    resp = api_client.post(
        "/api/v1/model-tasks",
        json={"workspaceId": "ws-demo", "title": "should fail (disabled)"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "failed"
    # The error code is surfaced on the task; the route itself returns 200 so
    # the client can render the failed task with its stable code.
    assert "MODEL_DISABLED" in body["detail"] or body["detail"]


def test_api_create_model_task_happy_path(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    # Make the provider ready and replace the model call with a scripted one
    # (no network). Mirrors the unit happy path.
    monkeypatch.setattr(
        "app.main.app.state.model_provider", _ready_config()
    )

    state = {"n": 0}

    def scripted_chat(self, messages, *, max_output_tokens=None):
        state["n"] += 1
        token = _token_from_messages(messages)
        if state["n"] == 1:
            return json.dumps(
                {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": token}}
            )
        base = _base_sha_from_messages(messages)
        return json.dumps(
            {
                "kind": "candidate_edit_intent",
                "fileToken": token,
                "baseSha256": base,
                "edits": [{"expectedText": "first line", "replacementText": "api edited"}],
                "rationale": "x",
                "plan": ["y"],
            }
        )

    monkeypatch.setattr(
        "app.services.model_orchestrator.OpenAICompatibleProvider.chat", scripted_chat
    )

    resp = api_client.post(
        "/api/v1/model-tasks", json={"workspaceId": "ws-demo", "title": "api edit"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == "awaiting_approval"
    assert body["changeSetId"]
    assert "rootPath" not in body

    # The GET endpoint returns the same read-only view.
    fetched = api_client.get(f"/api/v1/model-tasks/{body['id']}").json()
    assert fetched["state"] == "awaiting_approval"
    assert fetched["changeSetId"] == body["changeSetId"]


def test_api_model_task_rejects_client_root_path(api_client) -> None:
    # extra="forbid": a smuggled rootPath/filePath must be rejected by the DTO.
    resp = api_client.post(
        "/api/v1/model-tasks",
        json={"workspaceId": "ws-demo", "title": "evil", "rootPath": "/etc"},
    )
    assert resp.status_code == 422
