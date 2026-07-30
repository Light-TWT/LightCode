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


def test_list_files_issues_tokens_and_marks_secret(client: TestClient) -> None:
    resp = client.get("/api/v1/registered-workspaces/ws-demo/files")
    assert resp.status_code == 200
    items = resp.json()
    kinds = {item["name"]: item["kind"] for item in items}
    assert kinds["notes.txt"] == "file"
    assert kinds["sub"] == "dir"
    assert kinds[".env"] == "secret"
    # navigable entries carry an opaque token; the browser never receives a
    # free-form relative path to submit back.
    for item in items:
        assert "relativePath" not in item
        if item["kind"] in ("file", "dir"):
            assert item["token"]
        else:
            assert item["token"] == ""


def test_read_file_via_token(client: TestClient) -> None:
    listing = client.get("/api/v1/registered-workspaces/ws-demo/files").json()
    entry = next(i for i in listing if i["name"] == "notes.txt")
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"fileToken": entry["token"]}
    )
    assert resp.status_code == 200
    assert "first line" in resp.json()["content"]
    assert "relativePath" not in resp.json()


def test_navigate_subdirectory_via_token(client: TestClient) -> None:
    root = client.get("/api/v1/registered-workspaces/ws-demo/files").json()
    sub = next(i for i in root if i["name"] == "sub")
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/files", params={"nodeToken": sub["token"]}
    )
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()}
    assert "deep.txt" in names


def test_read_with_forged_token_denied(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"fileToken": "garbage.token"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "BROWSE_TOKEN_INVALID"


def test_read_with_wrong_operation_token_denied(client: TestClient) -> None:
    # a 'list' token (issued for a directory) cannot be used to read a file
    root = client.get("/api/v1/registered-workspaces/ws-demo/files").json()
    sub = next(i for i in root if i["name"] == "sub")
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"fileToken": sub["token"]}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "BROWSE_TOKEN_INVALID"


def test_read_secret_denied(client: TestClient) -> None:
    # a forged 'read' token pointing at .env is rejected by the guard
    from app.services.browse_tokens import issue

    token = issue("ws-demo", "read", ".env")
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"fileToken": token}
    )
    assert resp.status_code in (400, 403)
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
    hits = resp.json()
    assert any(h["name"] == "deep.txt" for h in hits)
    for hit in hits:
        assert "relativePath" not in hit
        assert hit["token"]
    # the token from the search hit opens the file without a free path
    first = hits[0]
    read = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"fileToken": first["token"]}
    )
    assert read.status_code == 200
    assert "nested content" in read.json()["content"]


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


def test_legacy_approve_endpoint_rejects_real_task(client: TestClient) -> None:
    # M0.2: real Phase 1 tasks must not be approvable through the legacy
    # Phase 0.5 endpoint. The guarded approval protocol is the only path.
    created = client.post(
        "/api/v1/real-tasks",
        json={"workspaceId": "ws-demo", "title": "must use guarded approval"},
    ).json()
    task_id = created["id"]
    resp = client.post(f"/api/v1/tasks/{task_id}/changeset/approve")
    assert resp.status_code == 405
    assert "Phase 1 approval endpoint" in resp.json()["detail"]
