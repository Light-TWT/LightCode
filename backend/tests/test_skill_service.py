"""SkillService 受控存储/状态/删除/Agent 投影测试（Task 4 失败基线）。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.db.database import initialize_database
from app.schemas.errors import (
    Phase1Error,
    SKILL_ALREADY_EXISTS,
    SKILL_DELETE_DENIED,
    SKILL_NOT_FOUND,
    SKILL_STORAGE_FAILED,
)
from app.services.skill_service import SkillService


def package_with_name(name: str) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"# {name}\n\n{name} description.\n\n## Rules\n".encode(),
        )
    return data.getvalue()


@pytest.fixture
def skill_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "managed-skills"
    monkeypatch.setenv("LIGHTCODE_SKILLS_PATH", str(root))
    return root


@pytest.fixture
def service(tmp_path: Path, skill_root: Path) -> SkillService:
    connection = initialize_database(tmp_path / "skills.db")
    return SkillService(connection, skill_root)


@pytest.fixture
def package_bytes() -> bytes:
    return package_with_name("review-helper")


def test_database_creates_skills_table_with_all_columns(tmp_path: Path) -> None:
    connection = initialize_database(tmp_path / "skills.db")
    names = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "skills" in names

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(skills)")}
    assert {
        "id",
        "name",
        "source",
        "status",
        "summary",
        "document_sha256",
        "package_sha256",
        "package_bytes",
        "document_bytes",
        "resource_count",
        "section_count",
        "created_at",
        "updated_at",
    } <= columns


def test_upload_persists_disabled_skill_and_document(service: SkillService, package_bytes: bytes) -> None:
    created = service.upload(package_bytes)

    assert created.status == "disabled"
    assert created.source == "uploaded"
    assert service.get_document(created.id).content.startswith("# review-helper")
    assert service.list_enabled_for_agent() == []


def test_enabled_projection_drops_disabled_and_deleted_skills(service: SkillService, package_bytes: bytes) -> None:
    created = service.upload(package_bytes)
    service.set_status(created.id, "enabled")
    assert [item.id for item in service.list_enabled_for_agent()] == [created.id]

    service.set_status(created.id, "disabled")
    assert service.list_enabled_for_agent() == []

    service.delete(created.id)
    assert service.list_enabled_for_agent() == []


def test_failed_duplicate_upload_leaves_no_second_directory(
    service: SkillService, package_bytes: bytes, skill_root: Path
) -> None:
    service.upload(package_bytes)
    with pytest.raises(Phase1Error) as caught:
        service.upload(package_bytes)

    assert caught.value.code == SKILL_ALREADY_EXISTS
    assert len([p for p in skill_root.iterdir() if p.is_dir()]) == 1


def test_upload_failure_leaves_no_row_and_no_directory(
    service: SkillService, package_bytes: bytes, skill_root: Path
) -> None:
    with pytest.raises(Phase1Error):
        service.upload(b"not a zip")
    assert service.list() == []
    assert not skill_root.exists() or list(skill_root.iterdir()) == []


def test_status_transitions_are_strict(service: SkillService, package_bytes: bytes) -> None:
    created = service.upload(package_bytes)
    before = service.get(created.id)
    updated = service.set_status(created.id, "enabled")
    assert updated.status == "enabled"
    assert updated.updatedAt != before.updatedAt


def test_delete_removes_storage_and_rejects_duplicate_and_builtin(
    service: SkillService, package_bytes: bytes, skill_root: Path
) -> None:
    created = service.upload(package_bytes)
    service.set_status(created.id, "enabled")

    response = service.delete(created.id)
    assert response.deleted is True
    assert not (skill_root / created.id).exists()
    assert service.list_enabled_for_agent() == []

    with pytest.raises(Phase1Error) as caught:
        service.delete(created.id)
    assert caught.value.code == SKILL_NOT_FOUND


def test_builtin_delete_denied_and_builtin_projection(service: SkillService) -> None:
    service.seed_builtin_for_test(
        skill_id="skill_11111111111111111111111111111111",
        name="builtin-helper",
        summary="Builtin helper.",
        document="# builtin-helper\n\nBuiltin description.\n",
    )
    assert service.list()[0].source == "builtin"

    with pytest.raises(Phase1Error) as caught:
        service.delete("skill_11111111111111111111111111111111")
    assert caught.value.code == SKILL_DELETE_DENIED


def test_document_hash_mismatch_fails_closed(
    service: SkillService, package_bytes: bytes, skill_root: Path
) -> None:
    created = service.upload(package_bytes)
    skill_dir = skill_root / created.id
    (skill_dir / "SKILL.md").write_text("# tampered\n", encoding="utf-8")

    with pytest.raises(Phase1Error) as caught:
        service.get_document(created.id)
    assert caught.value.code == SKILL_STORAGE_FAILED


def test_get_unknown_skill_returns_not_found(service: SkillService) -> None:
    with pytest.raises(Phase1Error) as caught:
        service.get("skill_ffffffffffffffffffffffffffffffff")
    assert caught.value.code == SKILL_NOT_FOUND


def test_malformed_skill_id_is_rejected(service: SkillService) -> None:
    with pytest.raises(Phase1Error) as caught:
        service.get_document("../../skills")
    assert caught.value.code in (SKILL_NOT_FOUND, SKILL_STORAGE_FAILED)


__all__ = ["package_with_name"]