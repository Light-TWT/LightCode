"""Tests for the SSE transport budgets and heartbeat (event_service).

The transport only replays persisted events and optionally tails; it must be
bounded (replay cap, tail timeout, heartbeat, max connections) and resume via
after_sequence. These tests verify those invariants without real time pressure
by overriding the module-level limits.
"""

import json
from types import SimpleNamespace

import pytest

from app.services import event_service


def _ev(seq: int, event_type: str, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        sequence=seq,
        eventType=event_type,
        payload=payload,
        createdAt="t",
        model_dump_json=lambda by_alias=False: json.dumps(
            {"sequence": seq, "eventType": event_type, "payload": payload, "createdAt": "t"}
        ),
    )


class FakeSource:
    def __init__(self, events: list) -> None:
        self._events = events

    def list_task_events_after(self, task_id: str, after_sequence: int) -> list:
        return [e for e in self._events if e.sequence > after_sequence]


def test_stream_replays_and_ends() -> None:
    src = FakeSource([_ev(1, "task.created", {}), _ev(2, "task.completed", {})])
    text = "".join(event_service.stream_events(src, "t1", 0, tail=False))
    assert "id: 1" in text
    assert "id: 2" in text
    assert "stream.end" in text


def test_resume_after_sequence() -> None:
    src = FakeSource([_ev(1, "a", {}), _ev(2, "b", {}), _ev(3, "c", {})])
    text = "".join(event_service.stream_events(src, "t1", 2, tail=False))
    assert "id: 1" not in text
    assert "id: 2" not in text
    assert "id: 3" in text


def test_replay_cap(monkeypatch) -> None:
    monkeypatch.setattr("app.services.event_service.SSE_REPLAY_CAP", 2)
    events = [_ev(i, "task.event", {}) for i in range(1, 10)]
    src = FakeSource(events)
    text = "".join(event_service.stream_events(src, "t1", 0, tail=False))
    assert "id: 1" in text and "id: 2" in text
    assert "id: 3" not in text


def test_stream_heartbeat_while_tailing(monkeypatch) -> None:
    monkeypatch.setattr("app.services.event_service.SSE_TAIL_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr("app.services.event_service.SSE_HEARTBEAT_INTERVAL_SECONDS", 0.2)
    monkeypatch.setattr("app.services.event_service.SSE_POLL_INTERVAL_SECONDS", 0.1)
    src = FakeSource([])
    text = "".join(event_service.stream_events(src, "t1", 0, tail=True))
    assert ": heartbeat" in text
    assert "stream.end" in text


def test_connection_limit_rejects_over_cap(monkeypatch) -> None:
    monkeypatch.setattr("app.services.event_service.SSE_MAX_CONNECTIONS", 0)
    src = FakeSource([])
    text = "".join(event_service.stream_events(src, "t1", 0, tail=False))
    assert "stream.error" in text
    assert event_service.active_connections() == 0


def test_concurrent_acquire_honors_cap(monkeypatch) -> None:
    """L-01: the in-process connection cap must be atomic under contention.

    Two threads race a cap of 1. We shrink the GIL switch interval so the
    check-and-increment interleaves deterministically; without the lock both
    threads pass the guard. The winner keeps holding its slot until the main
    thread releases the gate, so the loser is guaranteed to queue on the lock
    and observe the already-taken slot instead of a reset-to-zero counter.
    """
    import sys
    import threading
    import time

    monkeypatch.setattr("app.services.event_service.SSE_MAX_CONNECTIONS", 1)
    monkeypatch.setattr("app.services.event_service._active_connections", 0)

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        barrier = threading.Barrier(2)
        release_gate = threading.Event()
        results: list[str] = []
        results_lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            try:
                event_service.acquire_connection()
                with results_lock:
                    results.append("ok")
                # Keep holding the slot: the other thread must queue on the
                # lock and see the taken slot, never a reset counter.
                release_gate.wait(timeout=5)
                event_service.release_connection()
            except RuntimeError:
                with results_lock:
                    results.append("rejected")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        # Give both threads time to reach the acquire critical point.
        time.sleep(0.05)
        release_gate.set()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old_interval)

    assert sorted(results) == ["ok", "rejected"]
    assert event_service.active_connections() == 0
