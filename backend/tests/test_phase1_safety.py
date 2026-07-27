"""Module 1 new-capability tests: ChangeSet expiry, file policy, crash
recovery and SSE resume (see docs/plan module 1)."""

from __future__ import annotations

import json
import threading
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security.policy import MAX_DIFF_LINES
from app.services.phase1 import Phase1Service

TARGET = "notes.txt"


@pytest.fixture
def env(tmp_path, monkeypatch):
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    (ws_root / TARGET).write_text("first line\nsecond line\n", encoding="utf-8")
    config = {
        "workspaces": [
            {
                "id": "ws-demo",
                "displayName": "Demo Workspace",
                "rootPath": str(ws_root),
                "policy": "phase1-single-text-file",
                "targetFile": TARGET,
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
        yield c, ws_root


def _create_real_task(client, title="t") -> dict:
    return client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": title}
    ).json()


def _make_approval(cs: dict) -> dict:
    from uuid import uuid4

    return {
        "decision": "approve",
        "changeSetId": cs["changeSetId"],
        "revision": cs["revision"],
        "diffHash": cs["diffHash"],
        "idempotencyKey": uuid4().hex,
    }


# --- M1.1 ChangeSet expiry ---


def test_expired_changeset_rejected(env) -> None:
    client, ws_root = env
    original = (ws_root / TARGET).read_text(encoding="utf-8", newline="")
    created = _create_real_task(client)
    task_id = created["id"]
    cs_id = created["changeSet"]["changeSetId"]
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    client.app.state.db.execute(
        "UPDATE changesets SET expires_at = ? WHERE id = ?", (past, cs_id)
    )
    resp = client.post(
        f"/api/v1/real-tasks/{task_id}/approval", json=_make_approval(created["changeSet"])
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "CHANGESET_EXPIRED"
    # file must remain untouched
    assert (ws_root / TARGET).read_text(encoding="utf-8", newline="") == original


def test_fresh_changeset_expiry_field_present(env) -> None:
    client, _ = env
    created = _create_real_task(client)
    assert created["changeSet"]["expiresAt"]
    future = datetime.fromisoformat(created["changeSet"]["expiresAt"])
    assert future > datetime.now(timezone.utc)


# --- M1.2 file policy ---


def test_diff_line_limit_blocks_large_changeset(env, monkeypatch) -> None:
    client, _ = env
    monkeypatch.setattr("app.services.phase1.MAX_DIFF_LINES", 0)
    resp = client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": "too big"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_TYPE_DENIED"


def test_disallowed_extension_read_denied(env) -> None:
    client, ws_root = env
    (ws_root / "image.png").write_text("binary-ish", encoding="utf-8")
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/file", params={"path": "image.png"}
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "FILE_TYPE_DENIED"


def test_search_skips_disallowed_extension(env) -> None:
    client, ws_root = env
    (ws_root / "hidden.bin").write_text("needle-token-xyz", encoding="utf-8")
    resp = client.get(
        "/api/v1/registered-workspaces/ws-demo/search", params={"query": "needle-token-xyz"}
    )
    assert resp.status_code == 200
    assert not any("hidden.bin" in r["relativePath"] for r in resp.json())


# --- M1.3 crash recovery ---


def _set_applying(client, ws_root, created, file_content: str | None):
    task_id = created["id"]
    cs_id = created["changeSet"]["changeSetId"]
    if file_content is not None:
        (ws_root / TARGET).write_text(file_content, encoding="utf-8", newline="")
    client.app.state.db.execute(
        "UPDATE tasks SET state = 'applying_change' WHERE id = ?", (task_id,)
    )
    return client.app.state.db.execute(
        "SELECT * FROM changesets WHERE id = ?", (cs_id,)
    ).fetchone()


def test_recovery_completes_when_file_matches_proposed(env) -> None:
    client, ws_root = env
    created = _create_real_task(client)
    cs = _set_applying(client, ws_root, created, None)
    (ws_root / TARGET).write_text(cs["proposed_text"], encoding="utf-8", newline="")
    service = Phase1Service(client.app.state.db, client.app.state.registry, client.app.state.guard)
    summary = service.recover_incomplete_tasks()
    assert summary["completed"] == 1
    fetched = client.get(f"/api/v1/real-tasks/{created['id']}").json()
    assert fetched["state"] == "completed"
    assert fetched["changeSet"]["status"] == "applied"


def test_recovery_resets_when_baseline_intact(env) -> None:
    client, ws_root = env
    created = _create_real_task(client)
    original = (ws_root / TARGET).read_text(encoding="utf-8", newline="")
    _set_applying(client, ws_root, created, original)
    service = Phase1Service(client.app.state.db, client.app.state.registry, client.app.state.guard)
    summary = service.recover_incomplete_tasks()
    assert summary["reset"] == 1
    fetched = client.get(f"/api/v1/real-tasks/{created['id']}").json()
    assert fetched["state"] == "awaiting_approval"


def test_recovery_unknown_blocks_auto_write(env) -> None:
    client, ws_root = env
    created = _create_real_task(client)
    _set_applying(client, ws_root, created, "unexpected divergent content\n")
    service = Phase1Service(client.app.state.db, client.app.state.registry, client.app.state.guard)
    summary = service.recover_incomplete_tasks()
    assert summary["unknown"] == 1
    fetched = client.get(f"/api/v1/real-tasks/{created['id']}").json()
    assert fetched["state"] == "failed"
    assert fetched["changeSet"]["status"] == "failed"


# --- M1.4 SSE resume ---


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        fields = {}
        for line in block.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                fields[key.strip()] = val.strip()
        if "data" in fields:
            try:
                parsed = json.loads(fields["data"])
            except json.JSONDecodeError:
                continue
            # skip the terminal `stream.end` frame (payload `{}`)
            if "sequence" in parsed:
                events.append(parsed)
    return events


def test_sse_emit_id_field_for_resume(env) -> None:
    client, _ = env
    created = _create_real_task(client)
    task_id = created["id"]
    resp = client.get(f"/api/v1/real-tasks/{task_id}/events")
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events
    # every frame carries an `id:` equal to its sequence for Last-Event-ID
    for ev in events:
        assert f"id: {ev['sequence']}" in resp.text


def test_sse_after_sequence_skips_already_seen(env) -> None:
    client, _ = env
    created = _create_real_task(client)
    task_id = created["id"]
    full = client.get(f"/api/v1/real-tasks/{task_id}/events")
    last = _parse_sse(full.text)[-1]["sequence"]
    resp = client.get(
        f"/api/v1/real-tasks/{task_id}/events", params={"after_sequence": last}
    )
    assert "event: task.event" not in resp.text  # nothing new to replay
    assert "event: stream.end" in resp.text


def test_sse_last_event_id_header_resumes(env) -> None:
    client, _ = env
    created = _create_real_task(client)
    task_id = created["id"]
    full = client.get(f"/api/v1/real-tasks/{task_id}/events")
    last = _parse_sse(full.text)[-1]["sequence"]
    resp = client.get(
        f"/api/v1/real-tasks/{task_id}/events", headers={"Last-Event-ID": str(last)}
    )
    assert "event: task.event" not in resp.text


def test_sse_tail_captures_later_events(env, monkeypatch) -> None:
    client, _ = env
    monkeypatch.setattr("app.api.routes.SSE_TAIL_TIMEOUT_SECONDS", 2)
    created = _create_real_task(client)
    task_id = created["id"]
    approval = _make_approval(created["changeSet"])

    def _approve_later() -> None:
        _time.sleep(0.4)
        client.post(f"/api/v1/real-tasks/{task_id}/approval", json=approval)

    worker = threading.Thread(target=_approve_later)
    worker.start()
    resp = client.get(f"/api/v1/real-tasks/{task_id}/events", params={"tail": True})
    worker.join()
    text = resp.text
    # the approval generated applying_change / verification / completed events
    # that must be caught by the tailing stream.
    assert "task.applying_change" in text
    assert "task.completed" in text
