"""PyInstaller entry point for the LightCode desktop sidecar.

Electron spawns the bundled executable produced from this module. It reads the
loopback port from the desktop config and starts Uvicorn inside the same
process. All application behaviour (data root, token enforcement, registry,
credentials, logging) lives in :mod:`app.main`; this module only decides the
bind address and runs the server.

The token is read from the environment here only to decide whether the process
is in desktop mode; the actual token check happens in the registration route.
"""

from __future__ import annotations

import os

import uvicorn

from app.config.desktop import LOOPBACK_HOST, load_desktop_config
from app.main import app


def main() -> None:
    desktop = load_desktop_config()
    if desktop.enabled:
        host: str = desktop.bind_host
        port: int = desktop.bind_port
    else:
        # Non-desktop fallback is only for local development smoke runs; the
        # packaged sidecar is always launched with desktop env vars set.
        host = LOOPBACK_HOST
        try:
            port = int(os.environ.get("LIGHTCODE_SIDECAR_PORT", "8000"))
        except ValueError:
            port = 8000
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()