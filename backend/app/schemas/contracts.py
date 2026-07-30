from __future__ import annotations

from typing import Any, Literal, Optional

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


# ---------------------------------------------------------------------------
# Phase 1: real file-change closed loop (no root path leakage)
# ---------------------------------------------------------------------------


class RegisteredWorkspaceResponse(BaseModel, extra="forbid", populate_by_name=True):
    """Public workspace view. Must never include the real root path."""

    id: str
    displayName: str = Field(alias="displayName")
    enabled: bool
    capabilities: list[str]
    policyVersion: str = Field(alias="policyVersion")


class BrowseFileEntry(BaseModel, extra="forbid"):
    """A directory listing entry. The browser navigates via ``token`` only; the
    relative path is never echoed back as a client-constructible value."""

    name: str
    kind: str
    token: str


class BrowseFileContent(BaseModel, extra="forbid"):
    """A file preview. Only the content is returned; no path is exposed."""

    content: str


class BrowseSearchHit(BaseModel, extra="forbid"):
    """A search hit. The browser opens it via ``token`` only."""

    name: str
    token: str


class RealChangeSetResponse(BaseModel, extra="forbid", populate_by_name=True):
    changeSetId: str = Field(alias="changeSetId")
    revision: int
    diffHash: str = Field(alias="diffHash")
    baseSha256: str = Field(alias="baseSha256")
    proposedSha256: str = Field(alias="proposedSha256")
    logicalRelativePath: str = Field(alias="logicalRelativePath")
    status: str
    policyVersion: str = Field(alias="policyVersion")
    additions: int
    deletions: int
    before: list[str]
    after: list[str]
    expiresAt: Optional[str] = Field(None, alias="expiresAt")


class ApprovalRequest(BaseModel, extra="forbid"):
    """Client may only submit the decision bound to a specific version.

    Any rootPath/filePath/patch/command/relativePath fields are rejected by
    `extra="forbid"`.
    """

    decision: Literal["approve", "reject"]
    changeSetId: str = Field(alias="changeSetId")
    revision: int
    diffHash: str = Field(alias="diffHash")
    idempotencyKey: str = Field(alias="idempotencyKey")


class CreateRealTaskRequest(BaseModel, extra="forbid"):
    """Browser may only choose a registered workspace and a title.

    The actual change is generated server-side from a controlled template.
    """

    workspaceId: str = Field(alias="workspaceId")
    title: str
    templateId: str = Field(default="append-marker", alias="templateId")


class RealTaskResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    workspaceId: str = Field(alias="workspaceId")
    sessionId: str = Field(alias="sessionId")
    kind: str
    state: str
    title: str
    targetFile: Optional[str] = Field(None, alias="targetFile")
    changeSet: Optional[RealChangeSetResponse] = Field(None, alias="changeSet")
    plan: list[PlanStepResponse]
    toolCalls: list[ToolCallResponse] = Field(alias="toolCalls", default_factory=list)
    verification: VerificationResponse
    createdAt: str = Field(alias="createdAt")
