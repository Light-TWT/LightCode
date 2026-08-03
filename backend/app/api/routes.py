import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.contracts import (
    ApprovalRequest,
    BrowseFileContent,
    BrowseFileEntry,
    BrowseSearchHit,
    CreateRealTaskRequest,
    HistoryTaskDetailResponse,
    HistoryTaskEntryResponse,
    RealTaskResponse,
    RegisteredWorkspaceResponse,
    SessionResponse,
    TaskEventResponse,
    TaskResponse,
    WorkspaceEntryResponse,
    WorkspaceResponse,
)
from app.config.model_provider import MODEL_ALLOWED_TOOLS, ModelProviderConfig
from app.schemas.model_contracts import (
    ModelTaskCreateRequest,
    ModelTaskResponse,
    ProviderCapabilitiesResponse,
    ProviderHealthResponse,
    ProviderSecurityResponse,
)
from app.services.browse_tokens import issue, verify
from app.services.event_service import stream_events
from app.services.model_orchestrator import ModelOrchestrator
from app.services.observability import Metrics, correlation_id_var
from app.services.phase1 import Phase1Service
from app.services.runtime import RuntimeService

router = APIRouter(prefix="/api/v1")


@router.get("/workspaces/recent", response_model=list[WorkspaceEntryResponse])
def recent_workspaces(request: Request) -> list[WorkspaceEntryResponse]:
    return RuntimeService.from_request(request).list_recent_workspaces()


@router.get("/workspaces", response_model=list[WorkspaceEntryResponse])
def workspaces(request: Request) -> list[WorkspaceEntryResponse]:
    return RuntimeService.from_request(request).list_workspaces()


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def workspace(workspace_id: str, request: Request) -> WorkspaceResponse:
    return RuntimeService.from_request(request).get_workspace(workspace_id)


@router.get("/workspaces/{workspace_id}/sessions", response_model=list[SessionResponse])
def workspace_sessions(workspace_id: str, request: Request) -> list[SessionResponse]:
    return RuntimeService.from_request(request).list_workspace_sessions(workspace_id)


@router.get("/sessions/{session_id}/tasks/current", response_model=TaskResponse)
def current_task(session_id: str, request: Request) -> TaskResponse:
    return RuntimeService.from_request(request).get_current_task(session_id)


@router.post("/tasks/{task_id}/changeset/approve", response_model=TaskResponse)
def approve_changeset(task_id: str, request: Request) -> TaskResponse:
    return RuntimeService.from_request(request).approve_changeset(task_id)


@router.get("/workspaces/{workspace_id}/tasks/history", response_model=list[HistoryTaskEntryResponse])
def task_history(workspace_id: str, request: Request) -> list[HistoryTaskEntryResponse]:
    return RuntimeService.from_request(request).list_task_history(workspace_id)


@router.get("/tasks/{task_id}", response_model=HistoryTaskDetailResponse)
def task_detail(task_id: str, request: Request) -> HistoryTaskDetailResponse:
    return RuntimeService.from_request(request).get_task_detail(task_id)


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


@router.get("/tasks/{task_id}/events")
def task_events(
    task_id: str,
    request: Request,
    after_sequence: int = 0,
    tail: bool = False,
) -> StreamingResponse:
    """Replay persisted task events; supports resume via `?afterSequence=` or
    the `Last-Event-ID` header, and optional tailing for live catch-up."""
    service = RuntimeService.from_request(request)
    after = _resolve_after_sequence(request, after_sequence)
    return StreamingResponse(
        stream_events(service, task_id, after, tail),
        media_type="text/event-stream",
    )


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
    service = RuntimeService.from_request(request)
    after = _resolve_after_sequence(request, after_sequence)
    return StreamingResponse(
        stream_events(service, task_id, after, tail),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Phase 2 / WP5: model provider health (default-off, config-derived, read-only)
# ---------------------------------------------------------------------------


@router.get("/provider/health", response_model=ProviderHealthResponse)
def provider_health(request: Request) -> ProviderHealthResponse:
    """Report the provider status without contacting the provider.

    The response is derived purely from backend configuration, so calling this
    endpoint can never open a socket, incur cost or leak a prompt. It carries
    no API key, no Authorization header and no base URL — only the scheme, the
    allowlist verdict and the declared budgets (safety-contract §API/事件/错误码).
    """
    config: ModelProviderConfig = request.app.state.model_provider
    return ProviderHealthResponse(
        status=config.status(),
        provider=config.provider,
        modelId=config.model_id,
        detail=config.status_detail(),
        capabilities=ProviderCapabilitiesResponse(
            tools=list(MODEL_ALLOWED_TOOLS),
            # Hard product invariants, not runtime toggles: the model proposes,
            # the server decides, the user approves.
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
    # FastAPI runs this sync route in a threadpool, so re-bind the correlation id
    # set by the HTTP middleware (ContextVars do not cross into the pool thread).
    correlation_id_var.set(getattr(request.state, "correlation_id", "-"))
    return ModelOrchestrator.from_request(request).create_model_task(
        payload.workspaceId, payload.title
    )


@router.get("/model-tasks/{task_id}", response_model=ModelTaskResponse)
def get_model_task(task_id: str, request: Request) -> ModelTaskResponse:
    return ModelOrchestrator.from_request(request).get_model_task(task_id)
