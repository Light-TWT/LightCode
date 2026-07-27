from __future__ import annotations

import fnmatch
import os
from pathlib import Path

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
from app.security.fs import canonical_resolve, is_link_or_reparse, validate_relative_input
from app.workspaces.registry import RegistryWorkspace, WorkspaceRegistry

MAX_FILE_BYTES = 1_000_000
SECRET_GLOB = ("*.pem", "*.key", "id_rsa*", "credentials*", "secrets*")


def _is_secret(name: str) -> bool:
    base = os.path.basename(name)
    if base in (".env", ".git"):
        return True
    return any(fnmatch.fnmatch(base, pat) for pat in SECRET_GLOB)


def _resolve_under(root: Path, relative: str) -> Path:
    validate_relative_input(relative)
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise Phase1Error(PATH_POLICY_DENIED, "path escapes workspace root")
    if is_link_or_reparse(target):
        raise Phase1Error(SYMLINK_DENIED, "symlink/junction/reparse points are not allowed")
    return target


class WorkspaceGuard:
    def __init__(self, registry: WorkspaceRegistry) -> None:
        self._registry = registry

    def workspace(self, workspace_id: str) -> RegistryWorkspace:
        ws = self._registry.get(workspace_id)
        if ws is None:
            raise Phase1Error(WORKSPACE_NOT_REGISTERED, f"workspace not registered: {workspace_id}")
        if not ws.enabled:
            raise Phase1Error(WORKSPACE_DISABLED, f"workspace disabled: {workspace_id}")
        return ws

    def resolve(self, workspace_id: str, relative: str) -> Path:
        ws = self.workspace(workspace_id)
        return _resolve_under(ws.canonical_root, relative)

    def _require_readable_file(self, path: Path) -> None:
        if not path.exists():
            raise Phase1Error(FILE_TYPE_DENIED, "file does not exist")
        if path.is_dir():
            raise Phase1Error(FILE_TYPE_DENIED, "path is a directory")
        if is_link_or_reparse(path):
            raise Phase1Error(SYMLINK_DENIED, "symlink/junction/reparse points are not allowed")
        if _is_secret(path.name):
            raise Phase1Error(SECRET_FILE_DENIED, "secret file access is denied")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise Phase1Error(FILE_SIZE_DENIED, "file exceeds size limit")

    def read_text(self, workspace_id: str, relative: str) -> str:
        path = self.resolve(workspace_id, relative)
        self._require_readable_file(path)
        try:
            # newline="" 关闭通用换行转换，保留文件原始换行符。这样 sha256(文本)
            # 与磁盘原始字节的哈希一致，避免对 CRLF 文件误判 STALE_BASE，也避免
            # 写入时静默改写行尾。
            return path.read_text(encoding="utf-8", newline="")
        except UnicodeDecodeError:
            raise Phase1Error(FILE_TYPE_DENIED, "file is not valid UTF-8 text")

    def list_files(self, workspace_id: str, relative: str = "") -> list[dict]:
        if relative:
            base = self.resolve(workspace_id, relative)
        else:
            base = self.workspace(workspace_id).canonical_root
        if not base.exists() or not base.is_dir():
            raise Phase1Error(FILE_TYPE_DENIED, "directory does not exist")
        results = []
        for entry in sorted(base.iterdir()):
            if entry.is_dir():
                kind = "dir"
            elif is_link_or_reparse(entry):
                kind = "link"
            elif _is_secret(entry.name):
                kind = "secret"
            else:
                kind = "file"
            results.append({"name": entry.name, "kind": kind, "relativePath": str(entry.relative_to(base)).replace("\\", "/")})
        return results

    def search_files(self, workspace_id: str, query: str) -> list[dict]:
        root = self.workspace(workspace_id).canonical_root
        if not query:
            return []
        results = []
        for path in root.rglob("*"):
            if not path.is_file() or is_link_or_reparse(path) or _is_secret(path.name):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if query in text:
                results.append(
                    {"name": path.name, "relativePath": str(path.relative_to(root)).replace("\\", "/")}
                )
        return results
