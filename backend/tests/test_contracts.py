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


def test_skill_status_update_accepts_only_known_enabled_states() -> None:
    from app.schemas.skill_contracts import SkillStatusUpdateRequest

    assert SkillStatusUpdateRequest(status="enabled").status == "enabled"
    assert SkillStatusUpdateRequest(status="disabled").status == "disabled"

    with pytest.raises(ValidationError):
        SkillStatusUpdateRequest(status="active")


def test_skill_summary_rejects_path_fields() -> None:
    from app.schemas.skill_contracts import SkillSummary

    with pytest.raises(ValidationError):
        SkillSummary(
            id="skill_1",
            name="review-helper",
            source="uploaded",
            status="disabled",
            summary="Review code.",
            documentBytes=10,
            resourceCount=0,
            sectionCount=0,
            createdAt="2026-08-12T00:00:00Z",
            updatedAt="2026-08-12T00:00:00Z",
            storagePath="C:/secret",
        )
