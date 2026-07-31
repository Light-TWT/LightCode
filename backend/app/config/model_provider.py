"""Phase 2 / WP5: backend-only model provider configuration.

Design rules (docs/2026-07-30-phase-2-model-and-dx-plan.md §WP5):

1. The provider is configured **exclusively** by backend environment variables.
   The browser never inputs, stores, echoes or transmits an API key or base URL.
2. It is **off by default**. ``LIGHTCODE_MODEL_ENABLED`` must be explicitly set
   to a true spelling; anything else (including a typo) leaves it disabled.
3. Every derived state is **fail-closed**: a missing credential is
   ``unconfigured`` and a misconfiguration (origin outside the allowlist,
   plaintext HTTP without an explicit dev switch, unknown provider kind) is
   ``degraded``. Neither state is allowed to open a socket.
4. The API key lives in exactly one attribute, is excluded from ``repr()`` and
   is never included in :meth:`ModelProviderConfig.safe_summary`, which is the
   only sanctioned serialisation path.

This module performs no I/O and imports nothing from the service layer, so it
can be unit-tested with a plain dict instead of the real process environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Mapping
from urllib.parse import urlsplit

ProviderStatus = Literal["disabled", "unconfigured", "ready", "degraded"]

#: Only OpenAI-compatible chat completions are supported in Phase 2's first cut.
SUPPORTED_PROVIDERS = frozenset({"openai-compatible"})

#: Read-only tools the model is permitted to request. Declared here so the
#: health endpoint can advertise the boundary before WP6 wires the orchestrator.
MODEL_ALLOWED_TOOLS = ("read_file", "search_files")

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})

# Defaults mirror the budget table in the Phase 2 plan (§WP8).
_DEFAULTS: dict[str, float | int] = {
    "connect_timeout_seconds": 5.0,
    "read_timeout_seconds": 45.0,
    "total_timeout_seconds": 60.0,
    "max_tool_rounds": 8,
    "max_input_bytes": 262_144,
    "max_output_tokens": 2048,
    "max_requests_per_task": 10,
    "max_concurrent_tasks": 1,
}


def _as_bool(raw: str | None) -> bool:
    return (raw or "").strip().casefold() in _TRUE_VALUES


def _as_positive_int(raw: str | None, default: int) -> int:
    """Parse a positive int budget, falling back to the default.

    Fail-closed: a malformed or non-positive value must not be read as
    "unlimited"; it reverts to the documented default instead.
    """
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _as_positive_float(raw: str | None, default: float) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _origin_of(url: str) -> str:
    """Return ``scheme://host[:port]`` for an absolute URL, else ``""``."""
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme.casefold()}://{parts.netloc.casefold()}"


@dataclass(frozen=True)
class ModelProviderConfig:
    """Immutable snapshot of the provider configuration.

    ``api_key`` is marked ``repr=False`` so the generated ``__repr__`` (and
    therefore any accidental f-string, log line or traceback rendering of the
    object) cannot leak it.
    """

    enabled: bool
    provider: str
    base_url: str
    model_id: str
    allowed_origins: tuple[str, ...]
    connect_timeout_seconds: float
    read_timeout_seconds: float
    total_timeout_seconds: float
    max_tool_rounds: int
    max_input_bytes: int
    max_output_tokens: int
    max_requests_per_task: int
    max_concurrent_tasks: int
    allow_insecure_http: bool
    api_key: str = field(default="", repr=False)

    # --- Derived security properties ---

    @property
    def base_origin(self) -> str:
        return _origin_of(self.base_url)

    @property
    def origin_allowlisted(self) -> bool:
        origin = self.base_origin
        return bool(origin) and origin in self.allowed_origins

    @property
    def transport(self) -> str:
        """``https`` | ``http`` | ``none`` — scheme only, never the full URL."""
        scheme = urlsplit(self.base_url.strip()).scheme.casefold()
        return scheme if scheme in ("http", "https") else "none"

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> ProviderStatus:
        """Config-derived health. Never performs a network call."""
        if not self.enabled:
            return "disabled"
        if not (self.api_key and self.base_url.strip() and self.model_id.strip()):
            return "unconfigured"
        if self.provider not in SUPPORTED_PROVIDERS:
            return "degraded"
        if not self.origin_allowlisted:
            return "degraded"
        if self.transport == "none":
            return "degraded"
        if self.transport == "http" and not self.allow_insecure_http:
            return "degraded"
        return "ready"

    def status_detail(self) -> str:
        """A short, non-sensitive explanation of the current status."""
        status = self.status()
        if status == "disabled":
            return "模型能力未启用（LIGHTCODE_MODEL_ENABLED 未开启）。"
        if status == "unconfigured":
            missing = [
                name
                for name, present in (
                    ("API Key", self.api_key_configured),
                    ("Base URL", bool(self.base_url.strip())),
                    ("Model ID", bool(self.model_id.strip())),
                )
                if not present
            ]
            return "后端缺少配置：" + "、".join(missing) + "。"
        if status == "degraded":
            if self.provider not in SUPPORTED_PROVIDERS:
                return "不支持的 provider 类型。"
            if self.transport == "none":
                return "Base URL 不是合法的 http(s) 绝对地址。"
            if not self.origin_allowlisted:
                return "Base URL 的 origin 不在 allowlist 内，已拒绝出网。"
            return "生产环境要求 HTTPS；如需本地明文 HTTP 请显式开启开发开关。"
        return "Provider 已就绪。"

    def safe_summary(self) -> dict[str, object]:
        """The **only** sanctioned serialisation.

        Contains no key, no Authorization header, no full base URL, no prompt
        and no upstream response. Only the scheme and boolean facts escape.
        """
        return {
            "provider": self.provider,
            "modelId": self.model_id,
            "status": self.status(),
            "apiKeyConfigured": self.api_key_configured,
            "transport": self.transport,
            "originAllowlisted": self.origin_allowlisted,
            "followRedirects": False,
            "trustEnvProxies": False,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"ModelProviderConfig(status={self.status()}, provider={self.provider})"


def load_model_provider_config(
    environ: Mapping[str, str] | None = None,
) -> ModelProviderConfig:
    """Build the config from a mapping (defaults to ``os.environ``)."""
    env = os.environ if environ is None else environ

    def get(name: str) -> str:
        return env.get(name, "") or ""

    allowed_origins = tuple(
        origin
        for origin in (
            _origin_of(part) for part in get("LIGHTCODE_MODEL_ALLOWED_ORIGINS").split(",")
        )
        if origin
    )

    return ModelProviderConfig(
        enabled=_as_bool(get("LIGHTCODE_MODEL_ENABLED")),
        provider=get("LIGHTCODE_MODEL_PROVIDER").strip() or "openai-compatible",
        base_url=get("LIGHTCODE_MODEL_BASE_URL").strip(),
        model_id=get("LIGHTCODE_MODEL_ID").strip(),
        allowed_origins=allowed_origins,
        connect_timeout_seconds=_as_positive_float(
            get("LIGHTCODE_MODEL_CONNECT_TIMEOUT_SECONDS"),
            float(_DEFAULTS["connect_timeout_seconds"]),
        ),
        read_timeout_seconds=_as_positive_float(
            get("LIGHTCODE_MODEL_READ_TIMEOUT_SECONDS"),
            float(_DEFAULTS["read_timeout_seconds"]),
        ),
        total_timeout_seconds=_as_positive_float(
            get("LIGHTCODE_MODEL_TOTAL_TIMEOUT_SECONDS"),
            float(_DEFAULTS["total_timeout_seconds"]),
        ),
        max_tool_rounds=_as_positive_int(
            get("LIGHTCODE_MODEL_MAX_TOOL_ROUNDS"), int(_DEFAULTS["max_tool_rounds"])
        ),
        max_input_bytes=_as_positive_int(
            get("LIGHTCODE_MODEL_MAX_INPUT_BYTES"), int(_DEFAULTS["max_input_bytes"])
        ),
        max_output_tokens=_as_positive_int(
            get("LIGHTCODE_MODEL_MAX_OUTPUT_TOKENS"), int(_DEFAULTS["max_output_tokens"])
        ),
        max_requests_per_task=_as_positive_int(
            get("LIGHTCODE_MODEL_MAX_REQUESTS_PER_TASK"),
            int(_DEFAULTS["max_requests_per_task"]),
        ),
        max_concurrent_tasks=_as_positive_int(
            get("LIGHTCODE_MODEL_MAX_CONCURRENT_TASKS"),
            int(_DEFAULTS["max_concurrent_tasks"]),
        ),
        allow_insecure_http=_as_bool(get("LIGHTCODE_MODEL_ALLOW_INSECURE_HTTP")),
        api_key=get("LIGHTCODE_MODEL_API_KEY").strip(),
    )
