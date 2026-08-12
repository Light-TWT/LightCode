"""纯函数 ZIP 包安全识别失败基线（Task 1）。

这些测试先行编写，用于驱动 backend/app/services/skill_package.py 的实现；
当前阶段应因模块不存在而在收集阶段失败。
"""

import io
import zipfile

import pytest

from app.schemas.errors import Phase1Error
from app.services.skill_package import (
    inspect_skill_package,
    inspect_skill_package_info_only,
)


def package(entries: dict[str, bytes]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return data.getvalue()


def package_from_list(entries: list[tuple[str, bytes]]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return data.getvalue()


def test_inspect_accepts_one_utf8_skill_document() -> None:
    result = inspect_skill_package(
        package({"example/SKILL.md": b"# review-helper\n\nReview code with evidence.\n\n## Rules\n"})
    )

    assert result.name == "review-helper"
    assert result.summary == "Review code with evidence."
    assert result.resource_count == 0
    assert result.section_count == 1
    assert result.document == "# review-helper\n\nReview code with evidence.\n\n## Rules\n"


@pytest.mark.parametrize(
    ("entries", "code"),
    [
        ({}, "SKILL_DOCUMENT_MISSING"),
        ({"SKILL.md": b"# one", "nested/SKILL.md": b"# two"}, "SKILL_DOCUMENT_DUPLICATED"),
        ({"../SKILL.md": b"# escape"}, "SKILL_PACKAGE_ENTRY_DENIED"),
        ({"SKILL.md": b"not a heading"}, "SKILL_DOCUMENT_INVALID"),
        ({"SKILL.md": b"# valid", ".env": b"SECRET=x"}, "SKILL_PACKAGE_ENTRY_DENIED"),
    ],
)
def test_inspect_rejects_unsafe_or_invalid_packages(entries: dict[str, bytes], code: str) -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package(entries))

    assert caught.value.code == code


def test_inspect_rejects_encrypted_entry() -> None:
    data = package({"SKILL.md": b"# valid"})
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        info = archive.infolist()[0]
        info.flag_bits |= 0x1
        with pytest.raises(Phase1Error) as caught:
            inspect_skill_package_info_only([info], data)

    assert caught.value.code == "SKILL_PACKAGE_ENTRY_DENIED"


@pytest.mark.parametrize(
    "path",
    ["/SKILL.md", "C:/SKILL.md", "\\\\host\\share\\SKILL.md", "a/../../SKILL.md", "a/b/c/d/SKILL.md"],
)
def test_inspect_rejects_non_relative_or_too_deep_paths(path: str) -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({path: b"# valid"}))

    assert caught.value.code == "SKILL_PACKAGE_ENTRY_DENIED"


def test_inspect_rejects_empty_and_oversized_packages() -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(b"")
    assert caught.value.code == "SKILL_PACKAGE_INVALID"

    oversized = b"x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(oversized)
    assert caught.value.code == "SKILL_PACKAGE_SIZE_DENIED"


def test_inspect_rejects_corrupt_and_non_zip_bytes() -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(b"not a zip archive at all")
    assert caught.value.code == "SKILL_PACKAGE_INVALID"

    corrupt = package({"SKILL.md": b"# valid"})[:32] + b"\x00" * 16
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(corrupt)
    assert caught.value.code == "SKILL_PACKAGE_INVALID"


def test_inspect_rejects_too_many_entries_and_excessive_entry_bytes() -> None:
    many = {"SKILL.md": b"# valid"}
    for index in range(65):
        many[f"file-{index}.txt"] = b"x"
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package(many))
    assert caught.value.code == "SKILL_PACKAGE_STRUCTURE_DENIED"

    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(
            package({"SKILL.md": b"# valid", "big.txt": b"y" * (2 * 1024 * 1024 + 1)})
        )
    assert caught.value.code == "SKILL_PACKAGE_ENTRY_DENIED"


def test_inspect_rejects_extracted_total_above_budget() -> None:
    entries = {"SKILL.md": b"# valid"}
    for index in range(6):
        entries[f"chunk-{index}.txt"] = b"z" * (2 * 1024 * 1024 - 100)
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package(entries))
    assert caught.value.code == "SKILL_PACKAGE_STRUCTURE_DENIED"


def test_inspect_rejects_non_utf8_empty_and_invalid_documents() -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({"SKILL.md": b"# ok\xff\xfe"}))
    assert caught.value.code == "SKILL_DOCUMENT_INVALID"

    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({"SKILL.md": b"   \n\t "}))
    assert caught.value.code == "SKILL_DOCUMENT_INVALID"


def test_inspect_rejects_oversized_document_and_invalid_titles() -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({"SKILL.md": b"# " + b"a" * 256 * 1024}))
    assert caught.value.code == "SKILL_DOCUMENT_INVALID"

    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({"SKILL.md": ("# " + "a" * 81).encode()}))
    assert caught.value.code == "SKILL_DOCUMENT_INVALID"

    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({"SKILL.md": "# bad\x00title\ncontent".encode()}))
    assert caught.value.code == "SKILL_DOCUMENT_INVALID"


@pytest.mark.parametrize(
    "name",
    [".env", ".git", "id_rsa", "credentials.json", "secrets.txt", "cert.pem", "key.pem"],
)
def test_inspect_rejects_sensitive_names(name: str) -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(package({"SKILL.md": b"# valid", name: b"SECRET"}))
    assert caught.value.code == "SKILL_PACKAGE_ENTRY_DENIED"


def test_inspect_rejects_disallowed_suffixes_and_duplicates() -> None:
    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(
            package({"SKILL.md": b"# valid", "run.exe": b"MZ", "sh": b"#!/bin/sh"})
        )
    assert caught.value.code == "SKILL_PACKAGE_ENTRY_DENIED"

    with pytest.raises(Phase1Error) as caught:
        inspect_skill_package(
            package_from_list([("SKILL.md", b"# valid"), ("SKILL.md", b"# duplicate")])
        )
    assert caught.value.code == "SKILL_PACKAGE_ENTRY_DENIED"


def test_inspect_counts_resources_and_sections() -> None:
    result = inspect_skill_package(
        package(
            {
                "example/SKILL.md": b"# helper\n\nIntro paragraph.\n\n## First\n\n### Sub\n\n## Second\n",
                "example/logo.png": b"\x89PNG",
                "example/notes.txt": b"note",
            }
        )
    )

    assert result.name == "helper"
    assert result.summary == "Intro paragraph."
    assert result.resource_count == 2
    assert result.section_count == 3