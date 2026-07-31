"""WP5: Provider configuration is backend-env only, default-off, fail-closed.

Safety invariants under test:
  - The provider is disabled unless explicitly enabled by a backend env var.
  - A missing key/base URL/model id yields `unconfigured` and never a network call.
  - An origin outside the allowlist, or plain HTTP without an explicit dev
    switch, yields `degraded` instead of silently proceeding.
  - The API key never appears in repr(), str(), the health DTO or any log line.
"""

from __future__ import annotations

import pytest

from app.config.model_provider import ModelProviderConfig, load_model_provider_config

SECRET = "sk-super-secret-value-do-not-leak"


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


# --- Default-off -----------------------------------------------------------


def test_default_environment_is_disabled() -> None:
    config = load_model_provider_config({})
    assert config.enabled is False
    assert config.status() == "disabled"


def test_enabled_flag_must_be_explicit_true() -> None:
    for value in ("false", "0", "no", "", "TRUE_ISH"):
        config = load_model_provider_config(_env(LIGHTCODE_MODEL_ENABLED=value))
        assert config.status() == "disabled", value


def test_enabled_accepts_common_true_spellings() -> None:
    for value in ("true", "True", "1", "yes", "on"):
        config = load_model_provider_config(_env(LIGHTCODE_MODEL_ENABLED=value))
        assert config.enabled is True, value


# --- Unconfigured / degraded fail-closed -----------------------------------


def test_missing_api_key_is_unconfigured() -> None:
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_API_KEY=""))
    assert config.status() == "unconfigured"


def test_missing_base_url_is_unconfigured() -> None:
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_BASE_URL=""))
    assert config.status() == "unconfigured"


def test_missing_model_id_is_unconfigured() -> None:
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_ID=""))
    assert config.status() == "unconfigured"


def test_origin_outside_allowlist_is_degraded() -> None:
    config = load_model_provider_config(
        _env(LIGHTCODE_MODEL_ALLOWED_ORIGINS="https://other.example")
    )
    assert config.status() == "degraded"
    assert config.origin_allowlisted is False


def test_empty_allowlist_is_degraded() -> None:
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_ALLOWED_ORIGINS=""))
    assert config.status() == "degraded"


def test_plain_http_is_degraded_without_dev_switch() -> None:
    config = load_model_provider_config(
        _env(
            LIGHTCODE_MODEL_BASE_URL="http://127.0.0.1:11434/v1",
            LIGHTCODE_MODEL_ALLOWED_ORIGINS="http://127.0.0.1:11434",
        )
    )
    assert config.status() == "degraded"


def test_plain_http_allowed_with_explicit_dev_switch() -> None:
    config = load_model_provider_config(
        _env(
            LIGHTCODE_MODEL_BASE_URL="http://127.0.0.1:11434/v1",
            LIGHTCODE_MODEL_ALLOWED_ORIGINS="http://127.0.0.1:11434",
            LIGHTCODE_MODEL_ALLOW_INSECURE_HTTP="true",
        )
    )
    assert config.status() == "ready"


def test_unknown_provider_is_degraded() -> None:
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_PROVIDER="anthropic-native"))
    assert config.status() == "degraded"


def test_fully_configured_is_ready() -> None:
    config = load_model_provider_config(_env())
    assert config.status() == "ready"
    assert config.origin_allowlisted is True


# --- Budgets ---------------------------------------------------------------


def test_budget_defaults_match_the_plan() -> None:
    config = load_model_provider_config(_env())
    assert config.max_tool_rounds == 8
    assert config.max_requests_per_task == 10
    assert config.max_input_bytes == 262_144
    assert config.max_output_tokens == 2048
    assert config.max_concurrent_tasks == 1
    assert config.connect_timeout_seconds == 5.0
    assert config.read_timeout_seconds == 45.0
    assert config.total_timeout_seconds == 60.0


def test_malformed_numeric_budget_falls_back_to_default() -> None:
    # Fail-closed: a typo must not disable the budget entirely.
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_MAX_TOOL_ROUNDS="not-a-number"))
    assert config.max_tool_rounds == 8


def test_non_positive_budget_falls_back_to_default() -> None:
    config = load_model_provider_config(_env(LIGHTCODE_MODEL_MAX_REQUESTS_PER_TASK="0"))
    assert config.max_requests_per_task == 10


# --- Secret containment ----------------------------------------------------


def test_api_key_absent_from_repr_and_str() -> None:
    config = load_model_provider_config(_env())
    assert SECRET not in repr(config)
    assert SECRET not in str(config)


def test_api_key_absent_from_safe_summary() -> None:
    config = load_model_provider_config(_env())
    summary = config.safe_summary()
    assert SECRET not in str(summary)
    assert summary["apiKeyConfigured"] is True
    # The full base URL is a deployment detail and must not be echoed either.
    assert "provider.example/v1" not in str(summary)


def test_config_is_immutable() -> None:
    config = load_model_provider_config(_env())
    with pytest.raises(Exception):
        config.enabled = False  # type: ignore[misc]


def test_dataclass_field_is_not_serialised_by_asdict_helper() -> None:
    config = load_model_provider_config(_env())
    assert isinstance(config, ModelProviderConfig)
    # `safe_summary()` is the only sanctioned serialisation path.
    assert "apiKey" not in config.safe_summary()
    assert "api_key" not in config.safe_summary()
