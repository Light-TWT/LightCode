from fastapi.testclient import TestClient


def test_history_list_returns_entries(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/workspace-login-service/tasks/history")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 8
    assert payload[0]["id"] == "history-task-1"
    assert payload[1]["status"] == "done"


def test_done_task_detail_returns_complete_model(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/history-task-2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "history-task-2"
    assert payload["status"] == "done"
    assert len(payload["plan"]) == 4
    assert len(payload["toolCalls"]) == 12
    assert len(payload["files"]) == 3
    assert payload["approval"]["status"] == "approved"
    assert payload["test"]["result"] == "pass"
    assert payload.get("failReason") is None
    assert payload.get("cancelInfo") is None


def test_fail_task_detail_contains_failure_fields(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/history-task-3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "fail"
    assert payload["failReason"] == "依赖缺失"
    assert payload["rejectedCmd"] == "pip install slowapi"


def test_cancelled_task_detail_contains_cancel_info(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/history-task-8")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["cancelInfo"]["stage"] == "需求分析完成后"


def test_unknown_task_detail_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/unknown-task-id")

    assert response.status_code == 404
