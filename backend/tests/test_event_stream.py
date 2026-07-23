from fastapi.testclient import TestClient


def test_task_events_are_replayed_in_sequence(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/task-login-validation/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: task.event" in response.text
    assert '"sequence":1' in response.text
    assert "event: stream.end" in response.text
