from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkspaceEntryResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    name: str
    rootPath: str = Field(alias="rootPath")
    status: str
    tags: list[str]
    lastTask: str = Field(alias="lastTask")
    timeAgo: str = Field(alias="timeAgo")


class WorkspaceFileResponse(BaseModel, extra="forbid"):
    id: str
    name: str
    kind: str


class WorkspaceResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    name: str
    rootPath: str = Field(alias="rootPath")
    files: list[WorkspaceFileResponse]


class SessionResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    title: str
    status: str


class PlanStepResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    label: str
    status: str


class ToolCallDetailResponse(BaseModel, extra="forbid"):
    path: Optional[str] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None


class ToolCallResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    toolName: str = Field(alias="toolName")
    target: str
    status: str
    duration: str
    detail: list[str]
    fileSummary: Optional[ToolCallDetailResponse] = Field(None, alias="fileSummary")


class ChangeSetResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    status: str
    filePath: str = Field(alias="filePath")
    additions: int
    deletions: int
    before: list[str]
    after: list[str]


class VerificationResponse(BaseModel, extra="forbid", populate_by_name=True):
    status: str
    command: str
    lines: list[str]


class TaskResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    sessionId: str = Field(alias="sessionId")
    title: str
    state: str
    plan: list[PlanStepResponse]
    toolCalls: list[ToolCallResponse] = Field(alias="toolCalls")
    modelOutput: str = Field(alias="modelOutput")
    changeSet: ChangeSetResponse = Field(alias="changeSet")
    verification: VerificationResponse


class HistoryFileSummaryResponse(BaseModel, extra="forbid"):
    name: str
    additions: int
    deletions: int


class HistoryTestSummaryResponse(BaseModel, extra="forbid"):
    badge: str
    text: str


class HistoryTaskEntryResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    status: str
    title: str
    summary: str
    time: str
    duration: str
    toolCount: int = Field(alias="toolCount")
    files: list[HistoryFileSummaryResponse]
    testResult: HistoryTestSummaryResponse = Field(alias="testResult")


class HistoryPlanStepResponse(BaseModel, extra="forbid"):
    label: str
    state: str


class HistoryToolCallResponse(BaseModel, extra="forbid"):
    icon: str
    name: str
    args: str
    ok: bool


class HistoryFileChangeResponse(BaseModel, extra="forbid"):
    name: str
    additions: int
    deletions: int
    diff: str


class HistoryApprovalResponse(BaseModel, extra="forbid"):
    status: str
    text: str
    time: str


class HistoryTestResultResponse(BaseModel, extra="forbid"):
    command: str
    result: str
    detail: str


class HistoryTaskDetailResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    status: str
    title: str
    time: str
    duration: str
    toolCount: int = Field(alias="toolCount")
    summary: str
    plan: list[HistoryPlanStepResponse]
    toolCalls: list[HistoryToolCallResponse] = Field(alias="toolCalls")
    files: list[HistoryFileChangeResponse]
    approval: HistoryApprovalResponse
    test: HistoryTestResultResponse
    failReason: Optional[str] = Field(None, alias="failReason")
    failDetail: Optional[str] = Field(None, alias="failDetail")
    rejectedCmd: Optional[str] = Field(None, alias="rejectedCmd")
    cancelInfo: Optional[dict[str, str]] = Field(None, alias="cancelInfo")


class TaskEventResponse(BaseModel, extra="forbid", populate_by_name=True):
    sequence: int
    eventType: str = Field(alias="eventType")
    payload: dict[str, Any] = Field(alias="payload")
    createdAt: str = Field(alias="createdAt")
