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
from app.services.browse_tokens import issue, verify
from app.services.event_service import stream_events
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
        return max(after_sequence, int(last_event_id))
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
