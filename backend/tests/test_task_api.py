from fastapi.testclient import TestClient


def test_current_task_is_pending_before_approval(client: TestClient) -> None:
    response = client.get("/api/v1/sessions/session-login-validation/tasks/current")

    assert response.status_code == 200
    assert response.json()["state"] == "awaiting_approval"
    assert response.json()["changeSet"]["status"] == "pending"
    assert response.json()["verification"]["status"] == "pending"


def test_approve_changeset_updates_task_and_verification(client: TestClient) -> None:
    response = client.post("/api/v1/tasks/task-login-validation/changeset/approve")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "completed"
    assert payload["changeSet"]["status"] == "approved"
    assert payload["verification"]["status"] == "passed"


def test_unknown_task_returns_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/tasks/missing/changeset/approve")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found: missing"}


def test_double_approve_returns_conflict(client: TestClient) -> None:
    client.post("/api/v1/tasks/task-login-validation/changeset/approve")
    response = client.post("/api/v1/tasks/task-login-validation/changeset/approve")

    assert response.status_code == 409
    assert response.json() == {"detail": "Change set is not pending"}
