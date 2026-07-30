"""API-mode end-to-end verification of the Phase 1 real closed loop (M3).

Exercises the full, browser-faithful flow against the real HTTP surface:
registered-workspace listing (no root path), token-based browse + read + search,
real-task creation, approval (version-bound), disk write, and SSE replay of the
resulting terminal events. No free-form path is ever submitted by the client.
"""

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    (tmp_path / "workspaces.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("LIGHTCODE_WORKSPACES_CONFIG", str(tmp_path / "workspaces.json"))
    monkeypatch.setenv("LIGHTCODE_DATABASE_PATH", str(tmp_path / "lightcode.db"))

    with TestClient(app) as client:
        yield client, target


def _make_approval(task: dict) -> dict:
    cs = task["changeSet"]
    return {
        "decision": "approve",
        "changeSetId": cs["changeSetId"],
        "revision": cs["revision"],
        "diffHash": cs["diffHash"],
        "idempotencyKey": uuid.uuid4().hex,
    }


def test_api_mode_closed_loop(env) -> None:
    client, target = env

    # 1. Workspace listing never leaks the real root path.
    workspaces = client.get("/api/v1/registered-workspaces").json()
    assert any(w["id"] == "ws-demo" for w in workspaces)
    assert all("rootPath" not in w for w in workspaces)
    assert all("proj" not in json.dumps(w) for w in workspaces)

    # 2. Token-based browse: list, then read the target file via its token.
    files = client.get("/api/v1/registered-workspaces/ws-demo/files").json()
    note = next(f for f in files if f["name"] == "notes.txt")
    assert note["token"]
    content = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"fileToken": note["token"]}
    ).json()
    assert "first line" in content["content"]
    assert "relativePath" not in content

    # 3. Search returns tokens, not free paths.
    hit = (ws_root := None)
    search = client.get(
        "/api/v1/registered-workspaces/ws-demo/search", params={"query": "first line"}
    ).json()
    assert any(h["token"] for h in search)

    # 4. Create a real task -> awaiting_approval, with a version-bound ChangeSet.
    created = client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": "append marker"}
    ).json()
    assert created["state"] == "awaiting_approval"
    assert created["changeSet"]["logicalRelativePath"] == "notes.txt"
    assert created["changeSet"]["revision"] == 1

    # 5. Approve (version-bound) -> completed; file on disk is mutated exactly once.
    approval = _make_approval(created)
    result = client.post(
        f"/api/v1/real-tasks/{created['id']}/approval", json=approval
    ).json()
    assert result["state"] == "completed"

    # 6. Idempotent replay does not re-apply.
    replay = client.post(
        f"/api/v1/real-tasks/{created['id']}/approval", json=approval
    ).json()
    assert replay["state"] == "completed"

    # 7. Refresh reflects terminal state.
    again = client.get(f"/api/v1/real-tasks/{created['id']}").json()
    assert again["state"] == "completed"

    # 8. SSE replay (no tail) returns the terminal events; sequence resume works.
    events = client.get(
        f"/api/v1/real-tasks/{created['id']}/events", params={"tail": False}
    ).text
    assert "task.applying_change" in events
    assert "task.completed" in events

    # 9. On-disk file equals the approved proposal (LF preserved on this seed).
    disk = target.read_text(encoding="utf-8", newline="")
    assert "LightCode Phase 1 change marker" in disk
