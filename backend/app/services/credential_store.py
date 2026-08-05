"""核心 Agent 更新（阶段 A）：可替换的 Provider 凭据存储。

设计边界（docs/phase2-model-provider-design.md §1）：

* 浏览器只在设置页输入 Provider 参数，凭据经本机 FastAPI 设置端点接收后送入
  ``ProviderCredentialStore``；密钥绝不进入 SQLite、前端持久化、日志、SSE 或仓库。
* Web 开发期使用进程内存实现（``InMemoryProviderCredentialStore``）：后端重启后
  凭据丢失，回落为环境变量配置或 ``unconfigured``。
* Electron 阶段（阶段 C）以系统密钥库实现替换本模块的内存实现，Provider 设置
  API、聊天 UI 与编排接口保持稳定 —— 这是桌面交付的迁移边界。
* 任何实现都绝不提供"返回原始 API Key"的公开读取接口；只允许替换凭据、读取
  安全状态和清除凭据。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass(frozen=True)
class ProviderRuntimeCredential:
    """运行期凭据快照。``api_key`` 标记 ``repr=False``，任何日志/traceback 渲染
    都不能泄露它。``base_url`` 也只用于后端构建客户端，绝不序列化到公共 DTO。"""

    provider: str
    base_url: str
    model_id: str
    api_key: str = field(default="", repr=False)


class ProviderCredentialStore(Protocol):
    """凭据存储协议 —— Electron 阶段由系统密钥库实现替换。"""

    def get(self) -> Optional[ProviderRuntimeCredential]:
        """读取当前运行期凭据（若存在）。"""
        ...

    def set(self, credential: ProviderRuntimeCredential) -> None:
        """替换运行期凭据。"""
        ...

    def clear(self) -> None:
        """清除运行期凭据。"""
        ...


class InMemoryProviderCredentialStore:
    """进程内存实现：不落盘，后端重启后自动清空。

    线程安全（``threading.Lock``）。``get()`` 返回的对象仅在后端进程内使用，
    绝不出现在 API/SSE/日志/SQLite 中。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._credential: Optional[ProviderRuntimeCredential] = None

    def get(self) -> Optional[ProviderRuntimeCredential]:
        with self._lock:
            return self._credential

    def set(self, credential: ProviderRuntimeCredential) -> None:
        with self._lock:
            self._credential = credential

    def clear(self) -> None:
        with self._lock:
            self._credential = None


__all__ = [
    "InMemoryProviderCredentialStore",
    "ProviderCredentialStore",
    "ProviderRuntimeCredential",
]
