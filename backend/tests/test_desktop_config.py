"""Phase 3 desktop sidecar configuration tests.

Covers the desktop data-root contract: desktop mode is enabled only by an
explicit absolute data dir; all mutable locations resolve under that root; a
relative data dir, a missing token or a bad port fail closed; and error
messages never leak the data root or any derived absolute path.
"""

import pytest

from app.config.desktop import DesktopConfigError, load_desktop_config


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "LIGHTCODE_DESKTOP_DATA_DIR": "",
        "LIGHTCODE_SIDECAR_TOKEN": "",
        "LIGHTCODE_SIDECAR_PORT": "",
    }
    env.update(overrides)
    return env


def test_desktop_config_disabled_without_data_dir() -> None:
    cfg = load_desktop_config(_env())
    assert cfg.enabled is False


def test_desktop_config_resolves_paths_under_absolute_root() -> None:
    cfg = load_desktop_config(
        _env(
            LIGHTCODE_DESKTOP_DATA_DIR="C:\\LightCodeData",
            LIGHTCODE_SIDECAR_TOKEN="tok-abc",
            LIGHTCODE_SIDECAR_PORT="8123",
        )
    )
    from pathlib import Path

    assert cfg.enabled is True
    assert cfg.data_dir == Path("C:\\LightCodeData")
    assert cfg.database_path == Path("C:\\LightCodeData\\lightcode.db")
    assert cfg.skills_dir == Path("C:\\LightCodeData\\skills")
    assert cfg.workspaces_dir == Path("C:\\LightCodeData\\workspaces")
    assert cfg.sidecar_token == "tok-abc"
    assert cfg.sidecar_port == 8123
    assert cfg.bind_host == "127.0.0.1"


def test_desktop_config_rejects_relative_data_dir() -> None:
    with pytest.raises(DesktopConfigError):
        load_desktop_config(
            _env(
                LIGHTCODE_DESKTOP_DATA_DIR="relative/path",
                LIGHTCODE_SIDECAR_TOKEN="t",
                LIGHTCODE_SIDECAR_PORT="1",
            )
        )


def test_desktop_config_error_does_not_leak_path() -> None:
    with pytest.raises(DesktopConfigError) as exc:
        load_desktop_config(
            _env(
                LIGHTCODE_DESKTOP_DATA_DIR="Users\\Secret\\relative-confusion",
                LIGHTCODE_SIDECAR_TOKEN="t",
                LIGHTCODE_SIDECAR_PORT="1",
            )
        )
    assert "Secret" not in str(exc.value)
    assert "Users" not in str(exc.value)


def test_desktop_config_requires_token() -> None:
    with pytest.raises(DesktopConfigError):
        load_desktop_config(
            _env(LIGHTCODE_DESKTOP_DATA_DIR="C:\\Data", LIGHTCODE_SIDECAR_PORT="1")
        )


def test_desktop_config_rejects_bad_port() -> None:
    with pytest.raises(DesktopConfigError):
        load_desktop_config(
            _env(
                LIGHTCODE_DESKTOP_DATA_DIR="C:\\Data",
                LIGHTCODE_SIDECAR_TOKEN="t",
                LIGHTCODE_SIDECAR_PORT="not-a-port",
            )
        )
    with pytest.raises(DesktopConfigError):
        load_desktop_config(
            _env(
                LIGHTCODE_DESKTOP_DATA_DIR="C:\\Data",
                LIGHTCODE_SIDECAR_TOKEN="t",
                LIGHTCODE_SIDECAR_PORT="70000",
            )
        )