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

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional, Protocol


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


__all__ = [
    "InMemoryProviderCredentialStore",
    "ProviderCredentialStore",
    "ProviderRuntimeCredential",
]
