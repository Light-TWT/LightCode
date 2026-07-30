"""Phase 1 file-access and ChangeSet policy constants.

These constants are the single source of truth for the "策略禁止的文件" and
"有效期" rules referenced in `docs/phase1-safety-contract.md` (§路径拒绝 / 文件拒绝
and §审批与写入协议 step 1 "校验...有效期"). Keeping them here makes the policy
explicit and unit-testable instead of buried in guard/phase1 logic.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

# Maximum size of a file that may be read or searched (bytes).
MAX_FILE_BYTES = 1_000_000

# Maximum total changed lines (additions + deletions) a single ChangeSet may
# contain. Larger diffs are rejected with FILE_TYPE_DENIED before any write.
MAX_DIFF_LINES = 1000

# ChangeSet validity window in seconds. An approval submitted after expiry is
# rejected with CHANGESET_EXPIRED. Set to 0 to disable expiry at the policy level.
CHANGESET_TTL_SECONDS = 3600

# Allowed source/text file extensions for Phase 1 read/search. Files without an
# extension are permitted (treated as plain text). Binary/non-source extensions
# are rejected with FILE_TYPE_DENIED. Secrets (.env, *.pem, ...) are denied
# earlier by the secret-glob check and never reach this stage.
ALLOWED_EXTENSIONS = {
    ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue",
    ".json", ".json5", ".md", ".markdown", ".txt", ".rst", ".html", ".htm",
    ".css", ".scss", ".sass", ".less", ".yml", ".yaml", ".toml", ".ini",
    ".cfg", ".conf", ".sh", ".bash", ".zsh", ".bat", ".ps1", ".go", ".rs",
    ".java", ".kt", ".kts", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php",
    ".rb", ".pl", ".lua", ".sql", ".graphql", ".xml", ".xsl", ".svg", ".lock",
    ".gitignore", ".dockerignore", ".editorconfig", ".properties", ".gradle",
    ".mod", ".sum", ".tf", ".tfvars", ".gitattributes",
}

# Secret file globs rejected before any content read (see §默认敏感文件拒绝).
SECRET_GLOB = ("*.pem", "*.key", "id_rsa*", "credentials*", "secrets*")

# Logical path segments that are always sensitive, regardless of their position
# in the path. `.git` is rejected everywhere (not just as a bare basename) so
# `.git/config` cannot be read; `.env` is included because it is a secret store
# even when nested (e.g. `config/.env`). The check is case-insensitive because
# Windows filesystems fold `.GIT` onto `.git`.
SENSITIVE_SEGMENTS = {".env", ".git"}


def is_sensitive_relative_path(relative: str) -> bool:
    """Reject sensitive logical paths by a canonical per-segment check.

    Unlike a basename-only test, this denies every segment of the logical path,
    so `.git/config`, `.GIT/CONFIG`, `a/b/.env` and `secrets/prod.key` are all
    caught. Used by the guard on read, list and search entry points.

    Args:
        relative: A workspace-relative logical path (forward or back slashes).
    """
    segments = [s for s in relative.replace("\\", "/").split("/") if s]
    if not segments:
        return False
    lowered = [s.casefold() for s in segments]
    if any(seg in SENSITIVE_SEGMENTS for seg in lowered):
        return True
    for seg in lowered:
        if any(fnmatch.fnmatch(seg, pat.casefold()) for pat in SECRET_GLOB):
            return True
    return False


def is_allowed_extension(path: Path) -> bool:
    """True when the path's extension is permitted by the Phase 1 policy."""
    suffix = path.suffix.lower()
    return not suffix or suffix in ALLOWED_EXTENSIONS
