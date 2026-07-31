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
from app.security.fs import is_link_or_reparse
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
    # The sandbox may create a non-functional link (no reparse point and not
    # detected by os.path.islink). In that case the guard cannot distinguish it
    # from a real file, so skip rather than report a false failure.
    if not is_link_or_reparse(link):
        pytest.skip("symlinks are not detectable in this environment")
    g = _make_registry(root)
    with pytest.raises(Phase1Error) as exc:
        g.read_text("ws1", "evil.txt")
    assert exc.value.code == SYMLINK_DENIED


def test_symlink_segment_detected_before_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deterministic logic test: a reparse point at the final segment must be
    # caught BEFORE resolve() follows it. Does not depend on FS symlink support.
    root = tmp_path / "proj"
    root.mkdir()
    (root / "real.txt").write_text("data", encoding="utf-8")
    g = _make_registry(root)
    monkeypatch.setattr(
        "app.security.guard.is_link_or_reparse",
        lambda p: p.name == "evil.txt",
    )
    with pytest.raises(Phase1Error) as exc:
        g.read_text("ws1", "evil.txt")
    assert exc.value.code == SYMLINK_DENIED


def test_symlink_in_parent_segment_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "sub").mkdir()
    (root / "sub" / "real.txt").write_text("data", encoding="utf-8")
    g = _make_registry(root)
    monkeypatch.setattr(
        "app.security.guard.is_link_or_reparse",
        lambda p: p.name == "sub",
    )
    with pytest.raises(Phase1Error) as exc:
        g.read_text("ws1", "sub/real.txt")
    assert exc.value.code == SYMLINK_DENIED


def test_root_symlink_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "real.txt").write_text("data", encoding="utf-8")
    g = _make_registry(root)
    monkeypatch.setattr("app.security.guard.is_link_or_reparse", lambda p: True)
    with pytest.raises(Phase1Error) as exc:
        g.read_text("ws1", "real.txt")
    assert exc.value.code == SYMLINK_DENIED


# ---------------------------------------------------------------------------
# P0-1 (WP0): sensitive-path policy must reject the .git/** subtree by *every*
# access path (read / list / search), including case-variant spellings.
# Currently `_is_secret` only inspects the basename, so `.git/config` reads as
# `config` and slips through. These tests encode the post-fix invariant and are
# expected to FAIL (red) until WP1 introduces per-segment canonical checks.
# ---------------------------------------------------------------------------


@pytest.fixture
def secret_guard(tmp_path: Path) -> WorkspaceGuard:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "notes.txt").write_text("hello\n", encoding="utf-8")
    git_dir = root / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    # Case-variant subtree, best-effort: on case-insensitive filesystems (.GIT
    # == .git) this collides and is skipped, but the path `.GIT/CONFIG` still
    # resolves to `.git/CONFIG` so the casefold bypass test remains valid.
    upper_git = root / ".GIT"
    try:
        upper_git.mkdir()
        (upper_git / "CONFIG").write_text("[core]\n", encoding="utf-8")
    except FileExistsError:
        pass
    (root / "credentials.json").write_text("{}", encoding="utf-8")
    (root / "id_rsa").write_text("PRIVATE", encoding="utf-8")
    (root / "secret.key").write_text("KEY", encoding="utf-8")
    return _make_registry(root)


def test_read_git_config_denied(secret_guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        secret_guard.read_text("ws1", ".git/config")
    assert exc.value.code == SECRET_FILE_DENIED


def test_read_git_config_casefold_denied(secret_guard: WorkspaceGuard) -> None:
    with pytest.raises(Phase1Error) as exc:
        secret_guard.read_text("ws1", ".GIT/CONFIG")
    assert exc.value.code == SECRET_FILE_DENIED


def test_list_git_dir_denied(secret_guard: WorkspaceGuard) -> None:
    # Listing the .git subtree must be rejected, not enumerate its contents.
    with pytest.raises(Phase1Error) as exc:
        secret_guard.list_files("ws1", ".git")
    assert exc.value.code in (SECRET_FILE_DENIED, PATH_POLICY_DENIED)


def test_search_excludes_git_subtree(secret_guard: WorkspaceGuard) -> None:
    results = secret_guard.search_files("ws1", "core")
    assert not any(".git" in r["relativePath"].lower() for r in results)


# --- Nested browse navigation (WP3 token correctness) ---------------------
# `list_files` powers the browse-token flow in routes.py: each entry's
# `relativePath` is signed into a token that is later resolved from the
# WORKSPACE ROOT. Entries must therefore be root-relative, not base-relative,
# or navigation beyond the first directory level resolves the wrong path.


def test_nested_listing_returns_root_relative_paths(guard: WorkspaceGuard) -> None:
    entries = guard.list_files("ws1", "sub")
    by_name = {e["name"]: e for e in entries}
    assert by_name["deep.txt"]["relativePath"] == "sub/deep.txt"


def test_nested_listing_paths_are_resolvable_from_root(guard: WorkspaceGuard) -> None:
    # A path handed back by a nested listing must be usable as-is for a read,
    # which is exactly what the browse token round-trip does.
    entries = guard.list_files("ws1", "sub")
    relative = next(e["relativePath"] for e in entries if e["name"] == "deep.txt")
    assert guard.read_text("ws1", relative) == "nested content"
