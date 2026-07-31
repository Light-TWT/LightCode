"""Phase 2 / WP5+WP6: hardened LangChain ``ChatOpenAI`` factory.

This is the **single** integration point for the OpenAI-compatible provider.
Every model call in the system — WP5's standalone client and WP6's LangGraph
orchestrator — goes through :func:`build_llm`, so the security boundary is
pinned in one place:

* ``trust_env=False``   — ambient ``HTTP(S)_PROXY`` / ``NO_PROXY`` / netrc are
  ignored, so no operator env var can silently re-route model traffic.
* ``follow_redirects=False`` — a 3xx is an error, not an invitation to visit an
  off-allowlist host.
* ``max_retries=0`` — the SDK must not retry behind our back; the per-task
  request budget and fail-closed semantics own the retry decision.
* Explicit connect/read/total timeouts; no unbounded wait.
* The API key lives only in the ``ChatOpenAI`` instance, built from
  ``ModelProviderConfig``; it is never serialized, logged or returned.
* LangSmith / tracing is never enabled here (no key is set, no env opt-in).

Errors are mapped to LightCode's stable ``MODEL_*`` machine codes via
:func:`map_llm_errors`, with fixed human-written messages that never
interpolate the upstream body, request headers or the API key.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator

import httpx
from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
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


def build_http_client(
    config: ModelProviderConfig, *, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    """A hardened httpx client: no proxy trust, no redirect follow, explicit timeouts."""
    timeout = httpx.Timeout(
        config.total_timeout_seconds,
        connect=config.connect_timeout_seconds,
        read=config.read_timeout_seconds,
    )
    return httpx.Client(
        transport=transport,
        trust_env=False,
        follow_redirects=False,
        timeout=timeout,
    )


def build_llm(
    config: ModelProviderConfig,
    *,
    transport: httpx.BaseTransport | None = None,
    temperature: float = 0,
) -> ChatOpenAI:
    """Build a ``ChatOpenAI`` bound to the hardened client derived from ``config``.

    Fail-closed: constructing the client performs no network I/O. The caller is
    still responsible for checking ``config.status() == 'ready'`` before
    invoking it (see :class:`app.services.openai_compatible_provider.OpenAICompatibleProvider`).
    """
    client = build_http_client(config, transport=transport)
    return ChatOpenAI(
        model=config.model_id,
        api_key=config.api_key,
        base_url=config.base_url,
        http_client=client,
        timeout=config.total_timeout_seconds,
        max_tokens=config.max_output_tokens,
        temperature=temperature,
        max_retries=0,
        streaming=False,
    )


@contextlib.contextmanager
def map_llm_errors() -> Iterator[None]:
    """Translate LangChain/OpenAI exceptions into stable ``MODEL_*`` errors.

    Upstream status codes (never bodies) may appear in the message; the raw
    response text, headers and API key are deliberately excluded via
    ``from None`` and fixed templates.
    """
    try:
        yield
    except APITimeoutError:
        raise Phase1Error(MODEL_TIMEOUT, "Provider 请求超时。", http_status=504) from None
    except RateLimitError:
        raise Phase1Error(
            MODEL_RATE_LIMITED, "Provider 触发限流，请稍后重试。", http_status=429
        ) from None
    except APIConnectionError:
        raise Phase1Error(
            MODEL_UPSTREAM_ERROR, "无法连接到 Provider。", http_status=502
        ) from None
    except APIStatusError as exc:
        status = getattr(exc, "status_code", None)
        if status == 429:
            raise Phase1Error(
                MODEL_RATE_LIMITED, "Provider 触发限流，请稍后重试。", http_status=429
            ) from None
        raise Phase1Error(
            MODEL_UPSTREAM_ERROR,
            f"Provider 返回错误状态（HTTP {status}）。",
            http_status=502,
        ) from None
    except APIError:
        # Malformed JSON, missing choices, or response-schema validation failure.
        raise Phase1Error(
            MODEL_RESPONSE_INVALID, "Provider 响应不符合预期。", http_status=502
        ) from None
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        # The model-call boundary must never leak or crash on a malformed
        # upstream payload. LangChain/openai can surface a raw string or raise a
        # parsing-time builtin when the body is not a valid chat completion, so
        # we treat any such failure as an invalid response (spec §WP5).
        raise Phase1Error(
            MODEL_RESPONSE_INVALID, "Provider 响应无法解析。", http_status=502
        ) from None


__all__ = ["build_http_client", "build_llm", "map_llm_errors"]
