"""阶段 B：多供应商配置文件 CRUD 与安全不变量测试。

覆盖：列表（含多配置）、创建（连接测试通过才保存）、单条安全摘要、删除、
未知 id 404、extra=forbid 拒绝多余字段；所有响应绝不含 API Key 或完整 Base URL。
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.credential_store import InMemoryProviderCredentialStore

SECRET = "sk-profiles-must-not-leak"
BASE_URL = "https://api.profiles-test.example/v1"


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

    os.environ["LIGHTCODE_DATABASE_PATH"] = str(tmp_path / "profiles.db")
    with TestClient(app) as c:
        c.app.state.credential_store = InMemoryProviderCredentialStore()
        c.app.state.provider_transport = _transport()
        yield c
    os.environ.pop("LIGHTCODE_DATABASE_PATH", None)


def _create_payload(**overrides: str) -> dict:
    body = {
        "name": "测试供应商",
        "provider": "openai-compatible",
        "baseUrl": BASE_URL,
        "apiKey": SECRET,
        "modelId": "deepseek-chat",
        "enabled": True,
    }
    body.update(overrides)
    return body


def test_profiles_empty_when_nothing_saved(client: TestClient) -> None:
    body = client.get("/api/v1/provider/profiles").json()
    assert body == []


def test_create_profile_then_list_contains_it(client: TestClient) -> None:
    resp = client.post("/api/v1/provider/profiles", json=_create_payload())
    assert resp.status_code == 200
    created = resp.json()
    assert created["id"]
    assert created["name"] == "测试供应商"
    assert created["modelId"] == "deepseek-chat"
    assert created["enabled"] is True
    assert created["status"] == "ready"
    assert created["baseUrlHost"] == "api.profiles-test.example"

    profiles = client.get("/api/v1/provider/profiles").json()
    assert len(profiles) == 1
    assert profiles[0]["id"] == created["id"]


def test_create_second_profile_lists_both(client: TestClient) -> None:
    client.post("/api/v1/provider/profiles", json=_create_payload())
    client.post(
        "/api/v1/provider/profiles",
        json=_create_payload(name="第二个", modelId="gpt-4.1-mini"),
    )
    profiles = client.get("/api/v1/provider/profiles").json()
    assert len(profiles) == 2
    assert {p["name"] for p in profiles} == {"测试供应商", "第二个"}


def test_get_single_profile_by_id(client: TestClient) -> None:
    created = client.post("/api/v1/provider/profiles", json=_create_payload()).json()
    resp = client.get(f"/api/v1/provider/profiles/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_unknown_profile_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/provider/profiles/does-not-exist")
    assert resp.status_code == 404


def test_delete_profile_removes_it(client: TestClient) -> None:
    created = client.post("/api/v1/provider/profiles", json=_create_payload()).json()
    resp = client.delete(f"/api/v1/provider/profiles/{created['id']}")
    assert resp.status_code == 200
    assert client.get("/api/v1/provider/profiles").json() == []


def test_delete_unknown_profile_returns_404(client: TestClient) -> None:
    resp = client.delete("/api/v1/provider/profiles/does-not-exist")
    assert resp.status_code == 404


def test_create_fails_closed_when_connection_fails(client: TestClient) -> None:
    def _error(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    client.app.state.provider_transport = httpx.MockTransport(_error)
    resp = client.post("/api/v1/provider/profiles", json=_create_payload())
    assert resp.status_code == 502
    assert resp.json()["code"] == "PROVIDER_CONNECTION_FAILED"
    assert client.get("/api/v1/provider/profiles").json() == []


def test_create_rejects_forbidden_fields(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/provider/profiles",
        json={**_create_payload(), "rootPath": "C:/x"},
    )
    assert resp.status_code == 422  # extra="forbid"


def test_profiles_never_leak_key_or_full_url(client: TestClient) -> None:
    client.post("/api/v1/provider/profiles", json=_create_payload())
    raw = client.get("/api/v1/provider/profiles").text
    assert SECRET not in raw
    assert BASE_URL not in raw
    assert "api.profiles-test.example/v1" not in raw


def test_profiles_response_has_no_forbidden_field_names(client: TestClient) -> None:
    client.post("/api/v1/provider/profiles", json=_create_payload())
    body = client.get("/api/v1/provider/profiles").json()

    forbidden_field_names = {
        "apikey", "api_key",
        "baseurl", "base_url",
        "authorization", "bearer",
        "rootpath", "root_path",
    }

    def _collect_keys(obj) -> set[str]:
        keys: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                keys.add(str(k).casefold())
                keys.update(_collect_keys(v))
        elif isinstance(obj, list):
            for item in obj:
                keys.update(_collect_keys(item))
        return keys

    present = _collect_keys(body)
    assert forbidden_field_names.isdisjoint(present), present & forbidden_field_names
