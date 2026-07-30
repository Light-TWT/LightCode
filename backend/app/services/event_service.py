"""SSE transport for task events with budgets and heartbeat.

Pure transport: it only replays persisted events (contract §API、事件与错误码)
and optionally tails for new ones. It is bounded by a replay cap, a tail
timeout, a heartbeat cadence and a max-connection cap so a slow or abusive
client cannot exhaust the server or hold a connection open indefinitely.

All limits are overridable via environment variables so tests can use short
windows without waiting on real time.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

SSE_REPLAY_CAP = int(os.environ.get("LIGHTCODE_SSE_REPLAY_CAP", "1000"))
SSE_TAIL_TIMEOUT_SECONDS = int(os.environ.get("LIGHTCODE_SSE_TAIL_SECONDS", "30"))
SSE_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("LIGHTCODE_SSE_HEARTBEAT_SECONDS", "10"))
SSE_POLL_INTERVAL_SECONDS = float(os.environ.get("LIGHTCODE_SSE_POLL_SECONDS", "0.5"))
SSE_MAX_CONNECTIONS = int(os.environ.get("LIGHTCODE_SSE_MAX_CONNECTIONS", "50"))

_active_connections = 0


class EventSource:
    """Minimal protocol the transport needs from a service."""

    def list_task_events_after(self, task_id: str, after_sequence: int) -> list:
        raise NotImplementedError


def _frame(event: object) -> str:
    # ``event`` is a TaskEventResponse; serialize with camelCase aliases.
    data = event.model_dump_json(by_alias=True)  # type: ignore[attr-defined]
    return f"id: {event.sequence}\nevent: task.event\ndata: {data}\n\n"  # type: ignore[attr-defined]


def _heartbeat() -> str:
    return ": heartbeat\n\n"


def acquire_connection() -> None:
    """Track concurrent SSE connections; raise if over the cap."""
    global _active_connections
    if _active_connections >= SSE_MAX_CONNECTIONS:
        raise RuntimeError("sse connection limit reached")
    _active_connections += 1


def release_connection() -> None:
    global _active_connections
    if _active_connections > 0:
        _active_connections -= 1


def active_connections() -> int:
    return _active_connections


def stream_events(
    service: EventSource, task_id: str, after_sequence: int, tail: bool
) -> Iterator[str]:
    """Yield SSE frames for ``task_id``.

    Without ``tail`` the stream replays pending events (capped) then ends. With
    ``tail`` it keeps polling for new events up to the tail timeout, emitting a
    heartbeat frame on the configured cadence, and finally a ``stream.end``.
    """
    try:
        acquire_connection()
    except RuntimeError:
        yield 'event: stream.error\ndata: {"reason":"connection limit reached"}\n\n'
        return
    try:
        pending = service.list_task_events_after(task_id, after_sequence)[:SSE_REPLAY_CAP]
        last = after_sequence
        for event in pending:
            yield _frame(event)
            last = event.sequence
        if not tail:
            yield "event: stream.end\ndata: {}\n\n"
            return
        deadline = time.monotonic() + SSE_TAIL_TIMEOUT_SECONDS
        last_beat = time.monotonic()
        while time.monotonic() < deadline:
            for event in service.list_task_events_after(task_id, last):
                yield _frame(event)
                last = event.sequence
            if time.monotonic() - last_beat >= SSE_HEARTBEAT_INTERVAL_SECONDS:
                yield _heartbeat()
                last_beat = time.monotonic()
            time.sleep(SSE_POLL_INTERVAL_SECONDS)
        yield "event: stream.end\ndata: {}\n\n"
    finally:
        release_connection()
