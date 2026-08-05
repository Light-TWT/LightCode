"""核心 Agent 更新（阶段 A）：Provider 运行期设置 API 测试。

覆盖：设置读取（安全视图，无 key/baseUrl）、连接测试（ok/code）、测试并保存
（成功才落内存凭据）、清除、以及保存后 health 与聊天门禁随之变化。所有请求体
都不含 rootPath/filePath；所有响应都不含 API Key 或完整 Base URL。
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.credential_store import InMemoryProviderCredentialStore

SECRET = "sk-settings-test-must-not-leak"
BASE_URL = "https://api.settings-test.example/v1"


def _ok_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "pong"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def _transport() -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: _ok_response())


@pytest.fixture
def client(tmp_path) -> TestClient:
    import os

    os.environ["LIGHTCODE_DATABASE_PATH"] = str(tmp_path / "settings.db")
    with TestClient(app) as c:
        # 每测试使用全新的内存凭据存储与注入的 MockTransport。
        c.app.state.credential_store = InMemoryProviderCredentialStore()
        c.app.state.provider_transport = _transport()
        yield c
    os.environ.pop("LIGHTCODE_DATABASE_PATH", None)


def _payload(**overrides: str) -> dict:
    body = {
        "provider": "openai-compatible",
        "baseUrl": BASE_URL,
        "apiKey": SECRET,
        "modelId": "deepseek-chat",
    }
    body.update(overrides)
    return body


def test_settings_default_unconfigured(client: TestClient) -> None:
    body = client.get("/api/v1/provider/settings").json()
    assert body["configured"] is False
    assert body["status"] in ("disabled", "unconfigured")


def test_test_endpoint_ok_does_not_save(client: TestClient) -> None:
    resp = client.post("/api/v1/provider/settings/test", json=_payload())
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # 测试不保存：settings 仍是未配置。
    assert client.get("/api/v1/provider/settings").json()["configured"] is False


def test_test_endpoint_invalid_origin(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/provider/settings/test",
        json=_payload(baseUrl="http://127.0.0.1:9999/v1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["code"] == "PROVIDER_SETTINGS_INVALID"


def test_save_ok_then_health_ready_and_clear(client: TestClient) -> None:
    resp = client.post("/api/v1/provider/settings", json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["status"] == "ready"
    assert body["modelId"] == "deepseek-chat"

    health = client.get("/api/v1/provider/health").json()
    assert health["status"] == "ready"

    cleared = client.delete("/api/v1/provider/settings").json()
    assert cleared["configured"] is False
    # 清除后回落为默认（disabled/unconfigured）。
    assert client.get("/api/v1/provider/health").json()["status"] in ("disabled", "unconfigured")


def test_save_fails_closed_when_connection_fails(client: TestClient) -> None:
    def _error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    client.app.state.provider_transport = httpx.MockTransport(_error)
    resp = client.post("/api/v1/provider/settings", json=_payload())
    assert resp.status_code == 502
    assert resp.json()["code"] == "PROVIDER_CONNECTION_FAILED"
    # 失败不得保存。
    assert client.get("/api/v1/provider/settings").json()["configured"] is False


def test_save_rejects_missing_key(client: TestClient) -> None:
    resp = client.post("/api/v1/provider/settings", json=_payload(apiKey=""))
    assert resp.status_code == 422
    assert resp.json()["code"] == "PROVIDER_SETTINGS_INVALID"
    assert client.get("/api/v1/provider/settings").json()["configured"] is False


def test_settings_response_never_leaks_secret_or_url(client: TestClient) -> None:
    client.post("/api/v1/provider/settings", json=_payload())
    raw = client.get("/api/v1/provider/settings").text
    assert SECRET not in raw
    assert BASE_URL not in raw
    assert "api.settings-test.example" not in raw


def test_settings_rejects_forbidden_fields(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/provider/settings",
        json={**_payload(), "rootPath": "C:/x", "filePath": "a.py"},
    )
    assert resp.status_code == 422  # extra="forbid"
