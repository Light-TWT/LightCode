"""Phase 3 desktop sidecar configuration.

Desktop mode is enabled only by ``LIGHTCODE_DESKTOP_DATA_DIR``. In desktop mode
the sidecar derives all mutable locations (SQLite, skills, desktop workspace
registration) under a single absolute data root supplied by Electron, and is
bound to a loopback interface chosen by Electron.

Security contract:

* The data root must be an absolute path; a relative path is rejected.
* A per-launch ``LIGHTCODE_SIDECAR_TOKEN`` is required; without it the sidecar
  must not accept desktop registration requests.
* ``LIGHTCODE_SIDECAR_PORT`` must be a valid loopback port.
* No public DTO, log, event or error may contain the data root or any derived
  absolute path, so every error raised here uses a fixed, path-free message.

This module performs no I/O and imports nothing from the service layer, so it
can be unit-tested with a plain dict instead of the real process environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

LOOPBACK_HOST = "127.0.0.1"


class DesktopConfigError(Exception):
    """Desktop sidecar configuration is invalid (message is path-free)."""


@dataclass(frozen=True)
class DesktopConfig:
    """Immutable desktop sidecar configuration snapshot.

    When ``enabled`` is False every Path is empty and no desktop behaviour is
    active. ``sidecar_token`` is the per-launch registration token; it moves
    only from Electron main to the sidecar and never into public state.
    """

    enabled: bool
    data_dir: Path
    database_path: Path
    skills_dir: Path
    workspaces_dir: Path
    sidecar_token: str
    sidecar_port: int
    host: str

    @property
    def bind_host(self) -> str:
        return self.host

    @property
    def bind_port(self) -> int:
        return self.sidecar_port


def load_desktop_config(
    environ: Mapping[str, str] | None = None,
) -> DesktopConfig:
    """Build the desktop config from a mapping (defaults to ``os.environ``)."""
    env = os.environ if environ is None else environ

    raw_dir = env.get("LIGHTCODE_DESKTOP_DATA_DIR", "").strip()
    token = env.get("LIGHTCODE_SIDECAR_TOKEN", "").strip()
    port_raw = env.get("LIGHTCODE_SIDECAR_PORT", "").strip()

    if not raw_dir:
        # Not desktop mode: disabled config, no path resolution.
        return _disabled(sidecar_token=token)

    data_dir = Path(raw_dir)
    if not data_dir.is_absolute():
        raise DesktopConfigError("desktop data dir must be an absolute path")

    if not token:
        raise DesktopConfigError("desktop sidecar token is required")

    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise DesktopConfigError("desktop sidecar port must be an integer") from None
    if not (0 < port < 65536):
        raise DesktopConfigError("desktop sidecar port is out of range")

    return DesktopConfig(
        enabled=True,
        data_dir=data_dir,
        database_path=data_dir / "lightcode.db",
        skills_dir=data_dir / "skills",
        workspaces_dir=data_dir / "workspaces",
        sidecar_token=token,
        sidecar_port=port,
        host=LOOPBACK_HOST,
    )


def _disabled(sidecar_token: str) -> DesktopConfig:
    return DesktopConfig(
        enabled=False,
        data_dir=Path(""),
        database_path=Path(""),
        skills_dir=Path(""),
        workspaces_dir=Path(""),
        sidecar_token=sidecar_token,
        sidecar_port=0,
        host=LOOPBACK_HOST,
    )


__all__ = [
    "DesktopConfig",
    "DesktopConfigError",
    "LOOPBACK_HOST",
    "load_desktop_config",
]