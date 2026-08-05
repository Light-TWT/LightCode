"""Phase 2 / WP5: hardened OpenAI-compatible chat client (backed by LangChain).

This is the **only** place in the codebase permitted to make an outbound
model call in WP5, and it is deliberately not wired into any task flow yet —
WP6 (``model_orchestrator``) will consume it. The hardened transport and the
error-code mapping now live in :mod:`app.services.llm_client`, the single
integration point for LangChain, so the security behaviour is pinned before
the model can influence a ChangeSet.

Hardening (docs/2026-07-30-phase-2-model-and-dx-plan.md §WP5):

* ``trust_env=False``   — ambient ``HTTP(S)_PROXY`` / ``NO_PROXY`` / netrc are
  ignored, so no operator env var can silently re-route model traffic.
* ``follow_redirects=False`` — a 3xx is an error, not an invitation to visit an
  off-allowlist host.
* ``max_retries=0`` — the SDK never retries behind our back; the per-task
  request budget owns that decision.
* Origin allowlist is enforced at config load (``ModelProviderConfig.status``);
  a ``degraded`` config is rejected before any socket opens.
* Explicit connect/read/total timeouts; no unbounded wait.
* Per-instance request budget; one instance is intended per task.
* Errors carry a stable machine code and a fixed, human-written message. The
  upstream response body, the request headers and the API key are never
  interpolated into an error, a log line or an exception chain.
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Sequence

import httpx
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

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
from app.services.llm_client import build_llm, map_llm_errors
from app.services.observability import Metrics

_ROLE_TO_MESSAGE: Mapping[str, type[BaseMessage]] = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


def _to_langchain_messages(messages: Sequence[Mapping[str, Any]]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        message_cls = _ROLE_TO_MESSAGE.get(role, HumanMessage)
        converted.append(message_cls(content=content))
    return converted


class OpenAICompatibleProvider:
    """A single-task-scoped client for an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        config: ModelProviderConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        temperature: float = 0,
    ) -> None:
        self._config = config
        self._transport = transport
        self._temperature = temperature
        self._requests_made = 0
        self._llm: ChatOpenAI | None = None  # type: ignore[name-defined]

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
            Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED,
                "本次请求超出单任务输入字节预算。",
                http_status=413,
            )
        if self._requests_made >= self._config.max_requests_per_task:
            Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED,
                "本任务的 Provider 请求次数已达上限。",
                http_status=429,
            )

    def _llm_client(self):  # type: ignore[no-untyped-def]
        if self._llm is None:
            self._llm = build_llm(
                self._config, transport=self._transport, temperature=self._temperature
            )
        return self._llm

    # --- Call ---

    @staticmethod
    def _classify_error(code: str) -> str:
        """Map a stable ``MODEL_*`` code to a coarse HTTP-category label.

        The label is a code, never the upstream body, headers or key.
        """
        return {
            MODEL_TIMEOUT: "timeout",
            MODEL_RATE_LIMITED: "rate_limit",
            MODEL_UPSTREAM_ERROR: "upstream",
            MODEL_RESPONSE_INVALID: "invalid",
            MODEL_BUDGET_EXCEEDED: "budget",
            MODEL_DISABLED: "disabled",
            MODEL_UNCONFIGURED: "unconfigured",
        }.get(code, "error")

    @staticmethod
    def _extract_tokens(ai_message: Any) -> tuple[int, int]:
        """Safely pull token counts from the LangChain response metadata.

        Only integer counts escape — never the prompt text, the response body,
        the API key or the provider request headers.
        """
        try:
            usage = (ai_message.response_metadata or {}).get("token_usage", {}) or {}
            prompt = int(usage.get("prompt_tokens", 0) or 0)
            completion = int(usage.get("completion_tokens", 0) or 0)
            return prompt, completion
        except (AttributeError, TypeError, ValueError):
            return 0, 0

    def _check_output_budget(
        self, content: str, completion_tokens: int, max_output_tokens: int
    ) -> None:
        """Enforce the output budget locally, after the provider has replied.

        ``max_tokens`` in the request body is a hint, not a guarantee: a
        non-compliant provider can ignore it. If the reported
        ``completion_tokens`` exceeds the budget we fail closed. When usage is
        missing or unparseable (``completion_tokens == 0``) we fall back to a
        conservative UTF-8 byte limit (≤ 4 bytes per token) so an oversized
        body cannot be treated as zero cost.
        """
        if completion_tokens > 0 and completion_tokens > max_output_tokens:
            Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED,
                "Provider 响应超出单任务输出预算。",
                http_status=502,
            )
        if completion_tokens == 0 and len(content.encode("utf-8")) > max_output_tokens * 4:
            Metrics.budget_exceeded(MODEL_BUDGET_EXCEEDED)
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED,
                "Provider 响应超出单任务输出预算。",
                http_status=502,
            )

    def test_connection(self) -> None:
        """Minimal, budgeted round-trip to verify provider connectivity.

        Fail-closed: any non-``ready`` config raises before a socket opens; a
        missing/empty response is treated as an upstream error. Nothing is
        persisted, logged or returned beyond a stable success/error signal.
        """
        self._require_ready()
        with map_llm_errors():
            ai_message = self._llm_client().invoke(
                _to_langchain_messages([{"role": "user", "content": "ping"}])
            )
        content = ai_message.content if isinstance(ai_message.content, str) else ""
        if not content:
            raise Phase1Error(
                MODEL_UPSTREAM_ERROR,
                "Provider 响应缺少 assistant 文本。",
                http_status=502,
            )

    def chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        max_output_tokens: int | None = None,
    ) -> str:
        """Send one chat completion and return the assistant text.

        Raises :class:`Phase1Error` with a stable code for every failure mode.
        Records provider latency, HTTP category and token aggregation to
        :class:`Metrics`; no prompt, response, key or header is ever measured
        beyond opaque counts.
        """
        provider = self._config.provider
        model = self._config.model_id
        t0 = time.monotonic()
        effective_max_output_tokens = max_output_tokens or self._config.max_output_tokens
        try:
            self._require_ready()

            body = {
                "model": self._config.model_id,
                "messages": list(messages),
                "max_tokens": effective_max_output_tokens,
                "stream": False,
            }
            encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            self._check_budgets(len(encoded))

            self._requests_made += 1
            with map_llm_errors():
                ai_message = self._llm_client().invoke(_to_langchain_messages(messages))
            prompt_tokens, completion_tokens = self._extract_tokens(ai_message)
            content = ai_message.content if isinstance(ai_message.content, str) else ""
            if not content:
                raise Phase1Error(
                    MODEL_UPSTREAM_ERROR,
                    "Provider 响应缺少 assistant 文本。",
                    http_status=502,
                )
            # Local output-budget enforcement after the provider has replied
            # (fail-closed; the Phase1Error below is recorded via this branch).
            self._check_output_budget(
                content, completion_tokens, effective_max_output_tokens
            )
        except Phase1Error as exc:
            latency = (time.monotonic() - t0) * 1000
            Metrics.provider_call(
                provider=provider,
                model=model,
                http_category=self._classify_error(exc.code),
                ms=latency,
                prompt_tokens=0,
                completion_tokens=0,
            )
            raise

        latency = (time.monotonic() - t0) * 1000
        Metrics.provider_call(
            provider=provider,
            model=model,
            http_category="success",
            ms=latency,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return content
