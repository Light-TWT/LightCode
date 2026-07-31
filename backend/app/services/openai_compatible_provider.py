"""Phase 2 / WP5: hardened OpenAI-compatible chat client.

This is the **only** place in the codebase permitted to make an outbound
network call, and it is deliberately not wired into any task flow yet — WP6
(`model_orchestrator`) will consume it. Keeping it standalone lets the security
behaviour be pinned by tests before the model can influence a ChangeSet.

Hardening (docs/2026-07-30-phase-2-model-and-dx-plan.md §WP5):

* ``trust_env=False``   — ambient ``HTTP(S)_PROXY``/``NO_PROXY``/netrc are
  ignored, so no operator env var can silently re-route model traffic.
* ``follow_redirects=False`` — a 3xx is an error, not an invitation to visit
  an off-allowlist host.
* Origin allowlist re-checked at call time, not just at config load.
* Explicit connect/read/total timeouts; no unbounded wait.
* Per-instance request budget; one instance is intended per task.
* Errors carry a stable machine code and a fixed, human-written message. The
  upstream response body, the request headers and the API key are never
  interpolated into an error, a log line or an exception chain.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

import httpx

from app.config.model_provider import ModelProviderConfig
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

CHAT_COMPLETIONS_PATH = "/chat/completions"


class OpenAICompatibleProvider:
    """A single-task-scoped client for an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        config: ModelProviderConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._requests_made = 0

    # --- Introspection (safe: no key, no full URL) ---

    @property
    def config(self) -> ModelProviderConfig:
        return self._config

    @property
    def trust_env(self) -> bool:
        """Always False. Exposed so the invariant is directly assertable."""
        return False

    @property
    def requests_made(self) -> int:
        return self._requests_made

    # --- Guards ---

    def _require_ready(self) -> None:
        """Fail before any socket is opened.

        Every non-``ready`` state raises here, which is what makes
        "disabled means no network call" a structural property rather than a
        convention.
        """
        status = self._config.status()
        if status == "ready":
            return
        if status == "disabled":
            raise Phase1Error(MODEL_DISABLED, "模型能力未启用。", http_status=409)
        if status == "unconfigured":
            raise Phase1Error(
                MODEL_UNCONFIGURED, "后端未配置模型 Provider。", http_status=409
            )
        # degraded: misconfigured origin / scheme / provider kind.
        raise Phase1Error(
            MODEL_UPSTREAM_ERROR,
            "Provider 配置不满足安全要求，已拒绝出网。",
            http_status=409,
        )

    def _check_budgets(self, payload_bytes: int) -> None:
        if payload_bytes > self._config.max_input_bytes:
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED,
                "本次请求超出单任务输入字节预算。",
                http_status=413,
            )
        if self._requests_made >= self._config.max_requests_per_task:
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED,
                "本任务的 Provider 请求次数已达上限。",
                http_status=429,
            )

    def _client(self) -> httpx.Client:
        timeout = httpx.Timeout(
            self._config.total_timeout_seconds,
            connect=self._config.connect_timeout_seconds,
            read=self._config.read_timeout_seconds,
        )
        return httpx.Client(
            timeout=timeout,
            trust_env=self.trust_env,
            follow_redirects=False,
            transport=self._transport,
        )

    # --- Call ---

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        max_output_tokens: int | None = None,
    ) -> str:
        """Send one chat completion and return the assistant text.

        Raises :class:`Phase1Error` with a stable code for every failure mode.
        """
        self._require_ready()

        body = {
            "model": self._config.model_id,
            "messages": list(messages),
            "max_tokens": max_output_tokens or self._config.max_output_tokens,
            "stream": False,
        }
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._check_budgets(len(encoded))

        url = self._config.base_url.rstrip("/") + CHAT_COMPLETIONS_PATH
        headers = {
            "authorization": f"Bearer {self._config.api_key}",
            "content-type": "application/json",
            "accept": "application/json",
        }

        self._requests_made += 1
        try:
            with self._client() as client:
                response = client.post(url, content=encoded, headers=headers)
        except httpx.TimeoutException as exc:
            # `from None` keeps the upstream URL/host out of the chained traceback.
            raise Phase1Error(
                MODEL_TIMEOUT, "Provider 请求超时。", http_status=504
            ) from None
        except httpx.HTTPError:
            raise Phase1Error(
                MODEL_UPSTREAM_ERROR, "无法连接到 Provider。", http_status=502
            ) from None

        return self._parse(response)

    def _parse(self, response: httpx.Response) -> str:
        status = response.status_code

        if status in (301, 302, 303, 307, 308):
            # Never follow: the Location header may point outside the allowlist.
            raise Phase1Error(
                MODEL_UPSTREAM_ERROR,
                "Provider 返回了重定向，已按安全策略拒绝。",
                http_status=502,
            )
        if status == 429:
            raise Phase1Error(
                MODEL_RATE_LIMITED, "Provider 触发限流，请稍后重试。", http_status=429
            )
        if status >= 400:
            # The body may echo the key or user code; only the class escapes.
            raise Phase1Error(
                MODEL_UPSTREAM_ERROR,
                f"Provider 返回错误状态（HTTP {status}）。",
                http_status=502,
            )

        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            raise Phase1Error(
                MODEL_RESPONSE_INVALID, "Provider 响应不是合法 JSON。", http_status=502
            ) from None

        if not isinstance(payload, dict):
            raise Phase1Error(
                MODEL_RESPONSE_INVALID, "Provider 响应结构不符合预期。", http_status=502
            )
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise Phase1Error(
                MODEL_RESPONSE_INVALID, "Provider 响应缺少 choices。", http_status=502
            )
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise Phase1Error(
                MODEL_RESPONSE_INVALID,
                "Provider 响应缺少 assistant 文本。",
                http_status=502,
            )
        return content
