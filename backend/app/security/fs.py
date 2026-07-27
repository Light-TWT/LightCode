from __future__ import annotations

import os
import sys
from pathlib import Path

from app.schemas.errors import PATH_POLICY_DENIED, Phase1Error


def is_reparse_point(path: Path) -> bool:
    """Best-effort detection of Windows reparse points (junctions / symlinks).

    On non-Windows platforms reparse points do not exist, so this always
    returns False. On Windows we query the file attributes directly without
    following the reparse point.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes  # type: ignore

        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[attr-defined]
        if attrs == -1:
            return False
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def is_link_or_reparse(path: Path) -> bool:
    """True when the path itself is a symlink or reparse point.

    Callers must check this BEFORE resolving, because resolving would follow
    the link and mask the escape attempt.
    """
    if os.path.islink(str(path)):
        return True
    return is_reparse_point(path)


def canonical_resolve(path: Path) -> Path:
    """Resolve to an absolute, canonical path.

    The caller is responsible for rejecting links/reparse points beforehand via
    `is_link_or_reparse`.
    """
    return path.resolve()


def validate_relative_input(relative: str) -> None:
    """Reject dangerous logical relative paths before any filesystem touch.

    Raises `Phase1Error` with `PATH_POLICY_DENIED` on traversal, absolute,
    drive/scheme or backslash inputs.
    """
    if relative is None:
        raise Phase1Error(PATH_POLICY_DENIED, "path is required")
    norm = relative.replace("\\", "/")
    first_segment = norm.split("/", 1)[0]
    if norm.startswith("/") or norm.startswith("//"):
        raise Phase1Error(PATH_POLICY_DENIED, "absolute paths are not allowed")
    if ":" in first_segment:
        # drive letter (C:) or scheme-like prefix
        raise Phase1Error(PATH_POLICY_DENIED, "drive or scheme paths are not allowed")
    if "\\" in relative:
        raise Phase1Error(PATH_POLICY_DENIED, "backslash paths are not allowed")
    parts = norm.split("/")
    if ".." in parts:
        raise Phase1Error(PATH_POLICY_DENIED, "path traversal is not allowed")
    if "" in parts:
        raise Phase1Error(PATH_POLICY_DENIED, "empty path segment is not allowed")
