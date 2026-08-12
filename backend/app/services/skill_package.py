"""纯函数、fail-closed 的 Skill ZIP 包识别。

设计约束（docs/superpowers/specs/2026-08-12-skill-management-design.md §5）：
- 只使用标准库 ``zipfile``/``hashlib``/``pathlib``；不信任文件名、声明大小
  或 MIME；不调用 ``extractall()``。
- 所有拒绝路径抛 ``Phase1Error`` 稳定错误码，异常文本不含 ZIP 路径、条目名、
  解压目录或堆栈。
- 本模块不接触数据库、不写非调用方所有的目录：``extract_skill_package``
  只把 ``package.zip`` 与 ``SKILL.md`` 写入调用方提供的空临时目录。
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.config.skills import (
    ALLOWED_SKILL_SUFFIXES,
    MAX_SKILL_DOCUMENT_BYTES,
    MAX_SKILL_ENTRIES,
    MAX_SKILL_ENTRY_BYTES,
    MAX_SKILL_EXTRACTED_BYTES,
    MAX_SKILL_PACKAGE_BYTES,
    MAX_SKILL_PATH_DEPTH,
    SENSITIVE_SKILL_SEGMENTS,
    SENSITIVE_SKILL_STEM_PREFIXES,
    SENSITIVE_SKILL_SUFFIXES,
)
from app.schemas.errors import (
    Phase1Error,
    SKILL_DOCUMENT_DUPLICATED,
    SKILL_DOCUMENT_INVALID,
    SKILL_DOCUMENT_MISSING,
    SKILL_PACKAGE_ENTRY_DENIED,
    SKILL_PACKAGE_INVALID,
    SKILL_PACKAGE_SIZE_DENIED,
    SKILL_PACKAGE_STRUCTURE_DENIED,
)

_DOCUMENT_NAME = "SKILL.md"
_HEADING_MAX = 80
_SUMMARY_MAX = 240
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")
_SECTION_RE = re.compile(r"^#{2,6}\s+\S")
_INLINE_MARKDOWN_RE = re.compile(r"[`*_\]\[()#>\-!|]")


@dataclass(frozen=True)
class InspectedSkillPackage:
    name: str
    summary: str
    document: str
    document_sha256: str
    package_sha256: str
    package_bytes: int
    document_bytes: int
    resource_count: int
    section_count: int


def _reject(code: str) -> Phase1Error:
    # 统一固定文案，绝不携带路径/条目名/异常文本。
    messages = {
        SKILL_PACKAGE_SIZE_DENIED: "技能包超出大小限制。",
        SKILL_PACKAGE_INVALID: "技能包无法识别，请检查压缩文件。",
        SKILL_PACKAGE_STRUCTURE_DENIED: "技能包结构不符合要求。",
        SKILL_PACKAGE_ENTRY_DENIED: "技能包包含不允许的条目。",
        SKILL_DOCUMENT_MISSING: "技能包中未找到 SKILL.md。",
        SKILL_DOCUMENT_DUPLICATED: "技能包包含多个 SKILL.md。",
        SKILL_DOCUMENT_INVALID: "SKILL.md 格式不符合要求。",
    }
    return Phase1Error(code, messages.get(code, "技能包不被接受。"))


def _deny(code: str) -> Phase1Error:
    return _reject(code)


def _validate_entry_path(name: str) -> list[str] | None:
    """返回规范的路径段列表；非法路径返回 None（拒绝不区分原因）。"""
    if not name or "\x00" in name:
        return None
    normalized = name.replace("\\", "/")
    try:
        parts = PurePosixPath(normalized).parts
    except ValueError:
        return None
    if not parts or any(segment in ("", ".", "..") for segment in parts):
        return None
    if normalized.startswith("/") or PurePosixPath(normalized).is_absolute():
        return None
    # 驱动器（C:/...）与 UNC（//host/share/...）路径。
    if re.match(r"^[A-Za-z]:", normalized) or normalized.startswith("//"):
        return None
    if len(parts) > MAX_SKILL_PATH_DEPTH:
        return None
    return list(parts)


def _is_sensitive(name: str) -> bool:
    casefold = name.casefold()
    if any(segment.casefold() in SENSITIVE_SKILL_SEGMENTS for segment in casefold.split("/")):
        return True
    stem = PurePosixPath(casefold).name
    if not stem or stem.endswith("/"):
        return False
    if any(stem.startswith(prefix) for prefix in SENSITIVE_SKILL_STEM_PREFIXES):
        return True
    return any(stem.endswith(suffix) for suffix in SENSITIVE_SKILL_SUFFIXES)


def _allowed_file_type(info: zipfile.ZipInfo) -> bool:
    """外部属性中的 Unix 文件类型位：只允许普通文件或目录。

    ``zipfile`` 在 Windows 上默认写 ``0o600 << 16``（仅权限位、无类型位），
    视为普通条目放行；显式声明为符号链接/设备（``0o120000`` 等）一律拒绝。
    """
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = mode & 0o170000
    if file_type == 0:
        return True
    return file_type in (0o100000, 0o040000)


def _parse_document(raw: bytes) -> tuple[str, str, int]:
    """返回 (名称, 摘要, 章节数)；文档不合格抛 SKILL_DOCUMENT_INVALID。"""
    try:
        document = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _deny(SKILL_DOCUMENT_INVALID) from None

    lines = document.splitlines()
    if not any(line.strip() for line in lines):
        raise _deny(SKILL_DOCUMENT_INVALID)

    name: str | None = None
    paragraphs: list[str] = []
    section_count = 0
    current: list[str] = []

    def flush() -> None:
        if current and current[0].strip() and not current[0].lstrip().startswith("#"):
            paragraphs.append("\n".join(current).strip())
        current.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _SECTION_RE.match(stripped):
            section_count += 1
            flush()
            continue
        match = _TITLE_RE.match(stripped)
        if match and name is None and not stripped.startswith("##"):
            candidate = match.group(1).strip()
            if candidate and len(candidate) <= _HEADING_MAX and candidate.isprintable():
                name = unicodedata.normalize("NFC", candidate)
            flush()
            continue
        current.append(line)

    flush()

    if name is None:
        raise _deny(SKILL_DOCUMENT_INVALID)

    summary = ""
    for paragraph in paragraphs:
        cleaned = _INLINE_MARKDOWN_RE.sub("", paragraph)
        summary = " ".join(cleaned.split())
        if summary:
            break
    summary = unicodedata.normalize("NFC", summary)[:_SUMMARY_MAX]
    return name, summary, section_count


def _validate_zip_infos(
    infos: list[zipfile.ZipInfo],
) -> tuple[zipfile.ZipInfo | None, int]:
    """逐项校验中央目录；返回 (SKILL.md 条目, 资源数量)。

    校验顺序固定：加密 → 文件类型 → 路径 → 重复 → 敏感名 → 预算。任何
    一项不合格立即抛稳定错误码，绝不拼接条目名或声明值。
    """
    if len(infos) > MAX_SKILL_ENTRIES:
        raise _deny(SKILL_PACKAGE_STRUCTURE_DENIED)

    normalized_seen: set[str] = set()
    document_info: zipfile.ZipInfo | None = None
    resource_count = 0
    total_extracted = 0

    for info in infos:
        if info.flag_bits & 0x1:
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)
        if not _allowed_file_type(info):
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)
        parts = _validate_entry_path(info.filename)
        if parts is None:
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)
        depth = len(parts)
        normalized_path = posixpath.normpath("/".join(parts))
        if normalized_path in normalized_seen:
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)
        normalized_seen.add(normalized_path)
        if _is_sensitive(info.filename):
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)

        is_directory = info.filename.endswith("/") or (
            (info.external_attr >> 16) & 0o170000 == 0o040000
        )
        if is_directory:
            continue

        if info.file_size > MAX_SKILL_ENTRY_BYTES:
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)
        total_extracted += info.file_size
        if total_extracted > MAX_SKILL_EXTRACTED_BYTES:
            raise _deny(SKILL_PACKAGE_STRUCTURE_DENIED)

        suffix = PurePosixPath(info.filename).suffix.casefold()
        if PurePosixPath(info.filename).name.casefold() == _DOCUMENT_NAME.casefold() and depth <= 2:
            if document_info is not None:
                raise _deny(SKILL_DOCUMENT_DUPLICATED)
            document_info = info
            continue
        if suffix not in ALLOWED_SKILL_SUFFIXES:
            raise _deny(SKILL_PACKAGE_ENTRY_DENIED)
        resource_count += 1

    return document_info, resource_count


def inspect_skill_package_info_only(
    infos: list[zipfile.ZipInfo], package_bytes: bytes
) -> zipfile.ZipInfo | None:
    """仅做中央目录校验的注入点（测试确定性构造加密等标志场景）。

    不读取任何条目内容；``package_bytes`` 保留仅用于保持调用形态一致。
    """
    document_info, _ = _validate_zip_infos(infos)
    return document_info


def inspect_skill_package(package_bytes: bytes) -> InspectedSkillPackage:
    """校验 ZIP 中央目录与全部条目，提取文档元数据；不落盘。"""
    if not package_bytes:
        raise _deny(SKILL_PACKAGE_INVALID)
    if len(package_bytes) > MAX_SKILL_PACKAGE_BYTES:
        raise _deny(SKILL_PACKAGE_SIZE_DENIED)

    try:
        archive = zipfile.ZipFile(io.BytesIO(package_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError):
        raise _deny(SKILL_PACKAGE_INVALID) from None

    try:
        infos = archive.infolist()
    except (zipfile.BadZipFile, RuntimeError, OSError):
        raise _deny(SKILL_PACKAGE_INVALID) from None

    if len(infos) > MAX_SKILL_ENTRIES:
        raise _deny(SKILL_PACKAGE_STRUCTURE_DENIED)

    document_info, resource_count = _validate_zip_infos(infos)

    if document_info is None:
        raise _deny(SKILL_DOCUMENT_MISSING)

    try:
        raw = archive.read(document_info)
    except (zipfile.BadZipFile, RuntimeError, OSError, KeyError):
        raise _deny(SKILL_DOCUMENT_INVALID) from None
    if len(raw) > MAX_SKILL_DOCUMENT_BYTES:
        raise _deny(SKILL_DOCUMENT_INVALID)

    name, summary, section_count = _parse_document(raw)

    return InspectedSkillPackage(
        name=name,
        summary=summary,
        document=raw.decode("utf-8"),
        document_sha256=hashlib.sha256(raw).hexdigest(),
        package_sha256=hashlib.sha256(package_bytes).hexdigest(),
        package_bytes=len(package_bytes),
        document_bytes=len(raw),
        resource_count=resource_count,
        section_count=section_count,
    )


def extract_skill_package(package_bytes: bytes, destination: Path) -> InspectedSkillPackage:
    """先识别再落盘：仅写 ``package.zip`` 与 ``SKILL.md`` 两个文件。

    ``destination`` 必须由调用方创建为空目录；两个文件用排他创建模式写入，
    绝不把 ZIP 内其他资源/条目名带到磁盘。
    """
    inspected = inspect_skill_package(package_bytes)
    package_path = destination / "package.zip"
    with package_path.open("xb") as handle:
        handle.write(package_bytes)
    document_path = destination / "SKILL.md"
    with document_path.open("xb") as handle:
        handle.write(inspected.document.encode("utf-8"))
    return inspected