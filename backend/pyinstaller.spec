# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LightCode desktop sidecar.

Produces a single ``lightcode-sidecar.exe`` that FastAPI + Uvicorn inside the
same process. Test assets, documentation, and repository configuration are
excluded from the collection.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import PyInstaller.__main__  # noqa: F401  # ensure the hook loader is available

# Ensure the project root is on sys.path so that ``app`` can be imported.
_HERE = Path(SPECPATH).resolve()
sys.path.insert(0, str(_HERE))

# ---------------------------------------------------------------------------
# Block list – exclude everything that is not needed at runtime.
# ---------------------------------------------------------------------------
# NOTE: do NOT add distutils to the block list — PyInstaller 6.x on Python 3.13
# has a pre-safe-import hook that aliases the already-removed stdlib distutils
# module, and excluding it at the same time produces a ValueError.
#
# The following are excluded because the backend optionally imports huge data
# stacks (torch / scipy / cv2 / pandas) that the sidecar never uses at runtime.
# They are pulled in transitively via langchain/langgraph and would otherwise
# inflate the onefile artifact by gigabytes.
_EXCLUDES: list[str] = [
    "tkinter",
    "unittest",
    "setuptools",
    "pdb",
    "pygments",
    "pytest",
    "test",
    "tests",
    "torch",
    "torchvision",
    "torchaudio",
    "onnxruntime",
    "scipy",
    "numpy.random.mtrand",
    "cv2",
    "pandas",
    "bilibili_api",
    "faiss",
    "matplotlib",
    "sklearn",
    "sympy",
    "transformers",
    "tokenizers",
    "sentence_transformers",
    "datasets",
    "tensorflow",
    "keras",
    "jax",
    "PIL.ImageShow",
    "pyspark",
    "impala",
    "pymysql",
    "pymongo",
    "psycopg2",
    "cassandra",
    "redis",
    "duckdb",
    "lancedb",
    "chromadb",
    "pdfplumber",
    "pypdf",
    "docx",
    "openpyxl",
    "PIL",
    "IPython",
    "jupyter",
    "notebook",
    "nltk",
    "spacy",
    "jieba",
    "youtube_search",
    "wikipedia",
    "arxiv",
    "huggingface_hub",
]

# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
a = Analysis(
    ["sidecar_entry.py"],
    pathex=[str(_HERE)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan.on",
        "app",
        "app.api",
        "app.config",
        "app.db",
        "app.security",
        "app.services",
        "app.schemas",
        "app.workspaces",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="lightcode-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)