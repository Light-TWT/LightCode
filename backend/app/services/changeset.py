"""Deterministic ChangeSet generation for Phase 1.

The only supported template in Phase 1 is `append-marker`: it appends a single,
server-controlled marker line to an existing UTF-8 text file. The transform is a
pure function of (base_text, task_id), which guarantees that `proposedSha256` and
`diffHash` are reproducible and that the browser can never influence the content
that will be written.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

APPEND_MARKER_TEMPLATE = "append-marker"
MARKER_TEXT = "LightCode Phase 1 change marker :: {task_id}"


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _apply_append_marker(base_text: str, task_id: str) -> str:
    """Append a single deterministic marker line.

    Normalises the file so it ends with exactly one newline before the marker,
    then appends the marker terminated by a newline. This keeps the transform
    idempotent-in-shape and independent of whether the source ended with a
    trailing newline.
    """
    marker = MARKER_TEXT.format(task_id=task_id)
    body = base_text
    if body and not body.endswith("\n"):
        body = body + "\n"
    return body + marker + "\n"


@dataclass(frozen=True)
class GeneratedChangeSet:
    logical_relative_path: str
    policy_version: str
    base_text: str
    proposed_text: str
    base_sha256: str
    proposed_sha256: str
    diff_hash: str
    additions: int
    deletions: int
    before: list[str]
    after: list[str]


def generate_change_set(
    *,
    logical_relative_path: str,
    base_text: str,
    task_id: str,
    policy_version: str,
    template_id: str = APPEND_MARKER_TEMPLATE,
) -> GeneratedChangeSet:
    """Produce a deterministic ChangeSet for a registered target file.

    Raises ValueError for unsupported templates so callers can surface a stable
    error instead of silently doing nothing.
    """
    if template_id != APPEND_MARKER_TEMPLATE:
        raise ValueError(f"unsupported template: {template_id}")

    proposed_text = _apply_append_marker(base_text, task_id)
    base_sha = sha256_text(base_text)
    proposed_sha = sha256_text(proposed_text)
    # diffHash binds base, proposed and the logical path so an approval cannot be
    # replayed against a different file or a different revision of the content.
    diff_material = f"{base_sha}|{proposed_sha}|{logical_relative_path}"
    diff_hash = "sha256:" + hashlib.sha256(diff_material.encode("utf-8")).hexdigest()

    before = base_text.splitlines()
    after = proposed_text.splitlines()
    additions = max(0, len(after) - len(before))
    deletions = max(0, len(before) - len(after))

    return GeneratedChangeSet(
        logical_relative_path=logical_relative_path,
        policy_version=policy_version,
        base_text=base_text,
        proposed_text=proposed_text,
        base_sha256=base_sha,
        proposed_sha256=proposed_sha,
        diff_hash=diff_hash,
        additions=additions,
        deletions=deletions,
        before=before,
        after=after,
    )
