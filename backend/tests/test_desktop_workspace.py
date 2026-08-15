"""Phase 3 desktop workspace registration tests.

Covers the server-controlled dynamic registration of a selected folder: token
authentication, canonical/reparse validation, folder-name display derivation,
persistence across restart, and a strict no-path-leak contract on the response.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

TOKEN_HEADER = "x-lightcode-sidecar-token"
TEST_TOKEN = "test-sidecar-token"


@pytest.fixture
def desktop_client(tmp_path):
    data_dir = tmp_path / "desktop-data"
    os.environ["LIGHTCODE_DESKTOP_DATA_DIR"] = str(data_dir)
    os.environ["LIGHTCODE_SIDECAR_TOKEN"] = TEST_TOKEN
    os.environ["LIGHTCODE_SIDECAR_PORT"] = "8123"
    with TestClient(app) as c:
        yield c
    for key in (
        "LIGHTCODE_DESKTOP_DATA_DIR",
        "LIGHTCODE_SIDECAR_TOKEN",
        "LIGHTCODE_SIDECAR_PORT",
    ):
        os.environ.pop(key, None)


def _register(client, root_path, token=None):
    headers = {}
    if token is not None:
        headers[TOKEN_HEADER] = token
    return client.post(
        "/api/v1/desktop/workspaces/register",
        json={"rootPath": root_path},
        headers=headers,
    )


def test_register_desktop_workspace_returns_safe_dto_and_persists(
    desktop_client, tmp_path
) -> None:
    proj = tmp_path / "my-project"
    proj.mkdir()
    resp = _register(desktop_client, str(proj), TEST_TOKEN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"]
    assert body["displayName"] == "my-project"
    assert body["enabled"] is True
    assert body["capabilities"] == ["list_files", "read_file", "search_files"]
    assert body["policyVersion"]
    # No absolute path anywhere in the response.
    assert str(proj) not in resp.text
    assert "rootPath" not in body


def test_register_duplicate_canonical_root_is_idempotent(desktop_client, tmp_path) -> None:
    proj = tmp_path / "dup"
    proj.mkdir()
    first = _register(desktop_client, str(proj), TEST_TOKEN)
    assert first.status_code == 200
    # Re-selecting the same folder re-opens the existing workspace: same id,
    # no duplicate row, no error.
    second = _register(desktop_client, str(proj), TEST_TOKEN)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_register_relative_root_rejected(desktop_client, tmp_path) -> None:
    resp = _register(desktop_client, "relative/path", TEST_TOKEN)
    assert resp.status_code == 400
    assert resp.json()["code"] == "DESKTOP_WORKSPACE_INVALID"


def test_register_non_directory_root_rejected(desktop_client, tmp_path) -> None:
    missing = tmp_path / "does-not-exist"
    resp = _register(desktop_client, str(missing), TEST_TOKEN)
    assert resp.status_code == 400
    assert resp.json()["code"] == "DESKTOP_WORKSPACE_INVALID"


def test_register_reparse_point_root_rejected(desktop_client, tmp_path, monkeypatch) -> None:
    proj = tmp_path / "linklike"
    proj.mkdir()
    monkeypatch.setattr(
        "app.services.workspace_registration.is_link_or_reparse", lambda p: True
    )
    resp = _register(desktop_client, str(proj), TEST_TOKEN)
    assert resp.status_code == 400
    assert resp.json()["code"] == "DESKTOP_WORKSPACE_INVALID"


def test_register_missing_or_wrong_token_rejected(desktop_client, tmp_path) -> None:
    proj = tmp_path / "tok"
    proj.mkdir()
    assert _register(desktop_client, str(proj)).status_code == 401
    assert _register(desktop_client, str(proj), "wrong-token").status_code == 401
    assert _register(desktop_client, str(proj), TEST_TOKEN).status_code == 200


def test_register_disabled_outside_desktop_mode(tmp_path) -> None:
    os.environ["LIGHTCODE_DATABASE_PATH"] = str(tmp_path / "web.db")
    os.environ.pop("LIGHTCODE_DESKTOP_DATA_DIR", None)
    try:
        with TestClient(app) as c:
            proj = tmp_path / "webproj"
            proj.mkdir()
            resp = _register(c, str(proj), TEST_TOKEN)
            assert resp.status_code in (400, 404)
            # Outside desktop mode the endpoint must not register anything.
            assert resp.json()["code"] == "DESKTOP_MODE_DISABLED"
    finally:
        os.environ.pop("LIGHTCODE_DATABASE_PATH", None)


def test_desktop_workspaces_persist_across_restart(desktop_client, tmp_path) -> None:
    proj = tmp_path / "persist"
    proj.mkdir()
    first = _register(desktop_client, str(proj), TEST_TOKEN)
    assert first.status_code == 200
    ws_id = first.json()["id"]

    # Re-enter the app lifespan against the same desktop data dir: the registry
    # must reload the previously registered workspace from SQLite.
    with TestClient(app) as c:
        workspaces = c.get("/api/v1/registered-workspaces").json()
        assert any(w["id"] == ws_id for w in workspaces)


def test_desktop_registration_no_path_in_listed_workspaces(desktop_client, tmp_path) -> None:
    proj = tmp_path / "secrethome"
    proj.mkdir()
    assert _register(desktop_client, str(proj), TEST_TOKEN).status_code == 200
    listed = desktop_client.get("/api/v1/registered-workspaces").json()
    assert str(proj) not in str(listed)