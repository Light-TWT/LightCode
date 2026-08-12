"""Skill REST API 契约与脱敏（redaction）测试（Task 5）。

覆盖：上传/查询/文档/状态/删除、multipart 字段约束、错误码 fail-closed、
响应不含路径/条目名/异常文本、内置删除拒绝、未知字段拒绝。
"""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


def package_bytes(name: str = "review-helper") -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{name}/SKILL.md",
            f"# {name}\n\n{name} description.\n\n## Rules\n".encode(),
        )
    return data.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    os.environ["LIGHTCODE_DATABASE_PATH"] = str(tmp_path / "skills.db")
    os.environ["LIGHTCODE_SKILLS_PATH"] = str(tmp_path / "managed-skills")
    with TestClient(app) as c:
        yield c
    os.environ.pop("LIGHTCODE_DATABASE_PATH", None)
    os.environ.pop("LIGHTCODE_SKILLS_PATH", None)


def test_upload_returns_disabled_safe_summary(client: TestClient) -> None:
    response = client.post(
        "/api/v1/skills/upload",
        files={"package": ("review-helper.zip", package_bytes(), "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["source"] == "uploaded"
    assert "path" not in " ".join(body).lower()
    assert "# review-helper" not in " ".join(str(value) for value in body.values())


def test_upload_rejects_wrong_form_field_and_non_zip(client: TestClient) -> None:
    missing = client.post("/api/v1/skills/upload", files={"file": ("x.zip", b"data")})
    wrong = client.post("/api/v1/skills/upload", files={"package": ("x.txt", b"not zip")})

    assert missing.status_code == 422
    assert wrong.status_code == 400
    assert wrong.json()["code"] == "SKILL_PACKAGE_TYPE_DENIED"


def test_status_document_and_uploaded_delete(client: TestClient) -> None:
    created = client.post(
        "/api/v1/skills/upload", files={"package": ("review.zip", package_bytes())}
    ).json()
    skill_id = created["id"]

    enabled = client.patch(f"/api/v1/skills/{skill_id}/status", json={"status": "enabled"})
    document = client.get(f"/api/v1/skills/{skill_id}/document")
    deleted = client.delete(f"/api/v1/skills/{skill_id}")

    assert enabled.status_code == 200
    assert enabled.json()["status"] == "enabled"
    assert document.json()["content"].startswith("# review-helper")
    for key in ("rootPath", "filePath", "storagePath", "packagePath"):
        assert key not in document.json()
    assert deleted.json() == {"id": skill_id, "deleted": True}


def test_list_and_get_roundtrip(client: TestClient) -> None:
    created = client.post(
        "/api/v1/skills/upload", files={"package": ("review.zip", package_bytes())}
    ).json()

    listed = client.get("/api/v1/skills")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    detail = client.get(f"/api/v1/skills/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["documentSha256"] == created["documentSha256"]
    assert detail.json()["packageBytes"] > 0


def test_patch_rejects_unknown_fields_and_states(client: TestClient) -> None:
    created = client.post(
        "/api/v1/skills/upload", files={"package": ("review.zip", package_bytes())}
    ).json()

    with_fields = client.patch(
        f"/api/v1/skills/{created['id']}/status",
        json={"status": "enabled", "storagePath": "C:/secret"},
    )
    with_state = client.patch(
        f"/api/v1/skills/{created['id']}/status", json={"status": "active"}
    )

    assert with_fields.status_code == 422
    assert with_state.status_code == 422


def test_upload_rejects_invalid_zip_and_leaves_no_row(client: TestClient) -> None:
    response = client.post(
        "/api/v1/skills/upload", files={"package": ("bad.zip", b"not a zip")}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "SKILL_PACKAGE_INVALID"
    assert client.get("/api/v1/skills").json() == []


def test_duplicate_upload_returns_already_exists(client: TestClient) -> None:
    payload = package_bytes("dup-helper")
    first = client.post("/api/v1/skills/upload", files={"package": ("a.zip", payload)})
    second = client.post("/api/v1/skills/upload", files={"package": ("b.zip", payload)})

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["code"] == "SKILL_ALREADY_EXISTS"
    assert len(client.get("/api/v1/skills").json()) == 1


def test_unknown_skill_returns_not_found(client: TestClient) -> None:
    missing = "skill_ffffffffffffffffffffffffffffffff"
    assert client.get(f"/api/v1/skills/{missing}").status_code == 404
    assert client.get(f"/api/v1/skills/{missing}/document").status_code == 404
    assert client.delete(f"/api/v1/skills/{missing}").status_code == 404
    assert client.patch(
        f"/api/v1/skills/{missing}/status", json={"status": "enabled"}
    ).status_code == 404


def test_builtin_delete_denied(client: TestClient) -> None:
    from app.services.skill_service import SkillService

    service = SkillService(client.app.state.db, client.app.state.skill_root)
    builtin = service.seed_builtin_for_test(
        skill_id="skill_22222222222222222222222222222222",
        name="builtin-helper",
        summary="Builtin.",
        document="# builtin-helper\n\nBuiltin description.\n",
    )

    listed = client.get("/api/v1/skills").json()
    assert any(item["source"] == "builtin" for item in listed)

    denied = client.delete(f"/api/v1/skills/{builtin.id}")
    assert denied.status_code == 403
    assert denied.json()["code"] == "SKILL_DELETE_DENIED"

    ok = client.patch(f"/api/v1/skills/{builtin.id}/status", json={"status": "disabled"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "disabled"


def test_upload_error_responses_do_not_leak_locations_or_entry_names(client: TestClient) -> None:
    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("SKILL.md", b"# valid\n")
        archive.writestr("../../escape.txt", b"x")
    response = client.post(
        "/api/v1/skills/upload", files={"package": ("evil.zip", malicious.getvalue())}
    )

    assert response.status_code == 400
    text = response.text.lower()
    assert "skill" in text
    for leaked in ("escape", "tmp-", "managed-skills", "traceback", "\\"):
        assert leaked not in text