"""Skill 数据目录与 ZIP/文档预算常量。

所有限制以模块级常量固定，测试直接引用它们；Skill 数据目录只来自服务端
解析（模块位置或 LIGHTCODE_SKILLS_PATH），绝不接受浏览器提供的路径。
"""

import os
from pathlib import Path

MAX_SKILL_PACKAGE_BYTES = 5 * 1024 * 1024
MAX_SKILL_ENTRIES = 64
MAX_SKILL_EXTRACTED_BYTES = 10 * 1024 * 1024
MAX_SKILL_ENTRY_BYTES = 2 * 1024 * 1024
MAX_SKILL_DOCUMENT_BYTES = 256 * 1024
MAX_SKILL_PATH_DEPTH = 4
ALLOWED_SKILL_SUFFIXES = frozenset({".md", ".txt", ".json", ".png", ".jpg", ".jpeg", ".webp", ".svg"})

# 隐藏的敏感名称/扩展名：与 WorkspaceGuard 策略一致的拒绝名单，防止技能包
# 把 .env/.git/私钥等文件带入受控存储目录。匹配时对路径段与文件名逐段
# casefold 比较。
SENSITIVE_SKILL_SEGMENTS: tuple[str, ...] = (
    ".env",
    ".git",
)
SENSITIVE_SKILL_STEM_PREFIXES: tuple[str, ...] = (
    "id_rsa",
    "credentials",
    "secrets",
)
SENSITIVE_SKILL_SUFFIXES: tuple[str, ...] = (
    ".pem",
    ".key",
)


def skill_root() -> Path:
    configured = os.getenv("LIGHTCODE_SKILLS_PATH", "").strip()
    backend_root = Path(__file__).resolve().parent.parent.parent
    root = Path(configured) if configured else backend_root / "data" / "skills"
    if configured and not root.is_absolute():
        root = backend_root / root
    return root.resolve()