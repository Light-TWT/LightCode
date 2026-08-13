"""Phase 3 Windows Credential Manager credential store tests.

Uses an injectable credential backend so the store's protocol logic (set/get/
get-all/remove/clear), secret-safe repr and fail-closed behaviour are verified
without touching the real OS secret store.
"""

import pytest

from app.schemas.errors import Phase1Error
from app.services.credential_store import (
    ProviderRuntimeCredential,
    WindowsCredentialManagerProviderCredentialStore,
)


class FakeCredentialBackend:
    def __init__(self, fail_writes: bool = False) -> None:
        self._store: dict[str, str] = {}
        self.fail_writes = fail_writes

    def read_targets(self, prefix: str) -> list[str]:
        return [t for t in self._store if t.startswith(prefix)]

    def read_blob(self, target: str) -> str | None:
        return self._store.get(target)

    def write_blob(self, target: str, blob: str) -> None:
        if self.fail_writes:
            raise OSError("credential manager unavailable")
        self._store[target] = blob

    def delete_target(self, target: str) -> bool:
        return self._store.pop(target, None) is not None


def _cred(**overrides: str) -> ProviderRuntimeCredential:
    values = {
        "provider": "openai-compatible",
        "base_url": "https://api.example.test",
        "model_id": "gpt-x",
        "name": "test-profile",
        "enabled": True,
        "api_key": "sk-test-123",
    }
    values.update(overrides)
    return ProviderRuntimeCredential(**values)


@pytest.fixture
def store():
    return WindowsCredentialManagerProviderCredentialStore(
        backend=FakeCredentialBackend()
    )


def test_set_then_get_roundtrip(store) -> None:
    pid = store.set(_cred())
    got = store.get()
    assert got is not None
    assert got.api_key == "sk-test-123"
    assert got.provider == "openai-compatible"
    assert store.get_named(pid) is not None


def test_set_returns_active_profile(store) -> None:
    pid = store.set(_cred())
    assert store.get().model_id == "gpt-x"
    assert store.get_named(pid).model_id == "gpt-x"


def test_get_all_returns_all_profiles(store) -> None:
    store.set(_cred(name="a", api_key="key-a"))
    store.set(_cred(name="b", api_key="key-b"))
    all_profiles = store.get_all()
    assert len(all_profiles) == 2
    assert {c.name for c in all_profiles.values()} == {"a", "b"}


def test_remove_active_falls_back_to_next(store) -> None:
    first = store.set(_cred(name="a", api_key="key-a"))
    second = store.set(_cred(name="b", api_key="key-b"))
    assert store.remove(first) is True
    assert store.get().name == "b"
    assert store.get_named(first) is None


def test_remove_unknown_returns_false(store) -> None:
    assert store.remove("missing-id") is False


def test_clear_removes_all(store) -> None:
    store.set(_cred(name="a"))
    store.set(_cred(name="b"))
    store.clear()
    assert store.get() is None
    assert store.get_all() == {}


def test_set_fails_closed_when_backend_unavailable() -> None:
    store = WindowsCredentialManagerProviderCredentialStore(
        backend=FakeCredentialBackend(fail_writes=True)
    )
    with pytest.raises(Phase1Error):
        store.set(_cred())


def test_repr_excludes_api_key(store) -> None:
    store.set(_cred(api_key="sk-super-secret"))
    assert "sk-super-secret" not in repr(store)
    assert "sk-super-secret" not in repr(store.get())
    assert "sk-super-secret" not in repr(store.get_all())