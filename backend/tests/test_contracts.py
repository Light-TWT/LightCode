from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.contracts import (
    ApprovalRequest,
    CreateRealTaskRequest,
    RegisteredWorkspaceResponse,
)


def test_registered_workspace_has_no_root_path() -> None:
    ws = RegisteredWorkspaceResponse(
        id="ws1",
        displayName="WS",
        enabled=True,
        capabilities=["read_file"],
        policyVersion="phase1-single-text-file",
    )
    dumped = ws.model_dump(by_alias=True)
    assert "rootPath" not in dumped
    assert "canonicalRoot" not in dumped


def test_registered_workspace_rejects_root_path() -> None:
    with pytest.raises(ValidationError):
        RegisteredWorkspaceResponse(
            id="ws1",
            displayName="WS",
            enabled=True,
            capabilities=[],
            policyVersion="p",
            rootPath="C:\\x",
        )


def test_approval_rejects_extra_path_fields() -> None:
    with pytest.raises(ValidationError):
        ApprovalRequest(
            decision="approve",
            changeSetId="cs",
            revision=1,
            diffHash="h",
            idempotencyKey="k",
            filePath="x",
        )


def test_create_real_task_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateRealTaskRequest(workspaceId="ws1", title="t", rootPath="C:\\x")
