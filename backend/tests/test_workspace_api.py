from fastapi.testclient import TestClient


def test_recent_workspaces_return_camel_case_entries(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/recent")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "workspace-login-service"
    assert payload[0]["rootPath"] == "~/workspace/login-service"
    assert payload[0]["status"] == "waiting"


def test_unknown_workspace_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace not found: missing"}


def test_workspace_sessions_match_frontend_contract(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces/workspace-login-service/sessions")

    assert response.status_code == 200
    assert response.json()[0] == {
        "id": "session-login-validation",
        "title": "登录接口校验",
        "status": "awaiting_approval",
    }
