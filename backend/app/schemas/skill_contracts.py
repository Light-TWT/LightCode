"""Skill 管理公共 DTO（首期 Skill 列表/详情/文档/状态/删除）。

与 `contracts.py`/`model_contracts.py` 相同的约定：Pydantic v2、
``extra="forbid"``、camelCase 字段名（会话/任务 DTO 同款惯例）。

禁止项（测试点名覆盖）：DTO 不得包含 ``rootPath``/``filePath``/``storagePath``/
``packagePath``、ZIP 内容、密钥或异常文本。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SkillSource = Literal["builtin", "uploaded"]
SkillStatus = Literal["disabled", "enabled"]


class SkillSummary(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    name: str
    source: SkillSource
    status: SkillStatus
    summary: str
    documentBytes: int = Field(alias="documentBytes")
    resourceCount: int = Field(alias="resourceCount")
    sectionCount: int = Field(alias="sectionCount")
    createdAt: str = Field(alias="createdAt")
    updatedAt: str = Field(alias="updatedAt")


class SkillDetail(SkillSummary):
    documentSha256: str = Field(alias="documentSha256")
    packageBytes: int = Field(alias="packageBytes")


class SkillDocumentResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    name: str
    source: SkillSource
    status: SkillStatus
    content: str
    documentSha256: str = Field(alias="documentSha256")


class SkillStatusUpdateRequest(BaseModel, extra="forbid", populate_by_name=True):
    status: SkillStatus


class SkillDeleteResponse(BaseModel, extra="forbid", populate_by_name=True):
    id: str
    deleted: Literal[True]


class SkillAgentProjection(BaseModel, extra="forbid", populate_by_name=True):
    """Agent 可用 Skill 的安全投影：只读、无路径、无 ZIP 信息。"""

    id: str
    name: str
    summary: str
    documentSha256: str = Field(alias="documentSha256")
    content: str