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
    MODEL_UNCONFIGURED,
    MODEL_UPSTREAM_ERROR,
    Phase1Error,
)
from app.services.llm_client import build_llm, map_llm_errors

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

    def _llm_client(self):  # type: ignore[no-untyped-def]
        if self._llm is None:
            self._llm = build_llm(
                self._config, transport=self._transport, temperature=self._temperature
            )
        return self._llm

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
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self._check_budgets(len(encoded))

        self._requests_made += 1
        with map_llm_errors():
            ai_message = self._llm_client().invoke(_to_langchain_messages(messages))

        content = ai_message.content if isinstance(ai_message.content, str) else ""
        if not content:
            raise Phase1Error(
                MODEL_UPSTREAM_ERROR,
                "Provider 响应缺少 assistant 文本。",
                http_status=502,
            )
        return content
