from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Boot the app against a temp workspace + temp DB via env configuration.

    The registry is loaded from a temp workspaces.json; no rootPath is ever
    submitted by the client. Lifespan runs on entering the TestClient context.
    """
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    (ws_root / "notes.txt").write_text("first line\nsecond line\n", encoding="utf-8")
    (ws_root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (ws_root / "sub").mkdir()
    (ws_root / "sub" / "deep.txt").write_text("nested content here\n", encoding="utf-8")

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

    db_path = tmp_path / "lightcode.db"
    monkeypatch.setenv("LIGHTCODE_WORKSPACES_CONFIG", str(config_path))
    monkeypatch.setenv("LIGHTCODE_DATABASE_PATH", str(db_path))

    with TestClient(app) as c:
        yield c


def test_registered_workspaces_hide_root_path(client: TestClient) -> None:
    resp = client.get("/api/v1/registered-workspaces")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    ws = body[0]
    assert ws["id"] == "ws-demo"
    assert ws["displayName"] == "Demo Workspace"
    assert ws["capabilities"] == ["list_files", "read_file", "search_files"]
    # critical: the real root path must never leak into the public DTO
    assert "rootPath" not in ws
    assert "proj" not in json.dumps(ws)


def test_list_files_marks_secret(client: TestClient) -> None:
    resp = client.get("/api/v1/registered-workspaces/ws-demo/files")
    assert resp.status_code == 200
    kinds = {item["name"]: item["kind"] for item in resp.json()}
    assert kinds["notes.txt"] == "file"
    assert kinds["sub"] == "dir"
    assert kinds[".env"] == "secret"


def test_read_file_returns_content(client: TestClient) -> None:
    resp = client.get("/api/v1/registered-workspaces/ws-demo/file", params={"path": "notes.txt"})
    assert resp.status_code == 200
    assert "first line" in resp.json()["content"]


def test_read_traversal_denied(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"path": "../secret.txt"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "PATH_POLICY_DENIED"


def test_read_secret_denied(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"path": ".env"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "SECRET_FILE_DENIED"


def test_unregistered_workspace_denied(client: TestClient) -> None:
    resp = client.get("/api/v1/registered-workspaces/nope/files")
    assert resp.status_code == 400
    assert resp.json()["code"] == "WORKSPACE_NOT_REGISTERED"


def test_search_finds_nested_match(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/search", params={"query": "nested content"}
    )
    assert resp.status_code == 200
    assert any(r["relativePath"] == "sub/deep.txt" for r in resp.json())


def test_create_real_task_lands_in_awaiting_approval(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/real-tasks",
        json={"workspaceId": "ws-demo", "title": "append marker to notes"},
    )
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["kind"] == "real"
    assert task["state"] == "awaiting_approval"
    assert task["targetFile"] == "notes.txt"

    cs = task["changeSet"]
    assert cs is not None
    assert cs["status"] == "active"
    assert cs["revision"] == 1
    assert cs["logicalRelativePath"] == "notes.txt"
    assert cs["baseSha256"].startswith("sha256:")
    assert cs["proposedSha256"].startswith("sha256:")
    assert cs["diffHash"].startswith("sha256:")
    assert cs["additions"] == 1
    assert cs["deletions"] == 0
    # public change set must not leak the real root path
    assert "proj" not in json.dumps(cs)


def test_get_real_task_roundtrip(client: TestClient) -> None:
    created = client.post(
        "/api/v1/real-tasks",
        json={"workspaceId": "ws-demo", "title": "roundtrip"},
    ).json()
    task_id = created["id"]
    fetched = client.get(f"/api/v1/real-tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == task_id
    assert fetched.json()["changeSet"]["changeSetId"] == created["changeSet"]["changeSetId"]


def test_create_real_task_rejects_client_root_path(client: TestClient) -> None:
    # extra="forbid": attempts to smuggle rootPath/filePath must be rejected.
    resp = client.post(
        "/api/v1/real-tasks",
        json={
            "workspaceId": "ws-demo",
            "title": "evil",
            "rootPath": "/etc",
            "filePath": "/etc/passwd",
        },
    )
    assert resp.status_code == 422


def test_create_real_task_unregistered_workspace(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/real-tasks",
        json={"workspaceId": "ghost", "title": "x"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "WORKSPACE_NOT_REGISTERED"
