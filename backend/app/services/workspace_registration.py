"""Phase 3 desktop workspace registration service.

The desktop folder picker runs in Electron main; the selected absolute path is
sent to the sidecar over a trusted channel and this service validates and
persists it as a server-controlled workspace. The browser never submits a path.

Security contract:

* This endpoint is active only in desktop mode (``app.state.desktop.enabled``).
* Every request must present the per-launch ``X-LightCode-Sidecar-Token``
  header; a missing or wrong token is rejected fail-closed.
* The root must be an absolute, existing directory that is not a
  symlink/junction/reparse point.
* ``display_name`` is derived from the folder name only; the canonical root is
  server-private and never returned in a public DTO, SSE frame, log or error.
* A given canonical root can be registered at most once.
"""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Request

from app.schemas.contracts import RegisteredWorkspaceResponse
from app.schemas.errors import (
    DESKTOP_MODE_DISABLED,
    DESKTOP_SIDECAR_TOKEN_INVALID,
    DESKTOP_WORKSPACE_INVALID,
    Phase1Error,
)
from app.security.fs import canonical_resolve, is_link_or_reparse
from app.workspaces.registry import PHASE1_POLICY, RegistryWorkspace

TOKEN_HEADER = "x-lightcode-sidecar-token"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_desktop_workspaces(db) -> list[RegistryWorkspace]:
    """Rehydrate persisted desktop workspaces into ``RegistryWorkspace`` values.

    ``canonical_root`` is read from the server-private column and never
    serialised to a public DTO. Desktop workspaces have no static ``target_file``
    (the model later selects a file via ``read_file``/``search_files``).
    """
    rows = db.execute(
        "SELECT * FROM desktop_workspaces ORDER BY created_at ASC"
    ).fetchall()
    return [
        RegistryWorkspace(
            id=row["id"],
            display_name=row["display_name"],
            canonical_root=Path(row["canonical_root"]),
            enabled=bool(row["enabled"]),
            policy=row["policy"],
            policy_version=row["policy_version"],
            target_file="",
        )
        for row in rows
    ]


class DesktopWorkspaceService:
    def __init__(self, request: Request) -> None:
        state = request.app.state
        self._db = state.db
        self._desktop = state.desktop
        self._registry = state.registry

    @classmethod
    def from_request(cls, request: Request) -> "DesktopWorkspaceService":
        return cls(request)

    def register(self, root_path: str, token: Optional[str]) -> RegisteredWorkspaceResponse:
        if not self._desktop.enabled:
            raise Phase1Error(DESKTOP_MODE_DISABLED, "desktop mode is not active")
        if not token or not hmac.compare_digest(token, self._desktop.sidecar_token):
            raise Phase1Error(
                DESKTOP_SIDECAR_TOKEN_INVALID,
                "desktop sidecar token is invalid",
                http_status=401,
            )

        canonical = self._validate_root(root_path)
        workspace = self._persist(canonical)
        # Idempotent registration: a canonical root already persisted is returned
        # as-is (registry already holds it at startup or from an earlier call),
        # so re-selecting the same folder re-opens it instead of erroring.
        if self._registry.get(workspace.id) is None:
            self._registry.add(workspace)
        return RegisteredWorkspaceResponse(
            id=workspace.id,
            displayName=workspace.display_name,
            enabled=workspace.enabled,
            capabilities=workspace.capabilities,
            policyVersion=workspace.policy_version,
        )

    def _validate_root(self, root_path: str) -> Path:
        if not root_path or not root_path.strip():
            raise Phase1Error(DESKTOP_WORKSPACE_INVALID, "workspace root is required")
        root = Path(root_path.strip())
        if not root.is_absolute():
            raise Phase1Error(DESKTOP_WORKSPACE_INVALID, "workspace root must be absolute")
        if is_link_or_reparse(root):
            raise Phase1Error(
                DESKTOP_WORKSPACE_INVALID,
                "workspace root must not be a reparse point",
            )
        canonical = canonical_resolve(root)
        if not canonical.is_dir():
            raise Phase1Error(DESKTOP_WORKSPACE_INVALID, "workspace root must be a directory")
        return canonical

    def _persist(self, canonical: Path) -> RegistryWorkspace:
        now = _now()
        existing = self._db.execute(
            "SELECT * FROM desktop_workspaces WHERE canonical_root = ?",
            (str(canonical),),
        ).fetchone()
        if existing:
            # Idempotent: the same canonical root maps to the same workspace.
            return RegistryWorkspace(
                id=existing["id"],
                display_name=existing["display_name"],
                canonical_root=canonical,
                enabled=bool(existing["enabled"]),
                policy=existing["policy"],
                policy_version=existing["policy_version"],
                target_file="",
            )
        ws_id = f"desktop-{uuid.uuid4().hex[:12]}"
        display_name = canonical.name or "工作区"
        with self._db:
            self._db.execute(
                "INSERT INTO desktop_workspaces "
                "(id, display_name, canonical_root, enabled, policy, policy_version, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
                (
                    ws_id,
                    display_name,
                    str(canonical),
                    PHASE1_POLICY,
                    PHASE1_POLICY,
                    now,
                    now,
                ),
            )
        return RegistryWorkspace(
            id=ws_id,
            display_name=display_name,
            canonical_root=canonical,
            enabled=True,
            policy=PHASE1_POLICY,
            policy_version=PHASE1_POLICY,
            target_file="",
        )


__all__ = [
    "DesktopWorkspaceService",
    "TOKEN_HEADER",
    "load_desktop_workspaces",
]