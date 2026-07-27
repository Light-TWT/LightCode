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
    target = ws_root / "notes.txt"
    target.write_text("first line\nsecond line\n", encoding="utf-8")

    config = {
        "workspaces": [
            {
                "id": "ws-demo",
                "displayName": "Demo",
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


def _create(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/real-tasks",
        json={"workspaceId": "ws-demo", "title": "append marker"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _approval_body(task: dict, *, key: str = "idem-1", revision: int | None = None,
                   diff_hash: str | None = None, decision: str = "approve") -> dict:
    cs = task["changeSet"]
    return {
        "decision": decision,
        "changeSetId": cs["changeSetId"],
        "revision": revision if revision is not None else cs["revision"],
        "diffHash": diff_hash if diff_hash is not None else cs["diffHash"],
        "idempotencyKey": key,
    }


def test_approve_writes_file_and_completes(env) -> None:
    client, target = env
    task = _create(client)
    resp = client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=_approval_body(task))
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["state"] == "completed"
    assert result["verification"]["status"] == "passed"
    assert result["changeSet"]["status"] == "applied"
    # file on disk actually changed and carries the deterministic marker
    content = target.read_text(encoding="utf-8")
    assert content.startswith("first line\nsecond line\n")
    assert "LightCode Phase 1 change marker" in content


def test_reject_leaves_file_untouched(env) -> None:
    client, target = env
    before = target.read_text(encoding="utf-8")
    task = _create(client)
    resp = client.post(
        f"/api/v1/real-tasks/{task['id']}/approval",
        json=_approval_body(task, decision="reject"),
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "cancelled"
    assert target.read_text(encoding="utf-8") == before


def test_wrong_revision_rejected_no_write(env) -> None:
    client, target = env
    before = target.read_text(encoding="utf-8")
    task = _create(client)
    resp = client.post(
        f"/api/v1/real-tasks/{task['id']}/approval",
        json=_approval_body(task, revision=99),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CHANGESET_REVISION_MISMATCH"
    assert target.read_text(encoding="utf-8") == before


def test_wrong_diff_hash_rejected_no_write(env) -> None:
    client, target = env
    before = target.read_text(encoding="utf-8")
    task = _create(client)
    resp = client.post(
        f"/api/v1/real-tasks/{task['id']}/approval",
        json=_approval_body(task, diff_hash="sha256:deadbeef"),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CHANGESET_REVISION_MISMATCH"
    assert target.read_text(encoding="utf-8") == before


def test_idempotent_approval_applies_once(env) -> None:
    client, target = env
    task = _create(client)
    body = _approval_body(task, key="same-key")
    first = client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=body)
    assert first.status_code == 200
    after_first = target.read_text(encoding="utf-8")
    # replay with same idempotency key must not append a second marker
    second = client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=body)
    assert second.status_code == 200
    assert second.json()["state"] == "completed"
    assert target.read_text(encoding="utf-8") == after_first
    assert after_first.count("LightCode Phase 1 change marker") == 1


def test_stale_base_fails_and_preserves_external_change(env) -> None:
    client, target = env
    task = _create(client)
    # external modification after the change set was generated
    target.write_text("externally changed content\n", encoding="utf-8")
    resp = client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=_approval_body(task))
    assert resp.status_code == 200
    result = resp.json()
    assert result["state"] == "failed"
    # must not overwrite the external change
    assert target.read_text(encoding="utf-8") == "externally changed content\n"


def test_reused_key_for_different_changeset_conflicts(env) -> None:
    client, _ = env
    task_a = _create(client)
    task_b = _create(client)
    client.post(f"/api/v1/real-tasks/{task_a['id']}/approval", json=_approval_body(task_a, key="dup"))
    # same key, different task/changeset
    resp = client.post(
        f"/api/v1/real-tasks/{task_b['id']}/approval", json=_approval_body(task_b, key="dup")
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "APPROVAL_ALREADY_PROCESSED"


def test_events_persisted_through_completion(env) -> None:
    client, _ = env
    task = _create(client)
    client.post(f"/api/v1/real-tasks/{task['id']}/approval", json=_approval_body(task))
    events = client.get(f"/api/v1/tasks/{task['id']}/events")
    assert events.status_code == 200
    body = events.text
    assert "task.applying_change" in body
    assert "task.verification_completed" in body
    assert "task.completed" in body
