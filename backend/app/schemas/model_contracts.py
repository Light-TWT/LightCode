"""Phase 2 / WP5: public DTOs for the model provider surface.

Same conventions as `contracts.py`: Pydantic v2, ``extra="forbid"``, camelCase.

Denylist for this module (enforced by `test_provider_health_api.py`): no
``apiKey``, no ``baseUrl``/``base_url``, no ``authorization``, no prompt and no
raw upstream response may ever appear in a field name or a field value.
"""

from __future__ import annotations

from typing import Any, Literal

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


# ---------------------------------------------------------------------------
# WP6: model-task surface. The model only ever *proposes*; the server validates
# and turns a candidate into an immutable ChangeSet (see model_orchestrator).
# Every schema is extra="forbid" and carries no root path, patch, command, key
# or free-form path — by construction the model cannot request those.
# ---------------------------------------------------------------------------


class EditOp(BaseModel, extra="forbid"):
    """One exact, unique text replacement proposed by the model."""

    expectedText: str = Field(alias="expectedText")
    replacementText: str = Field(alias="replacementText")
    occurrence: int = Field(default=1, alias="occurrence")


class ToolRequestMessage(BaseModel, extra="forbid"):
    """The only read the model may request: a guarded, token-scoped read."""

    kind: Literal["tool_request"]
    tool: str
    arguments: dict[str, Any]


class CandidateEditIntent(BaseModel, extra="forbid"):
    """A proposed, server-validated edit intent (not a ChangeSet, not a write)."""

    kind: Literal["candidate_edit_intent"]
    fileToken: str = Field(alias="fileToken")
    baseSha256: str = Field(alias="baseSha256")
    edits: list[EditOp]
    rationale: str
    plan: list[str]


class ModelTaskCreateRequest(BaseModel, extra="forbid"):
    """Browser submits only workspaceId + title. Never a path or content."""

    workspaceId: str = Field(alias="workspaceId")
    title: str


class ModelTaskResponse(BaseModel, extra="forbid"):
    """Read-only view of a model task's current state."""

    id: str
    workspaceId: str = Field(alias="workspaceId")
    state: str
    changeSetId: str | None = Field(default=None, alias="changeSetId")
    detail: str = ""


# ---------------------------------------------------------------------------
# 核心 Agent 更新（阶段 A）：Provider 运行期设置。
#
# 这些 DTO 只在浏览器 <-> 本机 FastAPI 设置端点之间传递。API Key 与完整
# Base URL 绝不进入 SQLite、事件、日志或仓库；响应只回安全摘要。
# ---------------------------------------------------------------------------


class ProviderSettingsRequest(BaseModel, extra="forbid"):
    """Provider 设置表单。仅用于设置端点；请求体绝不落库、绝不打日志。"""

    provider: str = "openai-compatible"
    baseUrl: str = Field(alias="baseUrl")
    apiKey: str = Field(alias="apiKey")
    modelId: str = Field(alias="modelId")


class ProviderSettingsResponse(BaseModel, extra="forbid", populate_by_name=True):
    """Provider 设置的安全视图：无 key、无完整 baseUrl。"""

    configured: bool
    status: Literal["disabled", "unconfigured", "ready", "degraded"]
    provider: str
    modelId: str = Field(alias="modelId")
    detail: str
    originAllowlisted: bool = Field(alias="originAllowlisted")
    transport: Literal["https", "http", "none"]


class ProviderTestRequest(BaseModel, extra="forbid"):
    """Provider 连接测试请求（不保存）。"""

    provider: str = "openai-compatible"
    baseUrl: str = Field(alias="baseUrl")
    apiKey: str = Field(alias="apiKey")
    modelId: str = Field(alias="modelId")


class ProviderTestResponse(BaseModel, extra="forbid", populate_by_name=True):
    """连接测试结果：只有 ok 布尔与稳定错误码。"""

    ok: bool
    code: str = ""
    detail: str = ""


class ProviderProfile(BaseModel, extra="forbid", populate_by_name=True):
    """供应商安全摘要（只读列表项）：无 key、无完整 baseUrl。

    ``baseUrlHost`` 只含 hostname（无 scheme/port/path/userinfo），用于 UI
    识别供应商，绝不泄露完整 Base URL 或任何凭据。
    """

    id: str
    name: str
    provider: str
    modelId: str = Field(alias="modelId")
    enabled: bool
    status: Literal["disabled", "unconfigured", "ready", "degraded"]
    baseUrlHost: str = Field(alias="baseUrlHost")


class ProviderProfileCreate(BaseModel, extra="forbid"):
    """创建供应商配置的请求体（阶段 B）。

    仅用于 POST /provider/profiles；``apiKey``/``baseUrl`` 只在本机设置端点
    传递，绝不落库、不打日志、不回显。
    """

    name: str
    provider: str = "openai-compatible"
    baseUrl: str = Field(alias="baseUrl")
    apiKey: str = Field(alias="apiKey")
    modelId: str = Field(alias="modelId")
    enabled: bool = True


class ProviderProfileDeleteResponse(BaseModel, extra="forbid", populate_by_name=True):
    """删除供应商配置的结果。"""

    ok: bool


# ---------------------------------------------------------------------------
# 核心 Agent 更新（阶段 A）：聊天会话与消息。
# ---------------------------------------------------------------------------


class ChatSessionCreateRequest(BaseModel, extra="forbid"):
    """浏览器只提交 workspaceId + 可选标题。绝不提交路径/内容/key。"""

    workspaceId: str = Field(alias="workspaceId")
    title: str = ""


class ChatSessionUpdateRequest(BaseModel, extra="forbid"):
    """会话重命名：只允许标题，绝不携带路径/补丁/命令/密钥。"""

    title: str


class ChatSessionResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    workspaceId: str = Field(alias="workspaceId")
    title: str
    status: str
    createdAt: str = Field(alias="createdAt")
    updatedAt: str = Field(alias="updatedAt")


class ChatMessageResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    sessionId: str = Field(alias="sessionId")
    sequence: int
    role: Literal["user", "assistant"]
    content: str
    kind: str
    taskId: str = Field(default="", alias="taskId")
    createdAt: str = Field(alias="createdAt")


class ChatMessageSubmitRequest(BaseModel, extra="forbid"):
    """用户消息。仅文本内容；空白/超长由服务端拒绝。"""

    content: str


class ChatSessionDetailResponse(BaseModel, extra="forbid", populate_by_name=True):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse]


class ChatSessionDeleteResponse(BaseModel, extra="forbid", populate_by_name=True):
    ok: bool


class ChatSubmitResponse(BaseModel, extra="forbid", populate_by_name=True):
    """提交消息后的同步结果：持久化的 assistant 消息（或错误消息）。

    ``taskId`` 非空表示本次回复关联了一个等待审批的模型任务（编辑意图）。
    """

    message: ChatMessageResponse
    taskId: str = Field(default="", alias="taskId")


# ---------------------------------------------------------------------------
# 核心 Agent 更新（阶段 A）：模型侧工具/意图协议。
# ---------------------------------------------------------------------------


class AnswerMessage(BaseModel, extra="forbid"):
    """自由问答输出：模型直接返回用户可见回答。"""

    kind: Literal["answer"]
    text: str


class ReadFileToolRequest(BaseModel, extra="forbid"):
    """模型唯一可用的读取工具参数：服务端签发的 fileToken。"""

    fileToken: str = Field(alias="fileToken")


class SearchFilesToolRequest(BaseModel, extra="forbid"):
    """模型唯一可用的检索工具参数：纯文本查询，不含任何路径。"""

    query: str
