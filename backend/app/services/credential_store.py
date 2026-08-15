"""核心 Agent 更新（阶段 A/B）：可替换的 Provider 凭据存储。

设计边界（docs/phase2-model-provider-design.md §1）：

* 浏览器只在设置页输入 Provider 参数，凭据经本机 FastAPI 设置端点接收后送入
  ``ProviderCredentialStore``；密钥绝不进入 SQLite、前端持久化、日志、SSE 或仓库。
* Web 开发期使用进程内存实现（``InMemoryProviderCredentialStore``）：后端重启后
  凭据丢失，回落为环境变量配置或 ``unconfigured``。
* Electron 阶段（阶段 C）以系统密钥库实现替换本模块的内存实现，Provider 设置
  API、聊天 UI 与编排接口保持稳定 —— 这是桌面交付的迁移边界。
* 任何实现都绝不提供"返回原始 API Key"的公开读取接口；只允许替换凭据、读取
  安全状态和清除凭据。

阶段 B 扩展为多配置：每个运行期配置拥有稳定 ``id``；``get()`` 保持返回
“当前激活”配置，使 ChatService / ModelOrchestrator 的既有调用路径无需改动。
"""

from __future__ import annotations

import ctypes
import json
import sys
import threading
import uuid
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.schemas.errors import PROVIDER_SETTINGS_INVALID, Phase1Error


@dataclass(frozen=True)
class ProviderRuntimeCredential:
    """运行期凭据快照。``api_key`` 标记 ``repr=False``，任何日志/traceback 渲染
    都不能泄露它。``base_url`` 也只用于后端构建客户端，绝不序列化到公共 DTO。"""

    provider: str
    base_url: str
    model_id: str
    name: str = ""
    enabled: bool = True
    api_key: str = field(default="", repr=False)


class ProviderCredentialStore(Protocol):
    """凭据存储协议 —— Electron 阶段由系统密钥库实现替换。

    阶段 B 起为多配置：``get()`` 返回当前激活配置（兼容 ChatService /
    ModelOrchestrator 的既有路径）；``get_all()`` 返回全部配置（按 id）。
    """

    def get(self) -> Optional[ProviderRuntimeCredential]:
        """读取当前激活的运行期凭据（若存在）。"""
        ...

    def get_all(self) -> dict[str, ProviderRuntimeCredential]:
        """读取全部运行期凭据，键为配置 id。"""
        ...

    def get_named(self, profile_id: str) -> Optional[ProviderRuntimeCredential]:
        """按配置 id 读取（不存在返回 None）。"""
        ...

    def set(self, credential: ProviderRuntimeCredential) -> str:
        """保存运行期凭据为当前激活配置，返回其 id。"""
        ...

    def remove(self, profile_id: str) -> bool:
        """删除指定配置；删除的是激活配置时自动回落。返回是否删除成功。"""
        ...

    def clear(self) -> None:
        """清除全部运行期凭据。"""
        ...


class InMemoryProviderCredentialStore:
    """进程内存实现：不落盘，后端重启后自动清空。

    线程安全（``threading.Lock``）。``get()``/``get_all()`` 返回的对象仅在后端
    进程内使用，绝不出现在 API/SSE/日志/SQLite 中。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: dict[str, ProviderRuntimeCredential] = {}
        self._active_id: Optional[str] = None

    def get(self) -> Optional[ProviderRuntimeCredential]:
        with self._lock:
            if self._active_id is None:
                return None
            return self._profiles.get(self._active_id)

    def get_all(self) -> dict[str, ProviderRuntimeCredential]:
        with self._lock:
            return dict(self._profiles)

    def get_named(self, profile_id: str) -> Optional[ProviderRuntimeCredential]:
        with self._lock:
            return self._profiles.get(profile_id)

    def set(self, credential: ProviderRuntimeCredential) -> str:
        with self._lock:
            profile_id = uuid.uuid4().hex[:8]
            self._profiles[profile_id] = credential
            self._active_id = profile_id
            return profile_id

    def remove(self, profile_id: str) -> bool:
        with self._lock:
            if profile_id not in self._profiles:
                return False
            del self._profiles[profile_id]
            if self._active_id == profile_id:
                self._active_id = next(iter(self._profiles), None)
            return True

    def clear(self) -> None:
        with self._lock:
            self._profiles.clear()
            self._active_id = None


_TARGET_PREFIX = "LightCode/Provider/"
_ACTIVE_TARGET = "LightCode/Provider/Active"


class _CREDENTIAL(ctypes.Structure):
    """Native ``CREDENTIAL`` (wincred.h) layout, shared by read/write paths.

    Field order and types must match the OS definition exactly; the blob
    pointer and its size live at fixed offsets, so reading them back through
    the struct (rather than hand-computed indices) keeps the offsets correct.
    """

    _fields_ = [
        ("Flags", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", ctypes.c_ulong),
        ("CredentialBlob", ctypes.c_void_p),
        ("Persist", ctypes.c_ulong),
        ("AttributeCount", ctypes.c_ulong),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


PCREDENTIAL = ctypes.POINTER(_CREDENTIAL)


class _CredentialBackend(Protocol):
    """Abstract OS secret-store access. The real implementation talks to the
    Windows Credential Manager via ctypes; tests inject a fake backend."""

    def read_targets(self, prefix: str) -> list[str]: ...
    def read_blob(self, target: str) -> Optional[str]: ...
    def write_blob(self, target: str, blob: str) -> None: ...
    def delete_target(self, target: str) -> bool: ...


class _WindowsCredentialApi:
    """ctypes wrapper around advapi32 CredReadW/CredWriteW/CredDeleteW.

    The blob is stored in the OS-encrypted Credential Manager, so the API key
    never reaches SQLite, the renderer, logs or application resources. On
    non-Windows platforms or when advapi32 is unavailable every operation
    raises so the store fails closed.
    """

    def __init__(self) -> None:
        self._cred_read = None
        self._cred_write = None
        self._cred_delete = None
        self._cred_enum = None
        if sys.platform == "win32":
            try:
                import ctypes  # type: ignore
                from ctypes import wintypes  # type: ignore

                advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
                self._cred_read = advapi32.CredReadW
                self._cred_write = advapi32.CredWriteW
                self._cred_delete = advapi32.CredDeleteW
                self._cred_enum = advapi32.CredEnumerateW
                self._wintypes = wintypes
            except Exception:  # pragma: no cover - platform dependent
                self._cred_read = None

    def _available(self) -> bool:
        return all(
            callable(x) for x in (self._cred_read, self._cred_write, self._cred_delete)
        )

    def read_targets(self, prefix: str) -> list[str]:
        if not self._available():
            raise OSError("Windows Credential Manager is unavailable")
        # CredEnumerateW returns an array of PCREDENTIAL (pointers). Its built-in
        # filter is unreliable here (returns ERROR_NOT_FOUND even when matching
        # credentials exist), so enumerate everything and filter by prefix here.
        count = ctypes.c_ulong(0)
        credentials = ctypes.POINTER(PCREDENTIAL)()
        if not self._cred_enum(None, 0, ctypes.byref(count), ctypes.byref(credentials)):
            return []
        targets: list[str] = []
        try:
            for i in range(count.value):
                entry = credentials[i]
                if not entry or not entry.contents:
                    continue
                target = entry.contents.TargetName
                if target and target.startswith(prefix):
                    targets.append(target)
        finally:
            if credentials:
                ctypes.windll.advapi32.CredFree(credentials)
        return targets

    def read_blob(self, target: str) -> Optional[str]:
        if not self._available():
            raise OSError("Windows Credential Manager is unavailable")
        credential = PCREDENTIAL()
        if not self._cred_read(target, 1, 0, ctypes.byref(credential)):
            return None
        try:
            if not credential or not credential.contents:
                return None
            contents = credential.contents
            if not contents.CredentialBlob or contents.CredentialBlobSize <= 0:
                return None
            raw = ctypes.string_at(contents.CredentialBlob, contents.CredentialBlobSize)
            return raw.decode("utf-8")
        finally:
            ctypes.windll.advapi32.CredFree(credential)

    def write_blob(self, target: str, blob: str) -> None:
        if not self._available():
            raise OSError("Windows Credential Manager is unavailable")
        data = blob.encode("utf-8")
        buf = ctypes.create_string_buffer(data)
        cred = _CREDENTIAL()
        cred.Type = 1  # CRED_TYPE_GENERIC
        cred.TargetName = target
        cred.CredentialBlobSize = len(data)
        cred.CredentialBlob = ctypes.cast(buf, ctypes.c_void_p)
        cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
        if not self._cred_write(ctypes.byref(cred), 0):
            raise OSError("failed to write to Windows Credential Manager")

    def delete_target(self, target: str) -> bool:
        if not self._available():
            raise OSError("Windows Credential Manager is unavailable")
        return bool(self._cred_delete(target, 1, 0))


class WindowsCredentialManagerProviderCredentialStore:
    """Electron 阶段（阶段 C）的 Provider 凭据存储：密钥经 Windows Credential
    Manager 保存，绝不进入 SQLite、日志、事件、前端或安装资源。

    实现 ``ProviderCredentialStore`` 协议，使 ChatService / ModelOrchestrator
    零改动。每个运行期配置的完整凭据编码为 JSON 存入一个加密的 OS 凭据条目
    （``LightCode/Provider/<id>``），``Active`` 条目记录当前激活配置 id。
    底层 ``_CredentialBackend`` 可注入以便测试；默认使用 ctypes 的
    Windows Credential Manager 实现。任何后端失败都 fail-closed 抛出
    ``Phase1Error``，绝不回落写盘。
    """

    def __init__(self, backend: Optional[_CredentialBackend] = None) -> None:
        self._backend = backend if backend is not None else _WindowsCredentialApi()
        # RLock: facade methods (get/remove/clear) hold the lock while calling
        # other locked methods (get_named/get_all), so the lock must be reentrant.
        self._lock = threading.RLock()

    def _target(self, profile_id: str) -> str:
        return f"{_TARGET_PREFIX}{profile_id}"

    def _read_credential(self, target: str) -> Optional[ProviderRuntimeCredential]:
        blob = self._backend.read_blob(target)
        if not blob:
            return None
        try:
            data = json.loads(blob)
        except (ValueError, TypeError):
            return None
        return ProviderRuntimeCredential(
            provider=data.get("provider", ""),
            base_url=data.get("base_url", ""),
            model_id=data.get("model_id", ""),
            name=data.get("name", ""),
            enabled=bool(data.get("enabled", True)),
            api_key=data.get("api_key", ""),
        )

    def _write_credential(self, target: str, credential: ProviderRuntimeCredential) -> None:
        data = {
            "provider": credential.provider,
            "base_url": credential.base_url,
            "model_id": credential.model_id,
            "name": credential.name,
            "enabled": credential.enabled,
            "api_key": credential.api_key,
        }
        self._backend.write_blob(target, json.dumps(data))

    def _active_id(self) -> Optional[str]:
        blob = self._backend.read_blob(_ACTIVE_TARGET)
        if not blob:
            return None
        try:
            return json.loads(blob).get("active_id") or None
        except (ValueError, TypeError):
            return None

    def _set_active(self, profile_id: Optional[str]) -> None:
        self._backend.write_blob(_ACTIVE_TARGET, json.dumps({"active_id": profile_id or ""}))

    def get(self) -> Optional[ProviderRuntimeCredential]:
        with self._lock:
            active = self._active_id()
            if not active:
                return None
            return self.get_named(active)

    def get_all(self) -> dict[str, ProviderRuntimeCredential]:
        with self._lock:
            result: dict[str, ProviderRuntimeCredential] = {}
            for target in self._backend.read_targets(_TARGET_PREFIX):
                if target == _ACTIVE_TARGET:
                    continue
                profile_id = target[len(_TARGET_PREFIX):]
                credential = self._read_credential(target)
                if credential is not None:
                    result[profile_id] = credential
            return result

    def get_named(self, profile_id: str) -> Optional[ProviderRuntimeCredential]:
        with self._lock:
            return self._read_credential(self._target(profile_id))

    def set(self, credential: ProviderRuntimeCredential) -> str:
        with self._lock:
            try:
                profile_id = uuid.uuid4().hex[:8]
                self._write_credential(self._target(profile_id), credential)
                self._set_active(profile_id)
                return profile_id
            except OSError as exc:
                raise Phase1Error(
                    PROVIDER_SETTINGS_INVALID,
                    "无法访问系统凭据存储，凭据未保存。",
                ) from exc

    def remove(self, profile_id: str) -> bool:
        with self._lock:
            removed = self._backend.delete_target(self._target(profile_id))
            if not removed:
                return False
            active = self._active_id()
            if active == profile_id:
                remaining = [p for p in self.get_all() if p != profile_id]
                self._set_active(remaining[0] if remaining else None)
            return True

    def clear(self) -> None:
        with self._lock:
            for target in self._backend.read_targets(_TARGET_PREFIX):
                self._backend.delete_target(target)
            self._backend.delete_target(_ACTIVE_TARGET)


__all__ = [
    "InMemoryProviderCredentialStore",
    "ProviderCredentialStore",
    "ProviderRuntimeCredential",
    "WindowsCredentialManagerProviderCredentialStore",
]
