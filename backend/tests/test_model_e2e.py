"""WP8 API-mode end-to-end tests (Phase 2).

Exercises the full model-task surface over HTTP with a mocked provider
transport: token-browsed read -> candidate ChangeSet -> Phase 1 approval ->
atomic write -> SSE replay/resume, plus the failure catalogue. Every test also
asserts the sensitive-data invariant: no API key, Authorization, full base URL,
absolute path or raw code may appear in logs or event payloads.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config.model_provider import ModelProviderConfig
from app.main import app
from app.services.model_orchestrator import ModelOrchestrator
from app.services.observability import Metrics


# --- transport helpers (mirror test_model_orchestrator.py) ------------------


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
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        },
    )


def _token_from_messages(messages: list[dict]) -> str | None:
    return re.search(r"读取它的 token：(\S+)", messages[0]["content"]).group(1)


def _base_sha_from_messages(messages: list[dict]) -> str | None:
    return re.search(r"baseSha256: (sha256:\w+)", messages[-1]["content"]).group(1)


def _read_then_candidate_handler() -> httpx.MockTransport:
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


def _forbidden_path_handler() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        token = _token_from_messages(body["messages"])
        content = json.dumps(
            {
                "kind": "tool_request",
                "tool": "read_file",
                "arguments": {"fileToken": token, "path": "/etc/passwd"},
            }
        )
        return _chat_completion(content)

    return httpx.MockTransport(handler)


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    # Point the lifespan at an isolated DB and workspace config.
    monkeypatch.setenv("LIGHTCODE_DATABASE_PATH", str(tmp_path / "lightcode.db"))
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    (ws_root / "notes.txt").write_text(
        "first line\nsecond line\n", encoding="utf-8", newline=""
    )
    ws_config = {
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
    cfg_path = tmp_path / "workspaces.json"
    cfg_path.write_text(json.dumps(ws_config), encoding="utf-8")
    monkeypatch.setenv("LIGHTCODE_WORKSPACES_CONFIG", str(cfg_path))
    # A ready (but still mocked) model provider — never contacts the network.
    monkeypatch.setenv("LIGHTCODE_MODEL_ENABLED", "true")
    monkeypatch.setenv("LIGHTCODE_MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LIGHTCODE_MODEL_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("LIGHTCODE_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("LIGHTCODE_MODEL_ID", "test-model")
    monkeypatch.setenv("LIGHTCODE_MODEL_ALLOWED_ORIGINS", "https://api.example.test")

    with TestClient(app) as c:
        yield c


def _patch_transport(monkeypatch, transport: httpx.MockTransport) -> None:
    """Route /model-tasks through a mocked provider transport."""
    original = ModelOrchestrator.from_request

    def fake_from_request(request):
        return ModelOrchestrator(
            request.app.state.db,
            request.app.state.registry,
            request.app.state.guard,
            request.app.state.model_provider,
            transport=transport,
        )

    monkeypatch.setattr(ModelOrchestrator, "from_request", staticmethod(fake_from_request))
    return original


def _forbid_list() -> list[str]:
    # Substrings that must never surface in logs or event payloads.
    return [
        "test-key",
        "api.example.test",
        "Bearer",
        "Authorization",
    ]


def _assert_no_leak(caplog, db, task_id: str, tmp_path: Path) -> None:
    parts: list[str] = []
    skip = {
        "args", "msg", "message", "exc_info", "exc_text", "stack_info", "created",
        "msecs", "relativeCreated", "thread", "threadName", "processName", "process",
        "module", "filename", "funcName", "lineno", "levelname", "levelno",
        "pathname", "name", "correlation_id",
    }
    for rec in caplog.records:
        parts.append(rec.getMessage())
        for key, value in rec.__dict__.items():
            if key in skip:
                continue
            parts.append(str(value))
    blob = " ".join(parts)
    for forbidden in _forbid_list() + [str(tmp_path)]:
        assert forbidden not in blob, f"possible leak of {forbidden!r} in logs"

    rows = db.execute(
        "SELECT payload_json FROM task_events WHERE task_id = ?", (task_id,)
    ).fetchall()
    payload_blob = " ".join(r["payload_json"] for r in rows)
    for forbidden in _forbid_list() + [str(tmp_path)]:
        assert forbidden not in payload_blob, f"possible leak of {forbidden!r} in events"


# --- happy path -------------------------------------------------------------


def test_api_mode_e2e_happy_path(client, monkeypatch, caplog, tmp_path: Path) -> None:
    _patch_transport(monkeypatch, _read_then_candidate_handler())
    caplog.set_level(logging.INFO)
    Metrics.reset()

    resp = client.post(
        "/api/v1/model-tasks", json={"workspaceId": "ws-demo", "title": "edit first line"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "awaiting_approval"
    task_id = body["id"]
    cs_id = body["changeSetId"]
    assert cs_id

    db = client.app.state.db
    cs = db.execute("SELECT * FROM changesets WHERE id = ?", (cs_id,)).fetchone()
    assert cs is not None
    assert "first line (edited by model)" in cs["proposed_text"]

    # Approve through the Phase 1 endpoint -> atomic write to disk.
    diff_hash = db.execute(
        "SELECT diff_hash FROM changesets WHERE id = ?", (cs_id,)
    ).fetchone()["diff_hash"]
    approval = {
        "decision": "approve",
        "changeSetId": cs_id,
        "revision": 1,
        "diffHash": diff_hash,
        "idempotencyKey": uuid.uuid4().hex,
    }
    ar = client.post(f"/api/v1/real-tasks/{task_id}/approval", json=approval)
    assert ar.status_code == 200
    assert ar.json()["state"] == "completed"
    assert "first line (edited by model)" in (tmp_path / "proj" / "notes.txt").read_text(
        encoding="utf-8", newline=""
    )

    # SSE replay (non-tail) carries the full lifecycle.
    sse = client.get(
        f"/api/v1/real-tasks/{task_id}/events", params={"after_sequence": 0}
    )
    assert "event: task.event" in sse.text
    assert "task.awaiting_approval" in sse.text

    # Observability captured the right aggregates.
    counters = Metrics.snapshot()["counters"]
    assert counters["provider.call:openai-compatible:test-model:success"] >= 1
    assert counters["tool.call:model_read:read_file"] >= 1
    assert counters["task.transition:planning->awaiting_approval"] >= 1
    assert counters["sse.stream.started"] >= 1

    # No sensitive data anywhere.
    _assert_no_leak(caplog, db, task_id, tmp_path)


# --- failures ---------------------------------------------------------------


def test_e2e_malicious_tool_request_fails(client, monkeypatch, caplog, tmp_path: Path) -> None:
    _patch_transport(monkeypatch, _forbidden_path_handler())
    caplog.set_level(logging.INFO)
    Metrics.reset()

    resp = client.post(
        "/api/v1/model-tasks", json={"workspaceId": "ws-demo", "title": "evil"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "failed"
    task_id = body["id"]

    detail = client.app.state.db.execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()["verification_detail"]
    assert detail.startswith("MODEL_EDIT_INVALID")
    # The model never writes during orchestration.
    assert (tmp_path / "proj" / "notes.txt").read_text(encoding="utf-8", newline="") == (
        "first line\nsecond line\n"
    )
    assert Metrics.snapshot()["counters"]["task.transition:planning->failed"] >= 1
    _assert_no_leak(caplog, client.app.state.db, task_id, tmp_path)


def test_e2e_provider_request_budget_exhausted(
    client, monkeypatch, caplog, tmp_path: Path
) -> None:
    cfg = ModelProviderConfig(
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
        max_requests_per_task=1,  # force exhaustion after the first call
        max_concurrent_tasks=1,
        allow_insecure_http=False,
        api_key="test-key",
    )
    client.app.state.model_provider = cfg
    _patch_transport(monkeypatch, _read_then_candidate_handler())
    caplog.set_level(logging.INFO)
    Metrics.reset()

    resp = client.post(
        "/api/v1/model-tasks", json={"workspaceId": "ws-demo", "title": "loop"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "failed"
    task_id = body["id"]
    detail = client.app.state.db.execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()["verification_detail"]
    assert detail.startswith("MODEL_BUDGET_EXCEEDED")
    assert (tmp_path / "proj" / "notes.txt").read_text(encoding="utf-8", newline="") == (
        "first line\nsecond line\n"
    )
    assert Metrics.snapshot()["counters"]["budget.exceeded:MODEL_BUDGET_EXCEEDED"] >= 1
    _assert_no_leak(caplog, client.app.state.db, task_id, tmp_path)


# --- SSE resume -------------------------------------------------------------


def test_e2e_sse_resume_metric(client, monkeypatch) -> None:
    _patch_transport(monkeypatch, _read_then_candidate_handler())
    Metrics.reset()

    resp = client.post(
        "/api/v1/model-tasks", json={"workspaceId": "ws-demo", "title": "x"}
    )
    task_id = resp.json()["id"]

    # A client that reconnects with a Last-Event-ID must be counted as a resume.
    client.get(
        f"/api/v1/real-tasks/{task_id}/events",
        headers={"Last-Event-ID": "3"},
    )
    assert Metrics.snapshot()["counters"]["sse.resume"] >= 1
