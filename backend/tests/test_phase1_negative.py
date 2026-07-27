"""Phase 1 negative-scenario coverage (safety-contract §必须验证的负向场景).

These tests assert that forged inputs, invalid approvals and forbidden file
kinds never reach the filesystem, and that the Phase 1 code paths contain no
shell / subprocess / network / git machinery.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    (ws_root / "notes.txt").write_text("first\nsecond\n", encoding="utf-8")
    (ws_root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (ws_root / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
    (ws_root / "big.txt").write_bytes(b"x" * 1_000_001)

    disabled_root = tmp_path / "disabled"
    disabled_root.mkdir()
    (disabled_root / "notes.txt").write_text("x\n", encoding="utf-8")

    config = {
        "workspaces": [
            {
                "id": "ws-demo",
                "displayName": "Demo",
                "rootPath": str(ws_root),
                "policy": "phase1-single-text-file",
                "targetFile": "notes.txt",
                "enabled": True,
            },
            {
                "id": "ws-off",
                "displayName": "Disabled",
                "rootPath": str(disabled_root),
                "policy": "phase1-single-text-file",
                "targetFile": "notes.txt",
                "enabled": False,
            },
        ]
    }
    (tmp_path / "workspaces.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("LIGHTCODE_WORKSPACES_CONFIG", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("LIGHTCODE_DATABASE_PATH", str(tmp_path / "lightcode.db"))
    with TestClient(app) as client:
        yield client, ws_root


def _create(client: TestClient) -> dict:
    return client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": "t"}
    ).json()


# --- Forged / invalid approvals must not write ---

def test_wrong_changeset_id_not_active(env) -> None:
    client, ws_root = env
    before = (ws_root / "notes.txt").read_text(encoding="utf-8")
    task = _create(client)
    resp = client.post(
        f"/api/v1/real-tasks/{task['id']}/approval",
        json={
            "decision": "approve",
            "changeSetId": "cs-does-not-exist",
            "revision": 1,
            "diffHash": task["changeSet"]["diffHash"],
            "idempotencyKey": "k",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CHANGESET_NOT_ACTIVE"
    assert (ws_root / "notes.txt").read_text(encoding="utf-8") == before


def test_double_approval_second_is_idempotent_not_reapplied(env) -> None:
    client, ws_root = env
    task = _create(client)
    cs = task["changeSet"]
    body = {
        "decision": "approve",
        "changeSetId": cs["changeSetId"],
        "revision": cs["revision"],
        "diffHash": cs["diffHash"],
        "idempotencyKey": "once",
    }
    client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=body)
    content_after_first = (ws_root / "notes.txt").read_text(encoding="utf-8")
    # a fresh key on an already-completed task must be rejected as invalid state
    body2 = dict(body, idempotencyKey="twice")
    resp = client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=body2)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_STATE_TRANSITION"
    assert (ws_root / "notes.txt").read_text(encoding="utf-8") == content_after_first


def test_approval_rejects_smuggled_fields(env) -> None:
    client, _ = env
    task = _create(client)
    cs = task["changeSet"]
    resp = client.post(
        f"/api/v1/real-tasks/{task['id']}/approval",
        json={
            "decision": "approve",
            "changeSetId": cs["changeSetId"],
            "revision": cs["revision"],
            "diffHash": cs["diffHash"],
            "idempotencyKey": "k",
            "filePath": "/etc/passwd",
            "patch": "rm -rf /",
            "command": "sh",
        },
    )
    assert resp.status_code == 422


# --- Forbidden file kinds via read-only tools ---

def test_binary_file_denied(env) -> None:
    client, _ = env
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"path": "blob.bin"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_TYPE_DENIED"


def test_oversize_file_denied(env) -> None:
    client, _ = env
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"path": "big.txt"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_SIZE_DENIED"


def test_directory_read_denied(env) -> None:
    client, ws_root = env
    (ws_root / "sub").mkdir()
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"path": "sub"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_TYPE_DENIED"


def test_disabled_workspace_denied(env) -> None:
    client, _ = env
    resp = client.get("/api/v1/registered-workspaces/ws-off/files")
    assert resp.status_code == 400
    assert resp.json()["code"] == "WORKSPACE_DISABLED"


def test_create_task_on_disabled_workspace_denied(env) -> None:
    client, _ = env
    resp = client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-off", "title": "t"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "WORKSPACE_DISABLED"


# --- No shell / network / git in Phase 1 code paths ---

def test_phase1_modules_have_no_forbidden_machinery() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    modules = [
        backend_root / "app" / "services" / "phase1.py",
        backend_root / "app" / "services" / "atomic_write.py",
        backend_root / "app" / "services" / "changeset.py",
        backend_root / "app" / "security" / "guard.py",
        backend_root / "app" / "security" / "fs.py",
        backend_root / "app" / "workspaces" / "registry.py",
    ]
    forbidden = ("subprocess", "os.system", "socket", "urllib", "requests", "httpx", "pip ", "git ")
    for module in modules:
        source = module.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{module.name} must not reference {token!r}"
