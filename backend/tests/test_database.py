import sqlite3

import pytest

from app.db.database import initialize_database, run_migrations


def test_initialize_database_creates_chat_schema(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    connection = initialize_database(database_path)

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"chat_sessions", "chat_messages", "tasks", "changesets", "approvals"} <= tables
    # Mock-only tables are gone.
    assert "workspaces" not in tables
    assert "task_history" not in tables

    # tasks carry the chat_session_id linkage column.
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
    assert "chat_session_id" in columns


def test_initialize_database_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    initialize_database(database_path)
    connection = initialize_database(database_path)

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "chat_messages" in tables


def test_migration_drops_mock_tables_and_backfills_chat_column(tmp_path) -> None:
    """An old Phase 0.5 database keeps its data, gains chat columns and loses
    the mock-only tables."""
    database_path = tmp_path / "legacy.db"
    raw = sqlite3.connect(str(database_path))
    raw.execute("CREATE TABLE workspaces (id TEXT PRIMARY KEY)")
    raw.execute("CREATE TABLE task_history (id TEXT PRIMARY KEY)")
    raw.execute(
        """CREATE TABLE tasks (
            id TEXT PRIMARY KEY, session_id TEXT, workspace_id TEXT, title TEXT,
            state TEXT, plan_json TEXT, tool_calls_json TEXT, model_output TEXT,
            changeset_status TEXT, verification_status TEXT, verification_command TEXT,
            verification_lines_json TEXT
        )"""
    )
    raw.execute("INSERT INTO workspaces (id) VALUES ('ws-legacy')")
    raw.commit()
    raw.close()

    connection = initialize_database(database_path)

    tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "workspaces" not in tables
    assert "task_history" not in tables

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
    for expected in ("kind", "target_file", "changeset_id", "verification_detail", "chat_session_id"):
        assert expected in columns


def test_run_migrations_is_idempotent_on_fresh_database(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    connection = initialize_database(database_path)
    # Running migrations again must not raise (duplicate column etc.).
    run_migrations(connection)
