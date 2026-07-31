"""WP5: `GET /api/v1/provider/health` is safe, default-off and read-only.

The endpoint is the browser's only view of the provider. It must:
  - default to `disabled` with zero configuration;
  - never contact the provider (so it costs nothing and cannot hang);
  - never expose the API key, the Authorization header or the base URL.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

SECRET = "sk-health-endpoint-must-not-leak-this"
BASE_URL = "https://provider.example/v1"

PROVIDER_ENV = (
    "LIGHTCODE_MODEL_ENABLED",
    "LIGHTCODE_MODEL_PROVIDER",
    "LIGHTCODE_MODEL_BASE_URL",
    "LIGHTCODE_MODEL_API_KEY",
    "LIGHTCODE_MODEL_ID",
    "LIGHTCODE_MODEL_ALLOWED_ORIGINS",
    "LIGHTCODE_MODEL_ALLOW_INSECURE_HTTP",
)


@pytest.fixture(autouse=True)
def _clean_provider_env():
    saved = {name: os.environ.pop(name, None) for name in PROVIDER_ENV}
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _client(tmp_path, **env: str) -> TestClient:
    os.environ["LIGHTCODE_DATABASE_PATH"] = str(tmp_path / "health.db")
    os.environ.update(env)
    return TestClient(app)


def _configured_env() -> dict[str, str]:
    return {
        "LIGHTCODE_MODEL_ENABLED": "true",
        "LIGHTCODE_MODEL_PROVIDER": "openai-compatible",
        "LIGHTCODE_MODEL_BASE_URL": BASE_URL,
        "LIGHTCODE_MODEL_API_KEY": SECRET,
        "LIGHTCODE_MODEL_ID": "demo-model",
        "LIGHTCODE_MODEL_ALLOWED_ORIGINS": "https://provider.example",
    }


# --- Default-off -----------------------------------------------------------


def test_health_defaults_to_disabled(tmp_path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/v1/provider/health").json()
    assert body["status"] == "disabled"
    assert body["security"]["apiKeyConfigured"] is False


def test_health_reports_unconfigured_when_key_missing(tmp_path) -> None:
    env = _configured_env()
    env["LIGHTCODE_MODEL_API_KEY"] = ""
    with _client(tmp_path, **env) as client:
        body = client.get("/api/v1/provider/health").json()
    assert body["status"] == "unconfigured"


def test_health_reports_ready_when_fully_configured(tmp_path) -> None:
    with _client(tmp_path, **_configured_env()) as client:
        body = client.get("/api/v1/provider/health").json()
    assert body["status"] == "ready"
    assert body["modelId"] == "demo-model"
    assert body["security"]["transport"] == "https"
    assert body["security"]["originAllowlisted"] is True


def test_health_reports_degraded_for_off_allowlist_origin(tmp_path) -> None:
    env = _configured_env()
    env["LIGHTCODE_MODEL_ALLOWED_ORIGINS"] = "https://somewhere-else.example"
    with _client(tmp_path, **env) as client:
        body = client.get("/api/v1/provider/health").json()
    assert body["status"] == "degraded"
    assert body["security"]["originAllowlisted"] is False


# --- Capability boundary ---------------------------------------------------


def test_health_advertises_read_only_capabilities(tmp_path) -> None:
    with _client(tmp_path, **_configured_env()) as client:
        capabilities = client.get("/api/v1/provider/health").json()["capabilities"]
    assert capabilities["canWriteFiles"] is False
    assert capabilities["canRunCommands"] is False
    assert set(capabilities["tools"]) == {"read_file", "search_files"}


def test_health_advertises_budgets(tmp_path) -> None:
    with _client(tmp_path, **_configured_env()) as client:
        capabilities = client.get("/api/v1/provider/health").json()["capabilities"]
    assert capabilities["maxToolRounds"] == 8
    assert capabilities["maxRequestsPerTask"] == 10
    assert capabilities["maxConcurrentTasks"] == 1


# --- Secret containment ----------------------------------------------------


def test_health_never_leaks_key_or_base_url(tmp_path) -> None:
    with _client(tmp_path, **_configured_env()) as client:
        raw = client.get("/api/v1/provider/health").text
    assert SECRET not in raw
    assert BASE_URL not in raw
    assert "provider.example" not in raw


def test_health_response_has_no_forbidden_field_names(tmp_path) -> None:
    with _client(tmp_path, **_configured_env()) as client:
        body = client.get("/api/v1/provider/health").json()

    # Structural check on field *names* (not substrings): the boolean
    # `apiKeyConfigured` is legitimate and must not be confused with the
    # actual key field `apiKey`, which must never exist on this surface.
    forbidden_field_names = {
        "apikey", "api_key",
        "baseurl", "base_url",
        "authorization", "bearer",
        "rootpath", "root_path",
        "prompt",
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


# --- Read-only / no network ------------------------------------------------


def test_health_makes_no_outbound_call(tmp_path, monkeypatch) -> None:
    # The only network entry point for the model is `OpenAICompatibleProvider.chat`.
    # Patch it: if the health endpoint ever invoked the provider, the call would
    # raise and the request would fail. Patching the method (not global httpx)
    # keeps Starlette's TestClient itself functional.
    import app.services.openai_compatible_provider as provider_mod

    def _forbid(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("provider health must not call the model")

    monkeypatch.setattr(provider_mod.OpenAICompatibleProvider, "chat", _forbid)
    with _client(tmp_path, **_configured_env()) as client:
        assert client.get("/api/v1/provider/health").status_code == 200


def test_health_endpoint_rejects_writes(tmp_path) -> None:
    with _client(tmp_path, **_configured_env()) as client:
        assert client.post("/api/v1/provider/health", json={}).status_code == 405
