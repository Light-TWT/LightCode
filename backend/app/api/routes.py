from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.contracts import (
    HistoryTaskDetailResponse,
    HistoryTaskEntryResponse,
    SessionResponse,
    TaskEventResponse,
    TaskResponse,
    WorkspaceEntryResponse,
    WorkspaceResponse,
)
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


@router.get("/tasks/{task_id}/events")
def task_events(task_id: str, request: Request) -> StreamingResponse:
    service = RuntimeService.from_request(request)

    def event_stream():
        events = service.list_task_events(task_id)
        for event in events:
            data = event.model_dump_json(by_alias=True)
            yield f"event: task.event\ndata: {data}\n\n"
        yield "event: stream.end\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
