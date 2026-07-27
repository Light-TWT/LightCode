from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.workspaces.registry import (
    PHASE1_POLICY,
    WorkspaceRegistry,
    WorkspaceRegistryError,
)


def _write_config(path: Path, workspaces: list[dict]) -> None:
    path.write_text(json.dumps({"workspaces": workspaces}), encoding="utf-8")


def _entry(**over) -> dict:
    base = {
        "id": "demo",
        "displayName": "Demo",
        "rootPath": str(over.pop("root", Path("__root__"))),
        "enabled": True,
        "policy": PHASE1_POLICY,
        "targetFile": "notes.txt",
    }
    base.update(over)
    return base


def test_missing_config_yields_empty_registry(tmp_path: Path) -> None:
    reg = WorkspaceRegistry.load(tmp_path / "does-not-exist.json")
    assert reg.list_workspaces() == []
    assert reg.get("anything") is None


def test_valid_workspace_loaded(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [_entry(root=root)])
    reg = WorkspaceRegistry.load(cfg)
    ws = reg.get("demo")
    assert ws is not None
    assert ws.display_name == "Demo"
    assert ws.enabled is True
    assert ws.policy_version == PHASE1_POLICY
    assert ws.target_file == "notes.txt"
    assert ws.capabilities == ["list_files", "read_file", "search_files"]
    assert ws.canonical_root.is_absolute()
    assert ws.canonical_root == root.resolve()


def test_disabled_workspace_flagged(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [_entry(root=root, enabled=False)])
    reg = WorkspaceRegistry.load(cfg)
    assert reg.get("demo").enabled is False


def test_missing_target_file_rejected(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [{"id": "demo", "rootPath": str(root), "enabled": True, "policy": PHASE1_POLICY}])
    with pytest.raises(WorkspaceRegistryError):
        WorkspaceRegistry.load(cfg)


def test_traversal_target_file_rejected(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [_entry(root=root, targetFile="../escape.txt")])
    with pytest.raises(WorkspaceRegistryError):
        WorkspaceRegistry.load(cfg)


def test_missing_rootpath_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [{"id": "demo", "rootPath": ""}])
    with pytest.raises(WorkspaceRegistryError):
        WorkspaceRegistry.load(cfg)


def test_nonexistent_root_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [_entry(root=tmp_path / "nope")])
    with pytest.raises(WorkspaceRegistryError):
        WorkspaceRegistry.load(cfg)


def test_duplicate_id_rejected(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [_entry(root=root), _entry(root=root)])
    with pytest.raises(WorkspaceRegistryError):
        WorkspaceRegistry.load(cfg)


def test_symlink_root_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted in this environment")
    cfg = tmp_path / "workspaces.json"
    _write_config(cfg, [_entry(root=link)])
    with pytest.raises(WorkspaceRegistryError):
        WorkspaceRegistry.load(cfg)
