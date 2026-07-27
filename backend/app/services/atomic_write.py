"""Atomic single-file replacement and built-in verification for Phase 1.

The write path never launches an external process. It writes a sibling temp
file, fsyncs it, then uses `os.replace` for an atomic same-directory rename.
Built-in verification re-reads the target and checks UTF-8 validity plus the
expected content hash, matching the "内建完整性验证" requirement of the safety
contract.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from pathlib import Path

# Per-absolute-path locks so two tasks racing on the same file cannot both write.
_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: dict[str, threading.Lock] = {}


def file_lock(path: Path) -> threading.Lock:
    key = str(path)
    with _LOCKS_GUARD:
        lock = _FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _FILE_LOCKS[key] = lock
        return lock


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def current_hash(path: Path) -> str:
    """Hash the file's current on-disk bytes (newline-preserving)."""
    return sha256_bytes(path.read_bytes())


def atomic_replace(target: Path, new_text: str) -> None:
    """Atomically replace `target` contents with `new_text`.

    newline="" disables translation so the exact bytes we intend are what land
    on disk. On any failure before the rename, the original file is untouched.
    """
    parent = target.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(parent), prefix=".lightcode-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(new_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(target))
    except BaseException:
        # os.replace consumes the temp file on success; only clean up on failure.
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass
        raise


def verify_written(target: Path, expected_sha256: str) -> tuple[bool, str]:
    """Re-read the target and confirm UTF-8 validity and expected content hash."""
    raw = target.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, "written content is not valid UTF-8"
    actual = sha256_bytes(raw)
    if actual != expected_sha256:
        return False, "written content hash does not match proposed hash"
    return True, "ok"
