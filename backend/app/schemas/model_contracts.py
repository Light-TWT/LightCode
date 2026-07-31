"""Phase 2 / WP5: public DTOs for the model provider surface.

Same conventions as `contracts.py`: Pydantic v2, ``extra="forbid"``, camelCase.

Denylist for this module (enforced by `test_provider_health_api.py`): no
``apiKey``, no ``baseUrl``/``base_url``, no ``authorization``, no prompt and no
raw upstream response may ever appear in a field name or a field value.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderCapabilitiesResponse(BaseModel, extra="forbid", populate_by_name=True):
    """What the model is allowed to do, and within which budgets.

    ``tools`` is the read-only allowlist. Writing, shell execution, network
    access, package management and Git remain impossible for the model: it can
    only propose a candidate edit intent that the server independently
    validates and turns into a ChangeSet (WP6).
    """

    tools: list[str]
    canWriteFiles: bool = Field(alias="canWriteFiles")
    canRunCommands: bool = Field(alias="canRunCommands")
    maxToolRounds: int = Field(alias="maxToolRounds")
    maxRequestsPerTask: int = Field(alias="maxRequestsPerTask")
    maxInputBytes: int = Field(alias="maxInputBytes")
    maxOutputTokens: int = Field(alias="maxOutputTokens")
    maxConcurrentTasks: int = Field(alias="maxConcurrentTasks")


class ProviderSecurityResponse(BaseModel, extra="forbid", populate_by_name=True):
    """Boolean/enum security facts only — never the credential or the URL."""

    apiKeyConfigured: bool = Field(alias="apiKeyConfigured")
    transport: Literal["https", "http", "none"]
    originAllowlisted: bool = Field(alias="originAllowlisted")
    followRedirects: bool = Field(alias="followRedirects")
    trustEnvProxies: bool = Field(alias="trustEnvProxies")


class ProviderHealthResponse(BaseModel, extra="forbid", populate_by_name=True):
    """Config-derived provider health. Computing it performs no network call."""

    status: Literal["disabled", "unconfigured", "ready", "degraded"]
    provider: str
    modelId: str = Field(alias="modelId")
    detail: str
    capabilities: ProviderCapabilitiesResponse
    security: ProviderSecurityResponse
