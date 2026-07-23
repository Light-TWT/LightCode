from app.db.database import initialize_database


def test_initialize_database_seeds_current_workspace(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    connection = initialize_database(database_path)

    row = connection.execute(
        "SELECT id, name FROM workspaces WHERE id = ?",
        ("workspace-login-service",),
    ).fetchone()

    assert tuple(row) == ("workspace-login-service", "login-service")


def test_initialize_database_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "lightcode.db"
    initialize_database(database_path)
    connection = initialize_database(database_path)

    count = connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
    assert count == 7
