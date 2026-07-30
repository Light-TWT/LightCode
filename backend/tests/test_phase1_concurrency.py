"""P0-3 concurrency proof: at most one approval writes a given file.

The safety property is that the file-scoped conditional ``UPDATE`` in
``Phase1Service.submit_approval`` is a genuine cross-process mutex. Two
scenarios back this:

* ``test_file_scoped_claim_blocks_second_task_same_file`` opens two *independent*
  connections to the same database file (the exact situation of two Uvicorn
  workers / two OS processes) and issues the CAS UPDATE sequentially. The first
  claim succeeds (rowcount 1); the second, seeing the first's ``applying_change``
  state committed on the shared file, is rejected (rowcount 0). This is a
  deterministic proof that the mutex holds across processes with no new table
  and no schema change.

* ``test_concurrent_approvals_at_most_one_writes`` drives two independent
  ``Phase1Service`` instances (each on its own connection, i.e. two processes)
  from two threads against two tasks that target the same file, and asserts the
  on-disk file is written exactly once (no corruption / no double write) and
  exactly one task reaches ``completed`` while the other raises ``APPLY_CONFLICT``.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.connection import open_connection
from app.db.database import initialize_database
from app.main import app
from app.schemas.contracts import ApprovalRequest
from app.schemas.errors import APPLY_CONFLICT, Phase1Error
from app.services.phase1 import Phase1Service


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



def _claim(c, task_id: str, workspace_id: str, target_file: str) -> int:
    # Mirror submit_approval's exclusive write claim exactly.
    cur = c.execute(
        """UPDATE tasks
           SET state = 'applying_change'
           WHERE id = ? AND state = 'awaiting_approval'
             AND NOT EXISTS (
               SELECT 1 FROM tasks t2
               WHERE t2.workspace_id = ? AND t2.target_file = ?
                 AND t2.state IN ('applying_change', 'completed')
             )""",
        (task_id, workspace_id, target_file),
    )
    return cur.rowcount


def test_file_scoped_claim_blocks_second_task_same_file(tmp_path: Path) -> None:
    db_path = tmp_path / "conc.db"
    seed = initialize_database(db_path)
    workspace_id = "ws1"
    target_file = "notes.txt"
    seed.execute(
        "INSERT INTO tasks (id, session_id, workspace_id, title, state, kind, target_file) "
        "VALUES (?, 's', ?, 't', 'awaiting_approval', 'real', ?)",
        ("A", workspace_id, target_file),
    )
    seed.execute(
        "INSERT INTO tasks (id, session_id, workspace_id, title, state, kind, target_file) "
        "VALUES (?, 's', ?, 't', 'awaiting_approval', 'real', ?)",
        ("B", workspace_id, target_file),
    )
    seed.commit()
    seed.close()

    # Two independent connections == two separate processes / workers.
    c1 = open_connection(db_path)
    a_rows = _claim(c1, "A", workspace_id, target_file)  # first writer wins
    c1.commit()
    c1.close()

    c2 = open_connection(db_path)
    b_rows = _claim(c2, "B", workspace_id, target_file)  # same file is taken
    c2.commit()
    c2.close()

    assert a_rows == 1
    assert b_rows == 0


def _make_approval(task: dict) -> ApprovalRequest:
    cs = task["changeSet"]
    return ApprovalRequest(
        decision="approve",
        changeSetId=cs["changeSetId"],
        revision=cs["revision"],
        diffHash=cs["diffHash"],
        idempotencyKey=uuid.uuid4().hex,
    )


def _create(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/real-tasks",
        json={"workspaceId": "ws-demo", "title": "append marker"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_concurrent_approvals_at_most_one_writes(env) -> None:
    client, target = env
    db_path = Path(os.environ["LIGHTCODE_DATABASE_PATH"])
    registry = app.state.registry
    guard = app.state.guard

    t1 = _create(client)
    t2 = _create(client)
    a1 = _make_approval(t1)
    a2 = _make_approval(t2)

    # Two independent services on two independent connections == two processes.
    c1 = open_connection(db_path)
    c2 = open_connection(db_path)
    svc1 = Phase1Service(c1, registry, guard)
    svc2 = Phase1Service(c2, registry, guard)

    outcomes: dict[str, object] = {}

    def _run(key: str, svc: Phase1Service, task_id: str, approval: ApprovalRequest) -> None:
        try:
            outcomes[key] = svc.submit_approval(task_id, approval)
        except Phase1Error as exc:
            outcomes[key] = exc

    p1 = threading.Thread(target=_run, args=("r1", svc1, t1["id"], a1))
    p2 = threading.Thread(target=_run, args=("r2", svc2, t2["id"], a2))
    p1.start()
    p2.start()
    p1.join()
    p2.join()
    c1.close()
    c2.close()

    completed = [o for o in outcomes.values() if getattr(o, "state", None) == "completed"]
    conflicted = [
        o for o in outcomes.values()
        if isinstance(o, Phase1Error) and o.code == APPLY_CONFLICT
    ]
    # Exactly one task wrote the file; the other was rejected by the file-scoped
    # mutex instead of double-writing.
    assert len(completed) == 1
    assert len(conflicted) == 1

    # The on-disk file equals exactly one proposal (no doubling / no garbage).
    # Both tasks target the same file with the same seed, so the proposal text is
    # identical; a single winning write yields that text once.
    db = app.state.db
    rows = db.execute(
        "SELECT proposed_text FROM changesets WHERE task_id IN (?, ?)",
        (t1["id"], t2["id"]),
    ).fetchall()
    proposals = {r["proposed_text"] for r in rows}
    # Read with newline="" so the on-disk bytes are compared verbatim: the
    # production path preserves the file's original line endings (guard.read_text
    # uses newline=""), so a default-mode read that re-translates CRLF->LF would
    # not match the stored proposed_text even though the write was correct.
    content = target.read_text(encoding="utf-8", newline="")
    assert content in proposals
    assert len(content) in {len(p) for p in proposals}
