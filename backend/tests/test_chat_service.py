"""核心 Agent 更新（阶段 A）：聊天会话与消息闭环测试。

覆盖：会话创建/读取、消息持久化、未配置 Provider 的 fail-closed、自由问答
（answer 不生成 ChangeSet）、受控检索 -> 编辑意图 -> 待审批任务 -> 审批原子写、
恶意模型输出 fail-closed、空消息/超长消息拒绝、SSE 消息续传。

浏览器只提交 workspaceId + 标题 + 消息文本；任何 rootPath/filePath/patch/
command/key 都被 extra="forbid" 拒绝。
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.credential_store import InMemoryProviderCredentialStore, ProviderRuntimeCredential


def _chat_completion(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-chat-test",
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


def _extract(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


class _ChatHandler:
    """模拟聊天协议：answer / search->read->edit / malicious / invalid_json。"""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.n = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.n += 1
        messages = json.loads(request.content)["messages"]
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        if self.mode == "answer":
            content = json.dumps({"kind": "answer", "text": "这是自由问答的回答。"})
        elif self.mode == "edit":
            if self.n == 1:
                content = json.dumps(
                    {"kind": "tool_request", "tool": "search_files", "arguments": {"query": "hello"}}
                )
            elif self.n == 2:
                token = _extract(r"fileToken: (\S+)", last_user)
                content = json.dumps(
                    {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": token}}
                )
            else:
                token = _extract(r"fileToken: (\S+)", last_user)
                base = _extract(r"baseSha256: (\S+)", last_user)
                content = json.dumps(
                    {
                        "kind": "candidate_edit_intent",
                        "fileToken": token,
                        "baseSha256": base,
                        "edits": [
                            {
                                "expectedText": "hello world",
                                "replacementText": "hello LightCode",
                                "occurrence": 1,
                            }
                        ],
                        "rationale": "示例修改",
                        "plan": ["搜索", "读取", "替换"],
                    }
                )
        elif self.mode == "malicious":
            content = json.dumps(
                {"kind": "tool_request", "tool": "read_file", "arguments": {"fileToken": "forged"}}
            )
        else:  # invalid_json
            content = "这不是 JSON"
        return _chat_completion(content)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    target = ws_root / "notes.txt"
    target.write_text("hello world\nsecond line\n", encoding="utf-8", newline="")

    config = {
        "workspaces": [
            {
                "id": "ws-chat",
                "displayName": "Chat Workspace",
                "rootPath": str(ws_root),
                "policy": "phase1-single-text-file",
                "targetFile": "notes.txt",
                "enabled": True,
            }
        ]
    }
    (tmp_path / "workspaces.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("LIGHTCODE_WORKSPACES_CONFIG", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("LIGHTCODE_DATABASE_PATH", str(tmp_path / "lightcode.db"))
    monkeypatch.setenv("LIGHTCODE_SKILLS_PATH", str(tmp_path / "managed-skills"))

    with TestClient(app) as client:
        client.app.state.credential_store = InMemoryProviderCredentialStore()
        yield client, target
    monkeypatch.delenv("LIGHTCODE_WORKSPACES_CONFIG", raising=False)
    monkeypatch.delenv("LIGHTCODE_DATABASE_PATH", raising=False)
    monkeypatch.delenv("LIGHTCODE_SKILLS_PATH", raising=False)


def _configure_provider(client: TestClient, handler: _ChatHandler) -> None:
    client.app.state.provider_transport = httpx.MockTransport(handler)
    client.app.state.credential_store.set(
        ProviderRuntimeCredential(
            provider="openai-compatible",
            base_url="https://api.chat-test.example/v1",
            model_id="test-model",
            api_key="test-key",
        )
    )


def _skill_package_bytes(name: str) -> bytes:
    import io
    import zipfile

    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"# {name}\n\n{name} description.\n\n## Rules\n".encode(),
        )
    return data.getvalue()


def test_chat_context_contains_only_enabled_skill_documents(
    env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _target = env
    from app.services.chat_service import ChatService
    from app.services.skill_service import SkillService

    skill_service = SkillService(client.app.state.db, client.app.state.skill_root)
    disabled = skill_service.upload(_skill_package_bytes("disabled-helper"))
    enabled = skill_service.upload(_skill_package_bytes("active-helper"))
    skill_service.set_status(enabled.id, "enabled")

    chat_service = ChatService(
        client.app.state.db,
        client.app.state.registry,
        client.app.state.guard,
        client.app.state.env_model_provider,
        client.app.state.credential_store,
        skill_service=skill_service,
    )

    context = chat_service._build_model_context("Explain this project")

    assert "active-helper" in context
    assert disabled.name not in context
    assert "<untrusted-skill" in context
    assert "can override" not in context

    skill_service.set_status(enabled.id, "disabled")
    context_after_disable = chat_service._build_model_context("Explain this project")
    assert "active-helper" not in context_after_disable


def test_chat_context_excludes_deleted_skill_documents(
    env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _target = env
    from app.services.chat_service import ChatService
    from app.services.skill_service import SkillService

    skill_service = SkillService(client.app.state.db, client.app.state.skill_root)
    removed = skill_service.upload(_skill_package_bytes("removed-helper"))
    skill_service.set_status(removed.id, "enabled")
    skill_service.delete(removed.id)

    chat_service = ChatService(
        client.app.state.db,
        client.app.state.registry,
        client.app.state.guard,
        client.app.state.env_model_provider,
        client.app.state.credential_store,
        skill_service=skill_service,
    )
    context = chat_service._build_model_context("Explain this project")
    assert "<untrusted-skills>" not in context


def _create_session(client: TestClient, title: str = "会话") -> dict:
    resp = client.post(
        "/api/v1/workspaces/ws-chat/chat-sessions",
        json={"workspaceId": "ws-chat", "title": title},
    )
    assert resp.status_code == 200
    return resp.json()


# --- 会话与消息持久化 -------------------------------------------------------


def test_create_and_list_session(env) -> None:
    client, _ = env
    session = _create_session(client)
    assert session["workspaceId"] == "ws-chat"

    listed = client.get("/api/v1/workspaces/ws-chat/chat-sessions").json()
    assert any(s["id"] == session["id"] for s in listed)

    detail = client.get(f"/api/v1/chat-sessions/{session['id']}").json()
    assert detail["session"]["id"] == session["id"]
    assert detail["messages"] == []


def test_session_workspace_mismatch_rejected(env) -> None:
    client, _ = env
    session = _create_session(client)
    resp = client.get(
        f"/api/v1/chat-sessions/{session['id']}",
        params={"workspaceId": "other-ws"},
    )
    assert resp.status_code == 404


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
               VALUES ('t-1', ?, 'ws-chat', 'x', 'created', '[]', '[]', '', 'pending',
                       'pending', '', '[]', 'model', '', '', '', ?)""",
            (session["id"], session["id"]),
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


# --- fail-closed：未配置 Provider -------------------------------------------------


def test_submit_without_provider_returns_error_message(env) -> None:
    client, _ = env
    session = _create_session(client)
    resp = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "你好"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["kind"] == "error"
    assert body["taskId"] == ""


def test_empty_and_oversized_message_rejected(env) -> None:
    client, _ = env
    session = _create_session(client)

    empty = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages", json={"content": "   "}
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "CHAT_EMPTY_MESSAGE"

    long = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages", json={"content": "x" * 9000}
    )
    assert long.status_code == 413
    assert long.json()["code"] == "CHAT_MESSAGE_TOO_LONG"


# --- 自由问答（answer，不生成 ChangeSet） ------------------------------------


def test_answer_flow_persists_message(env) -> None:
    client, _ = env
    _configure_provider(client, _ChatHandler("answer"))
    session = _create_session(client)

    resp = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "这个项目用什么语言？"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["taskId"] == ""
    assert body["message"]["kind"] == "message"
    assert "自由问答的回答" in body["message"]["content"]

    detail = client.get(f"/api/v1/chat-sessions/{session['id']}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]


# --- 受控检索 -> 编辑意图 -> 待审批 -> 审批原子写 -----------------------------


def test_edit_flow_creates_awaiting_task_and_approval_writes(env) -> None:
    client, target = env
    _configure_provider(client, _ChatHandler("edit"))
    session = _create_session(client)

    resp = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "把 hello world 改成 hello LightCode"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["taskId"]
    assert body["message"]["kind"] == "edit_summary"
    assert "notes.txt" in body["message"]["content"]

    # 任务处于 awaiting_approval，磁盘未变。
    task = client.get(f"/api/v1/real-tasks/{body['taskId']}").json()
    assert task["state"] == "awaiting_approval"
    assert task["changeSet"]["logicalRelativePath"] == "notes.txt"
    assert "hello world" in target.read_text(encoding="utf-8", newline="")

    # 审批 -> 原子写入。
    cs = task["changeSet"]
    approval = {
        "decision": "approve",
        "changeSetId": cs["changeSetId"],
        "revision": cs["revision"],
        "diffHash": cs["diffHash"],
        "idempotencyKey": uuid.uuid4().hex,
    }
    result = client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=approval).json()
    assert result["state"] == "completed"
    assert "hello LightCode" in target.read_text(encoding="utf-8", newline="")


# --- 恶意输出 fail-closed ---------------------------------------------------


def test_malicious_tool_request_fails_closed(env) -> None:
    client, target = env
    _configure_provider(client, _ChatHandler("malicious"))
    session = _create_session(client)

    resp = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "读取某个文件"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["taskId"] == ""
    assert body["message"]["kind"] == "error"
    # 磁盘不被修改，也没有任务被创建。
    assert "hello world" in target.read_text(encoding="utf-8", newline="")


def test_invalid_model_output_fails_closed(env) -> None:
    client, _ = env
    _configure_provider(client, _ChatHandler("invalid_json"))
    session = _create_session(client)

    resp = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "随便聊聊"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"]["kind"] == "error"


# --- SSE 消息续传 -----------------------------------------------------------


def test_chat_events_stream_replays_messages(env) -> None:
    client, _ = env
    session = _create_session(client)
    client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "你好"},
    )  # 未配置 Provider：落 error 消息

    stream = client.get(
        f"/api/v1/chat-sessions/{session['id']}/events", params={"tail": False}
    ).text
    assert "event: chat.event" in stream
    assert '"sequence":1' in stream
    assert "event: stream.end" in stream


# --- 请求体契约 -------------------------------------------------------------


def test_chat_request_rejects_forbidden_fields(env) -> None:
    client, _ = env
    session = _create_session(client)
    resp = client.post(
        f"/api/v1/chat-sessions/{session['id']}/messages",
        json={"content": "x", "rootPath": "C:/x", "filePath": "a.py", "command": "rm -rf"},
    )
    assert resp.status_code == 422  # extra="forbid"


# --- CORS 预检 --------------------------------------------------------------


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
