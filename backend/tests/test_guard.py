from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.schemas.errors import (
    FILE_SIZE_DENIED,
    FILE_TYPE_DENIED,
    PATH_POLICY_DENIED,
    SECRET_FILE_DENIED,
    SYMLINK_DENIED,
    Phase1Error,
    WORKSPACE_DISABLED,
    WORKSPACE_NOT_REGISTERED,
)
from app.security.guard import WorkspaceGuard
from app.workspaces.registry import (
    PHASE1_POLICY,
    RegistryWorkspace,
    WorkspaceRegistry,
)


def _make_registry(root: Path, *, enabled: bool = True) -> WorkspaceGuard:
    ws = RegistryWorkspace(
        id="ws1",
        display_name="WS1",
        canonical_root=root.resolve(),
        enabled=enabled,
        policy=PHASE1_POLICY,
        policy_version=PHASE1_POLICY,
        target_file="notes.txt",
    )
    return WorkspaceGuard(WorkspaceRegistry([ws]))


@pytest.fixture
def guard(tmp_path: Path) -> WorkspaceGuard:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "notes.txt").write_text("hello world\nsecond line\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "deep.txt").write_text("nested content", encoding="utf-8")
    (root / "broken.bin").write_bytes(b"\xff\xfe\x00\x01")
    big = root / "big.bin"
    big.write_bytes(b"x" * (1_000_001))
    return _make_registry(root)


def test_read_valid_file(guard: WorkspaceGuard) -> None:
    assert "hello world" in guard.read_text("ws1", "notes.txt")


def test_traversal_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "../etc/passwd")
    assert exc.value.code == PATH_POLICY_DENIED


def test_absolute_path_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "/etc/passwd")
    assert exc.value.code == PATH_POLICY_DENIED


def test_drive_path_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "C:windows/system.ini")
    assert exc.value.code == PATH_POLICY_DENIED


def test_backslash_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "a\\b.txt")
    assert exc.value.code == PATH_POLICY_DENIED


def test_secret_file_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", ".env")
    assert exc.value.code == SECRET_FILE_DENIED


def test_directory_read_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "sub")
    assert exc.value.code == FILE_TYPE_DENIED


def test_non_utf8_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "broken.bin")
    assert exc.value.code == FILE_TYPE_DENIED


def test_oversize_denied(guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        guard.read_text("ws1", "big.bin")
    assert exc.value.code == FILE_SIZE_DENIED


def test_list_files_exposes_kinds(guard: WorkspaceGuard) -> None:
    listing = guard.list_files("ws1")
    kinds = {item["name"]: item["kind"] for item in listing}
    assert kinds["notes.txt"] == "file"
    assert kinds["sub"] == "dir"
    assert kinds[".env"] == "secret"


def test_search_files_finds_match(guard: WorkspaceGuard) -> None:
    results = guard.search_files("ws1", "nested content")
    assert any(r["relativePath"] == "sub/deep.txt" for r in results)


def test_unregistered_workspace_denied(tmp_path: Path) -> None:
    g = _make_registry(tmp_path / "proj")
    with pytest.raises(Phase1Error) as exc:
        g.read_text("nope", "notes.txt")
    assert exc.value.code == WORKSPACE_NOT_REGISTERED


def test_disabled_workspace_denied(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    g = _make_registry(root, enabled=False)
    with pytest.raises(Phase1Error) as exc:
        g.read_text("ws1", "notes.txt")
    assert exc.value.code == WORKSPACE_DISABLED


def test_symlink_target_denied(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "real.txt").write_text("data", encoding="utf-8")
    link = root / "evil.txt"
    try:
        os.symlink(root / "real.txt", link)
    except OSError:
        pytest.skip("symlink creation not permitted in this environment")
    g = _make_registry(root)
    with pytest.raises(Phase1Error) as exc:
        g.read_text("ws1", "evil.txt")
    assert exc.value.code == SYMLINK_DENIED
