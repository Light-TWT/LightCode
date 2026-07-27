import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.contracts import (
    ApprovalRequest,
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
from app.services.phase1 import Phase1Service
from app.services.runtime import RuntimeService

router = APIRouter(prefix="/api/v1")

# SSE resume behaviour. After replaying persisted events, a `tail=true` stream
# keeps polling for new events up to this timeout so the browser can resume
# after a dropped connection (contract §API、事件与错误码: SSE 仅传递已持久化
# 事实事件，且支持基于 sequence / Last-Event-ID 的续传).
SSE_TAIL_TIMEOUT_SECONDS = 30
SSE_POLL_INTERVAL_SECONDS = 0.5


def _event_to_sse(event: TaskEventResponse) -> str:
    """Serialize a task event as an SSE frame with an `id` for Last-Event-ID."""
    data = event.model_dump_json(by_alias=True)
    return f"id: {event.sequence}\nevent: task.event\ndata: {data}\n\n"


def _build_event_stream(service: RuntimeService, task_id: str, after_sequence: int, tail: bool):
    pending = service.list_task_events_after(task_id, after_sequence)
    for event in pending:
        yield _event_to_sse(event)
        after_sequence = event.sequence
    if not tail:
        yield "event: stream.end\ndata: {}\n\n"
        return
    deadline = time.monotonic() + SSE_TAIL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        for event in service.list_task_events_after(task_id, after_sequence):
            yield _event_to_sse(event)
            after_sequence = event.sequence
        time.sleep(SSE_POLL_INTERVAL_SECONDS)
    yield "event: stream.end\ndata: {}\n\n"


def _resolve_after_sequence(request: Request, after_sequence: int) -> int:
    """Honour a browser-sent Last-Event-ID for SSE resume."""
    last_event_id = request.headers.get("last-event-id")
    if last_event_id and last_event_id.isdigit():
        return max(after_sequence, int(last_event_id))
    return after_sequence


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
        _build_event_stream(service, task_id, after, tail),
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
    workspace_id: str, request: Request, path: str = ""
) -> list[dict]:
    return Phase1Service.from_request(request).list_files(workspace_id, path)


@router.get("/registered-workspaces/{workspace_id}/file")
def registered_workspace_file(
    workspace_id: str, path: str, request: Request
) -> dict:
    return Phase1Service.from_request(request).read_file(workspace_id, path)


@router.get("/registered-workspaces/{workspace_id}/search")
def registered_workspace_search(
    workspace_id: str, query: str, request: Request
) -> list[dict]:
    return Phase1Service.from_request(request).search_files(workspace_id, query)


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
        _build_event_stream(service, task_id, after, tail),
        media_type="text/event-stream",
    )
