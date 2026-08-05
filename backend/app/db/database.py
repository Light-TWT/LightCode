import sqlite3
from pathlib import Path
from typing import Optional

from app.services.observability import Metrics

SCHEMA_SQL = """
-- 会话（真实/模型任务使用；聊天会话见 chat_sessions）
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'created',
    plan_json TEXT NOT NULL DEFAULT '[]',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    model_output TEXT NOT NULL DEFAULT '',
    changeset_status TEXT NOT NULL DEFAULT 'pending',
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verification_command TEXT NOT NULL DEFAULT '',
    verification_lines_json TEXT NOT NULL DEFAULT '[]',
    kind TEXT NOT NULL DEFAULT 'real',
    target_file TEXT NOT NULL DEFAULT '',
    changeset_id TEXT NOT NULL DEFAULT '',
    verification_detail TEXT NOT NULL DEFAULT '',
    chat_session_id TEXT NOT NULL DEFAULT ''
);

-- Phase 1: server-generated, immutable, versioned ChangeSets.
CREATE TABLE IF NOT EXISTS changesets (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    logical_relative_path TEXT NOT NULL,
    base_sha256 TEXT NOT NULL,
    proposed_sha256 TEXT NOT NULL,
    diff_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    before_json TEXT NOT NULL DEFAULT '[]',
    after_json TEXT NOT NULL DEFAULT '[]',
    base_text TEXT NOT NULL DEFAULT '',
    proposed_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL DEFAULT ''
);

-- Phase 1: version-bound approval records with idempotency.
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changeset_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    revision INTEGER NOT NULL,
    diff_hash TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'pending',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE(idempotency_key)
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE(task_id, sequence)
);

-- 核心 Agent 更新（阶段 A）：聊天会话与消息持久化。
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'message',
    task_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE(session_id, sequence)
);
"""


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


class InstrumentedConnection:
    """Thin wrapper that counts SQLite ``busy``/``locked`` errors as a metric.

    It preserves the existing engine-level retry (``PRAGMA busy_timeout``) and
    the context-manager protocol used throughout the codebase. Only
    ``execute``/``executemany`` are intercepted; every other attribute (including
    ``commit`` via the underlying ``with`` block) is delegated unchanged. No
    schema or migration semantics are touched.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __getattr__(self, name: str):
        # Only reached for attributes not defined on this class (row_factory,
        # cursor, commit, close, executescript, ...).
        return getattr(self._conn, name)

    def __enter__(self) -> sqlite3.Connection:
        return self._conn.__enter__()

    def __exit__(self, *exc_info: object) -> None:
        self._conn.__exit__(*exc_info)

    @staticmethod
    def _count_busy(exc: Exception) -> None:
        text = str(exc).lower()
        if "locked" in text or "busy" in text:
            Metrics.sqlite_busy()

    def execute(self, *args, **kwargs):
        try:
            return self._conn.execute(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            self._count_busy(exc)
            raise

    def executemany(self, *args, **kwargs):
        try:
            return self._conn.executemany(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            self._count_busy(exc)
            raise


def run_migrations(connection: sqlite3.Connection) -> None:
    """Idempotently upgrade a pre-existing database to the current schema.

    Fresh databases already receive the new columns/tables from SCHEMA_SQL; this
    only backfills columns that older databases are missing. Mock-only tables
    (``workspaces``, ``task_history``) are dropped: the product no longer has a
    Mock runtime, and their seed data is not read by any new business flow.
    """
    task_columns = _column_names(connection, "tasks")
    changeset_columns = _column_names(connection, "changesets")
    # (column_name, target_table, ddl) — keyed by the table that owns the column
    # so the existence check queries the correct table.
    migrations = {
        "kind": ("tasks", "ALTER TABLE tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'real'"),
        "target_file": ("tasks", "ALTER TABLE tasks ADD COLUMN target_file TEXT NOT NULL DEFAULT ''"),
        "changeset_id": ("tasks", "ALTER TABLE tasks ADD COLUMN changeset_id TEXT NOT NULL DEFAULT ''"),
        "verification_detail": ("tasks", "ALTER TABLE tasks ADD COLUMN verification_detail TEXT NOT NULL DEFAULT ''"),
        "expires_at": ("changesets", "ALTER TABLE changesets ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''"),
        "chat_session_id": ("tasks", "ALTER TABLE tasks ADD COLUMN chat_session_id TEXT NOT NULL DEFAULT ''"),
    }
    for column, (table, statement) in migrations.items():
        existing = task_columns if table == "tasks" else changeset_columns
        if column not in existing:
            connection.execute(statement)

    # Mock-only tables removed in the 核心 Agent 更新（阶段 A）migration.
    for table in ("workspaces", "task_history"):
        if table in _table_names(connection):
            connection.execute(f"DROP TABLE IF EXISTS {table}")


def initialize_database(database_path: Optional[Path] = None) -> sqlite3.Connection:
    if database_path is None:
        # 回退路径同样基于本文件位置解析为绝对路径，避免依赖启动目录。
        database_path = Path(__file__).resolve().parent.parent.parent / "data" / "lightcode.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(database_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # WAL 提升并发读吞吐并降低写锁等待；busy_timeout 避免多连接短竞态下抛
    # "database is locked"。两者均为对既有 schema/迁移语义透明的引擎级调优。
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.executescript(SCHEMA_SQL)
    run_migrations(connection)
    connection.commit()
    return InstrumentedConnection(connection)
