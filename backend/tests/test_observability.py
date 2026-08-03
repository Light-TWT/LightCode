"""WP8 observability unit tests (Phase 2).

Verifies the metric counters, the denylist redaction and the SQLite-busy
instrumentation. None of these tests touch the network or a real model; the
provider/transport paths are covered by ``test_model_e2e.py``.
"""

from __future__ import annotations

import logging
import sqlite3

import pytest

from app.db.database import InstrumentedConnection, initialize_database
from app.services.model_orchestrator import _gate
from app.services.observability import (
    Metrics,
    correlation_id_var,
    get_logger,
    redact,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    Metrics.reset()
    _gate.reset()
    yield
    Metrics.reset()
    _gate.reset()


# --- redaction -------------------------------------------------------------


def test_redact_masks_secret_keys_and_locations():
    payload = {
        "api_key": "sk-1234567890abcdefghij",
        "authorization": "Bearer topsecret",
        "base_url": "https://provider.example.test/v1",
        "root_path": "/home/user/secret",
        "task_id": "model-task-abc",
        "count": 3,
    }
    scrubbed = redact(payload)
    assert scrubbed["api_key"] == "***"
    assert scrubbed["authorization"] == "***"
    assert scrubbed["base_url"] == "***"
    assert scrubbed["root_path"] == "***"
    # benign fields survive untouched
    assert scrubbed["task_id"] == "model-task-abc"
    assert scrubbed["count"] == 3


def test_redact_masks_secret_shapes_in_strings():
    text = "key=sk-1234567890abcdefghij and Authorization: Bearer xyz"
    scrubbed = redact(text)
    assert "sk-1234567890abcdefghij" not in scrubbed
    assert "Bearer xyz" not in scrubbed
    assert "***" in scrubbed


# --- metrics ----------------------------------------------------------------


def test_metrics_record_aggregates_without_secrets():
    Metrics.task_transition("planning", "awaiting_approval")
    Metrics.tool_call("read_file", "model_read", 12.5)
    Metrics.provider_call("openai-compatible", "test-model", "success", 30.0, 10, 5)
    Metrics.sse_open()
    Metrics.sse_resume()
    Metrics.sqlite_busy()
    Metrics.budget_exceeded("MODEL_BUDGET_EXCEEDED")
    Metrics.concurrency_rejected()

    snap = Metrics.snapshot()
    counters = snap["counters"]
    assert counters["task.transition:planning->awaiting_approval"] == 1
    assert counters["tool.call:model_read:read_file"] == 1
    assert counters["provider.call:openai-compatible:test-model:success"] == 1
    assert counters["provider.tokens.prompt"] == 10
    assert counters["provider.tokens.completion"] == 5
    assert counters["sse.stream.started"] == 1
    assert counters["sse.resume"] == 1
    assert counters["sqlite.busy"] == 1
    assert counters["budget.exceeded:MODEL_BUDGET_EXCEEDED"] == 1
    assert counters["model_task.concurrency_rejected"] == 1
    assert snap["gauges"]["sse.connections_active"] == 1
    # latency histogram carries counts/sums only, never the prompt/response.
    assert snap["latency_ms"]["provider.latency:openai-compatible:test-model"]["count"] == 1


# --- correlation id ---------------------------------------------------------


def test_correlation_id_propagates_to_log_record(caplog):
    correlation_id_var.set("cid-123")
    logger = get_logger("lightcode.test")
    with caplog.at_level(logging.INFO):
        logger.info("orchestration step", extra={"task_id": "t1"})
    assert any(
        getattr(rec, "correlation_id", None) == "cid-123" for rec in caplog.records
    )
    correlation_id_var.set("-")


# --- sqlite busy ------------------------------------------------------------


def test_instrumented_connection_counts_busy():
    # sqlite3.Connection is an immutable C type whose execute cannot be
    # monkeypatched, so drive the wrapper with a fake underlying connection
    # that raises a busy/locked error. The wrapper must record the metric.
    class _BusyConn:
        def execute(self, *args, **kwargs):
            raise sqlite3.OperationalError("database is locked")

        def executemany(self, *args, **kwargs):
            raise sqlite3.OperationalError("database is busy")

    db = InstrumentedConnection(_BusyConn())
    with pytest.raises(sqlite3.OperationalError):
        db.execute("SELECT 1")
    with pytest.raises(sqlite3.OperationalError):
        db.executemany("INSERT INTO t VALUES (?)", [(1,)])
    assert Metrics.snapshot()["counters"]["sqlite.busy"] == 2


def test_instrumented_connection_preserves_delegation(tmp_path):
    db = initialize_database(tmp_path / "lightcode.db")
    assert isinstance(db, InstrumentedConnection)
    # A normal statement still works and the context-manager protocol is intact.
    with db:
        row = db.execute("SELECT 1 AS v").fetchone()
    assert row["v"] == 1
    db.close()


# --- provider error classification -----------------------------------------


def test_provider_error_classification():
    from app.services.openai_compatible_provider import OpenAICompatibleProvider
    from app.schemas.errors import (
        MODEL_BUDGET_EXCEEDED,
        MODEL_RATE_LIMITED,
        MODEL_RESPONSE_INVALID,
        MODEL_TIMEOUT,
        MODEL_UPSTREAM_ERROR,
    )

    assert OpenAICompatibleProvider._classify_error(MODEL_TIMEOUT) == "timeout"
    assert OpenAICompatibleProvider._classify_error(MODEL_RATE_LIMITED) == "rate_limit"
    assert OpenAICompatibleProvider._classify_error(MODEL_UPSTREAM_ERROR) == "upstream"
    assert OpenAICompatibleProvider._classify_error(MODEL_RESPONSE_INVALID) == "invalid"
    assert OpenAICompatibleProvider._classify_error(MODEL_BUDGET_EXCEEDED) == "budget"
    assert OpenAICompatibleProvider._classify_error("UNKNOWN_CODE") == "error"


def test_provider_records_failure_metric_when_disabled():
    """A disabled config raises before any socket and must still be recorded."""
    from app.config.model_provider import ModelProviderConfig
    from app.services.openai_compatible_provider import OpenAICompatibleProvider
    from app.schemas.errors import MODEL_DISABLED, Phase1Error

    disabled = ModelProviderConfig(
        enabled=False,
        provider="openai-compatible",
        base_url="https://api.example.test/v1",
        model_id="test-model",
        allowed_origins=("https://api.example.test",),
        connect_timeout_seconds=5.0,
        read_timeout_seconds=45.0,
        total_timeout_seconds=60.0,
        max_tool_rounds=8,
        max_input_bytes=262_144,
        max_output_tokens=2048,
        max_requests_per_task=10,
        max_concurrent_tasks=1,
        allow_insecure_http=False,
        api_key="test-key",
    )
    provider = OpenAICompatibleProvider(disabled)
    with pytest.raises(Phase1Error) as excinfo:
        provider.chat([{"role": "user", "content": "x"}])
    assert excinfo.value.code == MODEL_DISABLED
    assert Metrics.snapshot()["counters"]["provider.call:openai-compatible:test-model:disabled"] >= 1


# --- concurrency gate -------------------------------------------------------


def test_concurrency_gate_records_rejection(monkeypatch, tmp_path):
    """A full gate must route the task to a stable fail-closed code and metric."""
    import json
    from pathlib import Path

    from app.config.model_provider import ModelProviderConfig
    from app.services.model_orchestrator import ModelOrchestrator

    ws_root = tmp_path / "proj"
    ws_root.mkdir()
    target = ws_root / "notes.txt"
    target.write_text("first line\nsecond line\n", encoding="utf-8", newline="")
    config = {
        "workspaces": [
            {
                "id": "ws-demo",
                "displayName": "Demo",
                "rootPath": str(ws_root),
                "policy": "phase1-single-text-file",
                "targetFile": "notes.txt",
                "enabled": True,
            }
        ]
    }
    config_path = tmp_path / "workspaces.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    from app.security.guard import WorkspaceGuard
    from app.workspaces.registry import WorkspaceRegistry

    registry = WorkspaceRegistry.load(config_path)
    guard = WorkspaceGuard(registry)
    db = initialize_database(tmp_path / "lightcode.db")

    # Force the gate to report "full" regardless of config.
    monkeypatch.setattr(_gate, "try_acquire", lambda _max: False)

    cfg = ModelProviderConfig(
        enabled=True,
        provider="openai-compatible",
        base_url="https://api.example.test/v1",
        model_id="test-model",
        allowed_origins=("https://api.example.test",),
        connect_timeout_seconds=5.0,
        read_timeout_seconds=45.0,
        total_timeout_seconds=60.0,
        max_tool_rounds=8,
        max_input_bytes=262_144,
        max_output_tokens=2048,
        max_requests_per_task=10,
        max_concurrent_tasks=1,
        allow_insecure_http=False,
        api_key="test-key",
    )
    orch = ModelOrchestrator(db, registry, guard, cfg)
    resp = orch.create_model_task("ws-demo", "edit")
    assert resp.state == "failed"
    detail = db.execute(
        "SELECT verification_detail FROM tasks WHERE id = ?", (resp.id,)
    ).fetchone()["verification_detail"]
    assert detail.startswith("MODEL_CONCURRENCY_EXCEEDED")
    assert Metrics.snapshot()["counters"]["model_task.concurrency_rejected"] >= 1
    db.close()
