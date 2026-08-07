from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config.model_provider import (
    MODEL_ALLOWED_TOOLS,
    ModelProviderConfig,
    build_runtime_config,
    effective_config,
)
from app.schemas.contracts import (
    ApprovalRequest,
    BrowseFileContent,
    BrowseFileEntry,
    BrowseSearchHit,
    CreateRealTaskRequest,
    RealTaskResponse,
    RegisteredWorkspaceResponse,
)
from app.schemas.errors import (
    PROVIDER_CONNECTION_FAILED,
    PROVIDER_SETTINGS_INVALID,
    Phase1Error,
)
from app.schemas.model_contracts import (
    ChatMessageSubmitRequest,
    ChatSessionCreateRequest,
    ChatSessionDeleteResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatSessionUpdateRequest,
    ChatSubmitResponse,
    ModelTaskCreateRequest,
    ModelTaskResponse,
    ProviderCapabilitiesResponse,
    ProviderHealthResponse,
    ProviderSecurityResponse,
    ProviderSettingsRequest,
    ProviderSettingsResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderProfile,
    ProviderProfileCreate,
    ProviderProfileDeleteResponse,
)
from app.services.browse_tokens import issue, verify
from app.services.chat_service import ChatService
from app.services.credential_store import ProviderRuntimeCredential
from app.services.event_service import stream_chat_events, stream_events
from app.services.model_orchestrator import ModelOrchestrator
from app.services.observability import Metrics, correlation_id_var
from app.services.openai_compatible_provider import OpenAICompatibleProvider
from app.services.phase1 import Phase1Service

router = APIRouter(prefix="/api/v1")


def _resolve_after_sequence(request: Request, after_sequence: int) -> int:
    """Honour a browser-sent Last-Event-ID for SSE resume."""
    last_event_id = request.headers.get("last-event-id")
    if last_event_id and last_event_id.isdigit():
        # A client that supplies a resume cursor has reconnected; record it but
        # never the payload or path it implied.
        Metrics.sse_resume()
        return max(after_sequence, int(last_event_id))
    if after_sequence > 0:
        Metrics.sse_resume()
    return after_sequence


def _provider_transport(request: Request):
    """Allow tests to inject an httpx transport (None in production)."""
    return getattr(request.app.state, "provider_transport", None)


# ---------------------------------------------------------------------------
# Phase 1: real file-change closed loop (registered workspaces, guarded tools)
# ---------------------------------------------------------------------------


@router.get("/registered-workspaces", response_model=list[RegisteredWorkspaceResponse])
def registered_workspaces(request: Request) -> list[RegisteredWorkspaceResponse]:
    return Phase1Service.from_request(request).list_registered_workspaces()


@router.get("/registered-workspaces/{workspace_id}/files")
def registered_workspace_files(
    workspace_id: str, request: Request, nodeToken: str = ""
) -> list[BrowseFileEntry]:
    """List a directory. The initial (root) listing takes no token; any deeper
    navigation passes the ``nodeToken`` issued for the parent directory. Each
    entry carries a freshly signed token (``list`` for dirs, ``read`` for files)
    so the browser never constructs or submits a relative path."""
    svc = Phase1Service.from_request(request)
    relative = verify(nodeToken, workspace_id, "list") if nodeToken else ""
    entries = svc.list_files(workspace_id, relative)
    result: list[BrowseFileEntry] = []
    for entry in entries:
        # Sensitive (secret) or non-navigable (link) entries get no token: the
        # browser can see they exist but cannot open or read them.
        if entry["kind"] in ("file", "dir"):
            op = "list" if entry["kind"] == "dir" else "read"
            token = issue(workspace_id, op, entry["relativePath"])
        else:
            token = ""
        result.append(
            BrowseFileEntry(name=entry["name"], kind=entry["kind"], token=token)
        )
    return result


@router.get("/registered-workspaces/{workspace_id}/file")
def registered_workspace_file(
    workspace_id: str, fileToken: str, request: Request
) -> BrowseFileContent:
    """Read a file by its ``fileToken`` (issued by a prior listing/search). The
    server resolves and guards the path; only the content is returned."""
    svc = Phase1Service.from_request(request)
    relative = verify(fileToken, workspace_id, "read")
    content = svc.read_file(workspace_id, relative)["content"]
    return BrowseFileContent(content=content)


@router.get("/registered-workspaces/{workspace_id}/search")
def registered_workspace_search(
    workspace_id: str, query: str, request: Request
) -> list[BrowseSearchHit]:
    """Search a workspace. Hits carry a ``read`` token; the browser opens them
    without ever seeing or submitting a path."""
    svc = Phase1Service.from_request(request)
    hits = svc.search_files(workspace_id, query)
    result: list[BrowseSearchHit] = []
    for hit in hits:
        result.append(
            BrowseSearchHit(
                name=hit["name"],
                token=issue(workspace_id, "read", hit["relativePath"]),
            )
        )
    return result


@router.post("/real-tasks", response_model=RealTaskResponse)
def create_real_task(payload: CreateRealTaskRequest, request: Request) -> RealTaskResponse:
    return Phase1Service.from_request(request).create_real_task(
        payload.workspaceId, payload.title, payload.templateId
    )


@router.get("/real-tasks/{task_id}", response_model=RealTaskResponse)
def get_real_task(task_id: str, request: Request) -> RealTaskResponse:
    return Phase1Service.from_request(request).get_real_task(task_id)


@router.post("/real-tasks/{task_id}/approval", response_model=RealTaskResponse)
def submit_real_task_approval(
    task_id: str, payload: ApprovalRequest, request: Request
) -> RealTaskResponse:
    return Phase1Service.from_request(request).submit_approval(task_id, payload)


@router.get("/real-tasks/{task_id}/events")
def real_task_events(
    task_id: str,
    request: Request,
    after_sequence: int = 0,
    tail: bool = False,
) -> StreamingResponse:
    """Real-task event stream (resume-capable). Reuses the same persisted
    `task_events` table as the generic endpoint; the browser connects by the
    real task id and resumes via `?afterSequence=` or `Last-Event-ID`."""
    service = Phase1Service.from_request(request)
    after = _resolve_after_sequence(request, after_sequence)
    return StreamingResponse(
        stream_events(service, task_id, after, tail),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Phase 2 / WP5: model provider health + runtime settings (阶段 A)
# ---------------------------------------------------------------------------


@router.get("/provider/health", response_model=ProviderHealthResponse)
def provider_health(request: Request) -> ProviderHealthResponse:
    """Report the provider status without contacting the provider.

    The response is derived purely from backend configuration (env snapshot
    merged with any runtime credential saved via the settings form), so calling
    this endpoint can never open a socket, incur cost or leak a prompt. It
    carries no API key, no Authorization header and no base URL.
    """
    config: ModelProviderConfig = effective_config(
        request.app.state.env_model_provider, request.app.state.credential_store
    )
    return ProviderHealthResponse(
        status=config.status(),
        provider=config.provider,
        modelId=config.model_id,
        detail=config.status_detail(),
        capabilities=ProviderCapabilitiesResponse(
            tools=list(MODEL_ALLOWED_TOOLS),
            canWriteFiles=False,
            canRunCommands=False,
            maxToolRounds=config.max_tool_rounds,
            maxRequestsPerTask=config.max_requests_per_task,
            maxInputBytes=config.max_input_bytes,
            maxOutputTokens=config.max_output_tokens,
            maxConcurrentTasks=config.max_concurrent_tasks,
        ),
        security=ProviderSecurityResponse(
            apiKeyConfigured=config.api_key_configured,
            transport=config.transport,
            originAllowlisted=config.origin_allowlisted,
            followRedirects=False,
            trustEnvProxies=False,
        ),
    )


def _settings_response(request: Request, configured: bool) -> ProviderSettingsResponse:
    config: ModelProviderConfig = effective_config(
        request.app.state.env_model_provider, request.app.state.credential_store
    )
    return ProviderSettingsResponse(
        configured=configured,
        status=config.status(),
        provider=config.provider,
        modelId=config.model_id,
        detail=config.status_detail(),
        originAllowlisted=config.origin_allowlisted,
        transport=config.transport,
    )


@router.get("/provider/settings", response_model=ProviderSettingsResponse)
def provider_settings(request: Request) -> ProviderSettingsResponse:
    """Read the current (safe) provider settings view. No key, no full URL."""
    store = request.app.state.credential_store
    return _settings_response(request, store.get() is not None)


@router.post("/provider/settings/test", response_model=ProviderTestResponse)
def test_provider_settings(
    payload: ProviderTestRequest, request: Request
) -> ProviderTestResponse:
    """Test connectivity against the submitted provider without saving.

    Returns 200 with ``ok=false`` and a stable code so the UI can show the
    error inline; never leaks the key or the full URL.
    """
    correlation_id_var.set(getattr(request.state, "correlation_id", "-"))
    env_config: ModelProviderConfig = request.app.state.env_model_provider
    credential = ProviderRuntimeCredential(
        provider=payload.provider.strip() or "openai-compatible",
        base_url=payload.baseUrl.strip(),
        model_id=payload.modelId.strip(),
        api_key=payload.apiKey.strip(),
    )
    config = effective_config(env_config, type("_Store", (), {"get": lambda self: credential})())
    if config.status() != "ready":
        return ProviderTestResponse(
            ok=False, code=PROVIDER_SETTINGS_INVALID, detail=config.status_detail()
        )
    try:
        OpenAICompatibleProvider(config, transport=_provider_transport(request)).test_connection()
    except Phase1Error as exc:
        return ProviderTestResponse(ok=False, code=exc.code, detail=exc.message)
    return ProviderTestResponse(ok=True)


@router.post("/provider/settings", response_model=ProviderSettingsResponse)
def save_provider_settings(
    payload: ProviderSettingsRequest, request: Request
) -> ProviderSettingsResponse:
    """Test the submitted provider and, on success, save it to the runtime
    credential store (in-memory; lost on restart). Fail-closed: never saved if
    the config is not `ready` or the connection test fails."""
    correlation_id_var.set(getattr(request.state, "correlation_id", "-"))
    env_config: ModelProviderConfig = request.app.state.env_model_provider
    credential = ProviderRuntimeCredential(
        provider=payload.provider.strip() or "openai-compatible",
        base_url=payload.baseUrl.strip(),
        model_id=payload.modelId.strip(),
        api_key=payload.apiKey.strip(),
    )
    config = build_runtime_config(env_config, credential)
    if config.status() != "ready":
        raise Phase1Error(
            PROVIDER_SETTINGS_INVALID, config.status_detail(), http_status=422
        )
    try:
        OpenAICompatibleProvider(config, transport=_provider_transport(request)).test_connection()
    except Phase1Error as exc:
        raise Phase1Error(
            PROVIDER_CONNECTION_FAILED, exc.message, http_status=502
        ) from exc
    request.app.state.credential_store.set(credential)
    return _settings_response(request, configured=True)


@router.delete("/provider/settings", response_model=ProviderSettingsResponse)
def clear_provider_settings(request: Request) -> ProviderSettingsResponse:
    """Clear the runtime credential (falls back to env config / unconfigured)."""
    request.app.state.credential_store.clear()
    return _settings_response(request, configured=False)


def _profile_from_config(profile_id: str, config: ModelProviderConfig) -> ProviderProfile:
    """Build a safe summary profile from a resolved config (never a raw URL)."""
    status = config.status()
    return ProviderProfile(
        id=profile_id,
        name=config.provider,
        provider=config.provider,
        modelId=config.model_id,
        enabled=status == "ready",
        status=status,
        baseUrlHost=config.host_summary,
    )


def _profile_from_credential(
    profile_id: str,
    credential: ProviderRuntimeCredential,
    env_config: ModelProviderConfig,
) -> ProviderProfile:
    config = build_runtime_config(env_config, credential)
    status = config.status()
    return ProviderProfile(
        id=profile_id,
        name=credential.name or credential.provider,
        provider=credential.provider,
        modelId=credential.model_id,
        enabled=bool(credential.enabled) and status == "ready",
        status=status,
        baseUrlHost=config.host_summary,
    )


@router.get("/provider/profiles", response_model=list[ProviderProfile])
def provider_profiles(request: Request) -> list[ProviderProfile]:
    """Read-only safe summary list of provider profiles (config-derived).

    Lists every saved runtime profile; when none is saved, falls back to the
    env-derived config as a single ``default`` entry (or ``[]`` when disabled).
    Never contacts the provider and never exposes the API key, the full Base
    URL or the Authorization header.
    """
    env_config: ModelProviderConfig = request.app.state.env_model_provider
    store = request.app.state.credential_store
    profiles = [
        _profile_from_credential(profile_id, credential, env_config)
        for profile_id, credential in store.get_all().items()
    ]
    if not profiles and env_config.status() != "disabled":
        profiles = [_profile_from_config("default", env_config)]
    return profiles


@router.post("/provider/profiles", response_model=ProviderProfile)
def create_provider_profile(
    payload: ProviderProfileCreate, request: Request
) -> ProviderProfile:
    """Create a provider profile: test connectivity, save only on success.

    The API key and full Base URL live only in the request body and the
    in-memory credential store; the response is the safe summary.
    """
    correlation_id_var.set(getattr(request.state, "correlation_id", "-"))
    env_config: ModelProviderConfig = request.app.state.env_model_provider
    credential = ProviderRuntimeCredential(
        provider=payload.provider.strip() or "openai-compatible",
        base_url=payload.baseUrl.strip(),
        model_id=payload.modelId.strip(),
        name=payload.name.strip(),
        enabled=payload.enabled,
        api_key=payload.apiKey.strip(),
    )
    config = build_runtime_config(env_config, credential)
    if config.status() != "ready":
        raise Phase1Error(
            PROVIDER_SETTINGS_INVALID, config.status_detail(), http_status=422
        )
    try:
        OpenAICompatibleProvider(config, transport=_provider_transport(request)).test_connection()
    except Phase1Error as exc:
        raise Phase1Error(
            PROVIDER_CONNECTION_FAILED, exc.message, http_status=502
        ) from exc
    profile_id = request.app.state.credential_store.set(credential)
    return _profile_from_credential(profile_id, credential, env_config)


@router.get("/provider/profiles/{profile_id}", response_model=ProviderProfile)
def get_provider_profile(profile_id: str, request: Request) -> ProviderProfile:
    env_config: ModelProviderConfig = request.app.state.env_model_provider
    credential = request.app.state.credential_store.get_named(profile_id)
    if credential is None:
        raise Phase1Error("PROFILE_NOT_FOUND", "未找到该供应商配置。", http_status=404)
    return _profile_from_credential(profile_id, credential, env_config)


@router.delete("/provider/profiles/{profile_id}", response_model=ProviderProfileDeleteResponse)
def delete_provider_profile(profile_id: str, request: Request) -> ProviderProfileDeleteResponse:
    removed = request.app.state.credential_store.remove(profile_id)
    if not removed:
        raise Phase1Error("PROFILE_NOT_FOUND", "未找到该供应商配置。", http_status=404)
    return ProviderProfileDeleteResponse(ok=True)


# ---------------------------------------------------------------------------
# Phase 2 / WP6: model-task surface. The model only proposes; the server
# validates and the user approves (reuses the Phase 1 guarded approval path).
# No root path, patch, command or key is ever submitted by the browser.
# ---------------------------------------------------------------------------


@router.post("/model-tasks", response_model=ModelTaskResponse)
def create_model_task(payload: ModelTaskCreateRequest, request: Request) -> ModelTaskResponse:
    """Create a model task and run the orchestration end-to-end.

    The browser submits only ``workspaceId`` + ``title``. The server creates the
    task in ``planning``, runs the read -> candidate -> ChangeSet loop under its
    own control, and returns either ``awaiting_approval`` (with an immutable
    ChangeSet the user can approve via the Phase 1 endpoint) or ``failed`` with a
    stable machine code. No filesystem write occurs here — only at approval.
    """
    correlation_id_var.set(getattr(request.state, "correlation_id", "-"))
    return ModelOrchestrator.from_request(request).create_model_task(
        payload.workspaceId, payload.title
    )


@router.get("/model-tasks/{task_id}", response_model=ModelTaskResponse)
def get_model_task(task_id: str, request: Request) -> ModelTaskResponse:
    return ModelOrchestrator.from_request(request).get_model_task(task_id)


# ---------------------------------------------------------------------------
# 核心 Agent 更新（阶段 A）：聊天会话与消息（SQLite 持久化 + SSE 续传）
# ---------------------------------------------------------------------------


@router.get("/workspaces/{workspace_id}/chat-sessions", response_model=list[ChatSessionResponse])
def chat_sessions(workspace_id: str, request: Request) -> list[ChatSessionResponse]:
    return ChatService.from_request(request).list_sessions(workspace_id)


@router.post("/workspaces/{workspace_id}/chat-sessions", response_model=ChatSessionResponse)
def create_chat_session(
    workspace_id: str, payload: ChatSessionCreateRequest, request: Request
) -> ChatSessionResponse:
    return ChatService.from_request(request).create_session(workspace_id, payload.title)


@router.get("/chat-sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(
    session_id: str, request: Request, workspaceId: str = ""
) -> ChatSessionDetailResponse:
    return ChatService.from_request(request).get_session(
        session_id, workspaceId or None
    )


@router.post("/chat-sessions/{session_id}/messages", response_model=ChatSubmitResponse)
def submit_chat_message(
    session_id: str, payload: ChatMessageSubmitRequest, request: Request
) -> ChatSubmitResponse:
    """Submit a user message. The user message is persisted first, then the
    chat orchestration runs synchronously and the assistant reply is persisted.
    No rootPath/filePath/patch/command/key is ever accepted."""
    correlation_id_var.set(getattr(request.state, "correlation_id", "-"))
    return ChatService.from_request(request).submit_message(session_id, payload.content)


@router.patch("/chat-sessions/{session_id}", response_model=ChatSessionResponse)
def rename_chat_session(
    session_id: str, payload: ChatSessionUpdateRequest, request: Request, workspaceId: str
) -> ChatSessionResponse:
    """Rename a chat session. Request body is limited to ``title`` (extra=forbid);
    workspace ownership is enforced via the required ``workspaceId`` query param."""
    return ChatService.from_request(request).rename_session(
        session_id, workspaceId, payload.title
    )


@router.delete("/chat-sessions/{session_id}", response_model=ChatSessionDeleteResponse)
def delete_chat_session(
    session_id: str, request: Request, workspaceId: str
) -> ChatSessionDeleteResponse:
    """Permanently delete a chat session (workspace ownership required)."""
    ChatService.from_request(request).delete_session(session_id, workspaceId)
    return ChatSessionDeleteResponse(ok=True)


@router.get("/chat-sessions/{session_id}/events")
def chat_session_events(
    session_id: str,
    request: Request,
    after_sequence: int = 0,
    tail: bool = False,
) -> StreamingResponse:
    """Chat-message event stream (resume-capable via `afterSequence=` /
    `Last-Event-ID`). Replays persisted chat_messages as `chat.event` frames."""
    service = ChatService.from_request(request)
    after = _resolve_after_sequence(request, after_sequence)
    return StreamingResponse(
        stream_chat_events(service, session_id, after, tail),
        media_type="text/event-stream",
    )
