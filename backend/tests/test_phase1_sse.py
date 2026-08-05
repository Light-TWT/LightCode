from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    (ws_root / "notes.txt").write_text("alpha\nbeta\n", encoding="utf-8")
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
    with TestClient(app) as c:
        yield c


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        event_name = next((l[len("event:"):].strip() for l in lines if l.startswith("event:")), "")
        data = next((l[len("data:"):].strip() for l in lines if l.startswith("data:")), "")
        if event_name == "task.event" and data:
            events.append(json.loads(data))
    return events


def test_create_only_replays_readonly_lifecycle(client: TestClient) -> None:
    task = client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": "t"}
    ).json()
    resp = client.get(f"/api/v1/real-tasks/{task['id']}/events")
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    types = [e["eventType"] for e in events]
    # exactly the read-only + diff generation lifecycle, ending at awaiting_approval
    assert types == [
        "task.created",
        "task.planning",
        "task.reading_workspace",
        "task.generating_diff",
        "task.awaiting_approval",
    ]
    # sequence numbers must be strictly monotonic starting at 1
    seqs = [e["sequence"] for e in events]
    assert seqs == list(range(1, len(seqs) + 1))


def test_full_lifecycle_events_after_approval(client: TestClient) -> None:
    task = client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": "t"}
    ).json()
    cs = task["changeSet"]
    client.post(
        f"/api/v1/real-tasks/{task['id']}/approval",
        json={
            "decision": "approve",
            "changeSetId": cs["changeSetId"],
            "revision": cs["revision"],
            "diffHash": cs["diffHash"],
            "idempotencyKey": "k1",
        },
    )
    resp = client.get(f"/api/v1/real-tasks/{task['id']}/events")
    events = _parse_sse(resp.text)
    types = [e["eventType"] for e in events]
    assert types == [
        "task.created",
        "task.planning",
        "task.reading_workspace",
        "task.generating_diff",
        "task.awaiting_approval",
        "task.applying_change",
        "task.running_verification",
        "task.verification_completed",
        "task.completed",
    ]
    seqs = [e["sequence"] for e in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))  # no duplicates


def test_sse_stream_ends_with_marker(client: TestClient) -> None:
    task = client.post(
        "/api/v1/real-tasks", json={"workspaceId": "ws-demo", "title": "t"}
    ).json()
    resp = client.get(f"/api/v1/real-tasks/{task['id']}/events")
    assert "event: stream.end" in resp.text
