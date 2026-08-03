"""Phase 2 / WP8: observability (logging + metrics) without third-party deps.

Design constraints (docs/2026-07-30-phase-2-model-and-dx-plan.md §WP8):

* Record task/correlation IDs, state transitions, tool name/latency/category,
  provider name/model/HTTP category/latency/token aggregation, budget, SQLite
  busy, write lease (model-task concurrency gate) and SSE connect/reconnect.
* **Never** log an API key, Authorization/Cookie, full prompt/response, raw
  code, full root path, absolute path, provider request headers or an unmasked
  stack trace.

This module is the single sanctioned sink. It uses only the standard library
(``logging`` + a process-local ``Metrics`` registry); no Prometheus/client
dependency is introduced, so the capability carries zero new packages.

Secrets are scrubbed by :func:`redact` at the boundary, and :class:`Metrics`
exposes only numeric aggregates (never the values it counted).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections import defaultdict
from contextvars import ContextVar
from typing import Any, Mapping, Sequence

# --- Correlation ID -------------------------------------------------------

#: Per-request correlation id, injected by the middleware in ``app.main`` and
#: read by every logger call so a request can be traced through orchestration,
#: the provider boundary and the event stream.
correlation_id_var: ContextVar[str] = ContextVar("lightcode_correlation_id", default="-")


class CorrelationFilter(logging.Filter):
    """Attach the active correlation id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        return True


# --- Redaction (defense-in-depth) ----------------------------------------

#: Keys whose *values* must never appear in logs/metrics, even by accident.
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "proxy_authorization",
        "cookie",
        "secret",
        "password",
        "passwd",
        "token",  # broad: fileToken is benign but opaque; mask by default
    }
)

#: Keys that reveal server topology; only the scheme/allowlist verdict may log.
_LOCATION_KEYS = frozenset({"base_url", "baseurl", "root_path", "rootpath", "filepath", "file_path"})

_MASK = "***"


def _secret_string(value: str) -> str:
    """Mask well-known secret shapes inside a free-form string."""
    if not isinstance(value, str):
        return value
    masked = value
    # OpenAI-style key.
    masked = re.sub(r"sk-[A-Za-z0-9]{20,}", _MASK, masked)
    # Bearer / Basic credentials.
    masked = re.sub(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._\-]+", r"\1 " + _MASK, masked)
    return masked


def redact(obj: Any) -> Any:
    """Recursively scrub secrets/locations from a log/metric context object.

    Returns a copy; the input is never mutated. Dict keys in the secret/location
    denylists are replaced with ``_MASK``; every string is run through
    :func:`_secret_string`. This is belt-and-suspenders: callers must not place
    sensitive values in logs in the first place, but a stray payload cannot leak.
    """
    if isinstance(obj, str):
        return _secret_string(obj)
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            key_str = str(key).strip().lower()
            if key_str in _SECRET_KEYS or key_str in _LOCATION_KEYS:
                out[key] = _MASK
            else:
                out[key] = redact(value)
        return out
    if isinstance(obj, Sequence):
        return [redact(item) for item in obj]
    return obj


# --- Structured logging ---------------------------------------------------

class _JSONFormatter(logging.Formatter):
    """Emit one JSON object per record. No secret field escapes."""

    _SKIP = frozenset({"args", "msg", "message", "exc_info", "exc_text", "stack_info"})

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", "-"),
            "event": record.getMessage(),
        }
        # Attach only scrubbed structured context.
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in self._SKIP
            and k
            not in (
                "name",
                "msg",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "correlation_id",
                "message",
            )
        }
        if extra:
            payload["context"] = redact(extra)
        if record.exc_info:
            # Mask the traceback text; never surface an unmasked stack.
            payload["error"] = _secret_string(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


_LOG_CONFIGURED = False


def configure_logging() -> None:
    """Install the JSON formatter on the root logger exactly once.

    Level is ``LIGHTCODE_LOG_LEVEL`` (default ``WARNING``). Safe to call from
    the FastAPI lifespan multiple times; only the first call configures.
    """
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return
    level_name = (os.environ.get("LIGHTCODE_LOG_LEVEL") or "WARNING").strip().upper()
    level = getattr(logging, level_name, logging.WARNING)

    handler = logging.StreamHandler()
    if (os.environ.get("LIGHTCODE_LOG_FORMAT") or "json").strip().lower() == "text":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s")
        )
    else:
        handler.setFormatter(_JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # Replace any existing handlers to avoid duplicate lines under reloads.
    root.handlers = [handler]
    root.addFilter(CorrelationFilter())
    # Third-party HTTP/LLM clients log the full request URL (which embeds the
    # provider base URL) and occasionally payloads at INFO. That would violate
    # the WP8 denylist, so their verbosity is capped at WARNING here; our own
    # structured logs remain the sanctioned observability surface.
    for name in ("httpx", "httpcore", "openai", "langchain", "langchain_core", "langchain_openai"):
        logging.getLogger(name).setLevel(logging.WARNING)
    _LOG_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger whose records carry the correlation id."""
    logger = logging.getLogger(name)
    logger.addFilter(CorrelationFilter())
    return logger


# --- Metrics (process-local, numeric aggregates only) ---------------------

class _Metrics:
    """Thread-safe, in-process metric registry.

    Only numeric aggregates are stored and exposed via :meth:`snapshot`; the
    category strings are codes/state names (never secrets), so ``snapshot`` is
    safe to surface in a test assertion or a future debug endpoint.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, int] = {}
        self._hist: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum_ms": 0.0})

    # --- primitives ---
    def _inc(self, name: str, by: int = 1) -> None:
        with self._lock:
            self._counters[name] += by

    def _gauge(self, name: str, value: int) -> None:
        with self._lock:
            self._gauges[name] = value

    def _observe(self, name: str, ms: float) -> None:
        with self._lock:
            bucket = self._hist[name]
            bucket["count"] += 1
            bucket["sum_ms"] += float(ms)

    def reset(self) -> None:
        """Clear all aggregates. Intended for test isolation only."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._hist.clear()

    # --- domain helpers ---
    def task_transition(self, frm: str, to: str) -> None:
        self._inc(f"task.transition:{frm}->{to}")

    def tool_call(self, name: str, category: str, ms: float) -> None:
        self._inc(f"tool.call:{category}:{name}")
        self._observe(f"tool.latency:{category}:{name}", ms)

    def provider_call(
        self,
        provider: str,
        model: str,
        http_category: str,
        ms: float,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        # provider/model are config-derived facts (no key, no full URL).
        self._inc(f"provider.call:{provider}:{model}:{http_category}")
        self._observe(f"provider.latency:{provider}:{model}", ms)
        self._inc("provider.tokens.prompt", prompt_tokens)
        self._inc("provider.tokens.completion", completion_tokens)

    def budget_exceeded(self, code: str) -> None:
        self._inc(f"budget.exceeded:{code}")

    def sse_open(self) -> None:
        self._inc("sse.stream.started")
        with self._lock:
            self._gauges["sse.connections_active"] = self._gauges.get("sse.connections_active", 0) + 1

    def sse_close(self) -> None:
        self._inc("sse.stream.ended")
        with self._lock:
            cur = self._gauges.get("sse.connections_active", 0)
            self._gauges["sse.connections_active"] = max(0, cur - 1)

    def sse_resume(self) -> None:
        self._inc("sse.resume")

    def sqlite_busy(self) -> None:
        self._inc("sqlite.busy")

    def concurrency_rejected(self) -> None:
        self._inc("model_task.concurrency_rejected")

    def snapshot(self) -> dict[str, Any]:
        """Return only numeric aggregates — no sensitive values."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "latency_ms": {
                    name: {"count": int(b["count"]), "sum_ms": round(b["sum_ms"], 3)}
                    for name, b in self._hist.items()
                },
            }


#: Process-wide singleton. Replaced by ``reset()`` only in tests.
Metrics = _Metrics()


__all__ = [
    "correlation_id_var",
    "CorrelationFilter",
    "redact",
    "configure_logging",
    "get_logger",
    "Metrics",
]
