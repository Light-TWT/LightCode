"""WP5: the OpenAI-compatible client is fail-closed at the transport boundary.

The client is deliberately NOT wired into any task flow in WP5. These tests
pin the security behaviour so WP6 can build on it:

  - disabled / unconfigured / degraded config never opens a socket;
  - redirects are refused rather than followed;
  - ambient proxy env vars are not trusted;
  - timeouts, 429, 5xx, malformed JSON and oversized input map to stable codes;
  - no error message, log line or exception ever carries the key or raw body.
"""

from __future__ import annotations

import httpx
import pytest

from app.config.model_provider import load_model_provider_config
from app.schemas.errors import (
    MODEL_BUDGET_EXCEEDED,
    MODEL_DISABLED,
    MODEL_RATE_LIMITED,
    MODEL_RESPONSE_INVALID,
    MODEL_TIMEOUT,
    MODEL_UNCONFIGURED,
    MODEL_UPSTREAM_ERROR,
    Phase1Error,
)
from app.services.openai_compatible_provider import OpenAICompatibleProvider

SECRET = "sk-super-secret-value-do-not-leak"
MESSAGES = [{"role": "user", "content": "hello"}]


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "LIGHTCODE_MODEL_ENABLED": "true",
        "LIGHTCODE_MODEL_PROVIDER": "openai-compatible",
        "LIGHTCODE_MODEL_BASE_URL": "https://provider.example/v1",
        "LIGHTCODE_MODEL_API_KEY": SECRET,
        "LIGHTCODE_MODEL_ID": "demo-model",
        "LIGHTCODE_MODEL_ALLOWED_ORIGINS": "https://provider.example",
    }
    base.update(overrides)
    return base


def _provider(handler, **overrides: str) -> OpenAICompatibleProvider:
    config = load_model_provider_config(_env(**overrides))
    transport = httpx.MockTransport(handler)
    return OpenAICompatibleProvider(config, transport=transport)


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"role": "assistant", "content": "hi there"}}]},
    )


def _exploding_handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
    raise AssertionError("no network call may be attempted for this configuration")


# --- No socket unless ready ------------------------------------------------


def test_disabled_provider_never_calls_out() -> None:
    provider = _provider(_exploding_handler, LIGHTCODE_MODEL_ENABLED="false")
    with pytest.raises(Phase1Error) as exc:
        provider.chat(MESSAGES)
    assert exc.value.code == MODEL_DISABLED


def test_unconfigured_provider_never_calls_out() -> None:
    provider = _provider(_exploding_handler, LIGHTCODE_MODEL_API_KEY="")
    with pytest.raises(Phase1Error) as exc:
        provider.chat(MESSAGES)
    assert exc.value.code == MODEL_UNCONFIGURED


def test_degraded_origin_never_calls_out() -> None:
    provider = _provider(
        _exploding_handler, LIGHTCODE_MODEL_ALLOWED_ORIGINS="https://other.example"
    )
    with pytest.raises(Phase1Error) as exc:
        provider.chat(MESSAGES)
    assert exc.value.code == MODEL_UPSTREAM_ERROR


# --- Happy path ------------------------------------------------------------


def test_ready_provider_returns_assistant_content() -> None:
    provider = _provider(_ok_handler)
    assert provider.chat(MESSAGES) == "hi there"


def test_request_carries_bearer_auth_and_model_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode("utf-8")
        return _ok_handler(request)

    _provider(handler).chat(MESSAGES)
    assert seen["auth"] == f"Bearer {SECRET}"
    assert seen["url"] == "https://provider.example/v1/chat/completions"
    assert '"model":"demo-model"' in str(seen["body"]).replace(" ", "")


# --- Transport hardening ---------------------------------------------------


def test_redirects_are_refused_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.example/v1"})

    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert exc.value.code == MODEL_UPSTREAM_ERROR
    assert "evil.example" not in exc.value.message


def test_ambient_proxy_env_is_not_trusted() -> None:
    provider = _provider(_ok_handler)
    assert provider.trust_env is False


def test_timeout_maps_to_stable_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert exc.value.code == MODEL_TIMEOUT


def test_rate_limit_maps_to_stable_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert exc.value.code == MODEL_RATE_LIMITED


def test_server_error_maps_to_stable_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream on fire")

    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert exc.value.code == MODEL_UPSTREAM_ERROR
    assert "on fire" not in exc.value.message


def test_malformed_json_maps_to_stable_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert exc.value.code == MODEL_RESPONSE_INVALID


def test_missing_choices_maps_to_stable_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "cmpl-1"})

    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert exc.value.code == MODEL_RESPONSE_INVALID


# --- Budgets ---------------------------------------------------------------


def test_oversized_input_is_rejected_before_the_call() -> None:
    provider = _provider(_exploding_handler, LIGHTCODE_MODEL_MAX_INPUT_BYTES="128")
    with pytest.raises(Phase1Error) as exc:
        provider.chat([{"role": "user", "content": "x" * 500}])
    assert exc.value.code == MODEL_BUDGET_EXCEEDED


def test_per_task_request_budget_is_enforced() -> None:
    provider = _provider(_ok_handler, LIGHTCODE_MODEL_MAX_REQUESTS_PER_TASK="2")
    provider.chat(MESSAGES)
    provider.chat(MESSAGES)
    with pytest.raises(Phase1Error) as exc:
        provider.chat(MESSAGES)
    assert exc.value.code == MODEL_BUDGET_EXCEEDED


# --- Secret containment ----------------------------------------------------


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(401, json={"error": {"message": SECRET}}),
        lambda request: httpx.Response(500, text=SECRET),
        lambda request: httpx.Response(200, text=SECRET),
    ],
)
def test_upstream_body_never_reaches_the_error_message(handler) -> None:
    with pytest.raises(Phase1Error) as exc:
        _provider(handler).chat(MESSAGES)
    assert SECRET not in exc.value.message
    assert SECRET not in str(exc.value)
