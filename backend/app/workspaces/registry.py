from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from app.security.fs import canonical_resolve, is_link_or_reparse, validate_relative_input

DEFAULT_CONFIG_FILENAME = "workspaces.json"
CONFIG_ENV_VAR = "LIGHTCODE_WORKSPACES_CONFIG"
PHASE1_POLICY = "phase1-single-text-file"
POLICY_CAPABILITIES = {
    PHASE1_POLICY: ["list_files", "read_file", "search_files"],
}


@dataclass(frozen=True)
class RegistryWorkspace:
    """Server-private view of a registered workspace.

    `canonical_root` is never exposed in public DTOs, SSE, logs or errors.
    `target_file` is the logical relative path the Phase 1 template mutates;
    it is server-determined and never accepted from the browser.
    """

    id: str
    display_name: str
    canonical_root: Path
    enabled: bool
    policy: str
    policy_version: str
    target_file: str

    @property
    def capabilities(self) -> list[str]:
        return list(POLICY_CAPABILITIES.get(self.policy, []))


class WorkspaceRegistryError(Exception):
    """Raised when the static workspace configuration is malformed."""


class WorkspaceRegistry:
    def __init__(self, workspaces: list[RegistryWorkspace]) -> None:
        self._by_id = {w.id: w for w in workspaces}

    @classmethod
    def load(cls, config_path: Path | None = None) -> "WorkspaceRegistry":
        if config_path is None:
            env = os.environ.get(CONFIG_ENV_VAR)
            config_path = Path(env) if env else Path(DEFAULT_CONFIG_FILENAME)
        if not config_path.exists():
            # No config is allowed: the server runs with zero real workspaces.
            return cls([])
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise WorkspaceRegistryError(f"cannot read workspace config {config_path}: {exc}") from exc
        workspaces_raw = raw.get("workspaces", [])
        if not isinstance(workspaces_raw, list):
            raise WorkspaceRegistryError("workspace config 'workspaces' must be a list")
        seen: dict[str, RegistryWorkspace] = {}
        for entry in workspaces_raw:
            ws = cls._validate_entry(entry)
            if ws.id in seen:
                raise WorkspaceRegistryError(f"duplicate workspace id: {ws.id}")
            seen[ws.id] = ws
        return cls(list(seen.values()))

    @staticmethod
    def _validate_entry(entry: dict) -> RegistryWorkspace:
        if not isinstance(entry, dict):
            raise WorkspaceRegistryError("workspace entry must be an object")
        ws_id = entry.get("id")
        if not ws_id or not isinstance(ws_id, str):
            raise WorkspaceRegistryError("workspace id must be a non-empty string")
        display_name = entry.get("displayName") or ws_id
        root_raw = entry.get("rootPath")
        if not root_raw or not isinstance(root_raw, str):
            raise WorkspaceRegistryError(f"workspace {ws_id} missing string rootPath")
        root = Path(root_raw)
        if is_link_or_reparse(root):
            raise WorkspaceRegistryError(
                f"workspace {ws_id} root must not be a symlink/junction/reparse point"
            )
        canonical = canonical_resolve(root)
        if not canonical.exists():
            raise WorkspaceRegistryError(f"workspace {ws_id} root does not exist: {canonical}")
        if not canonical.is_dir():
            raise WorkspaceRegistryError(f"workspace {ws_id} root is not a directory: {canonical}")
        policy = entry.get("policy", PHASE1_POLICY)
        # Fail-closed: only allow-listed policies are accepted. A non-string
        # (bool/number), a stringified boolean ("true"), or any unknown policy
        # name is rejected rather than silently defaulted to a permitted policy.
        if not isinstance(policy, str) or policy not in POLICY_CAPABILITIES:
            raise WorkspaceRegistryError(
                f"workspace {ws_id} policy must be one of {sorted(POLICY_CAPABILITIES)}"
            )
        target_file = entry.get("targetFile")
        if not target_file or not isinstance(target_file, str):
            raise WorkspaceRegistryError(f"workspace {ws_id} missing string targetFile")
        # Reject dangerous target paths at registration time.
        try:
            validate_relative_input(target_file)
        except Exception as exc:  # noqa: BLE001 - surface as registry error
            raise WorkspaceRegistryError(
                f"workspace {ws_id} targetFile is invalid: {exc}"
            ) from exc
        enabled = bool(entry.get("enabled", True))
        return RegistryWorkspace(
            id=ws_id,
            display_name=display_name,
            canonical_root=canonical,
            enabled=enabled,
            policy=policy,
            policy_version=policy,
            target_file=target_file,
        )

    def get(self, workspace_id: str) -> RegistryWorkspace | None:
        return self._by_id.get(workspace_id)

    def list_workspaces(self) -> list[RegistryWorkspace]:
        return list(self._by_id.values())
