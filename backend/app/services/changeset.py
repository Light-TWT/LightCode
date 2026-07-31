"""Deterministic ChangeSet generation for Phase 1 and Phase 2 / WP6.

Phase 1 (``append-marker``): appends a single, server-controlled marker line to
an existing UTF-8 text file. The transform is a pure function of
(base_text, task_id), which guarantees that ``proposedSha256`` and ``diffHash``
are reproducible and that the browser can never influence the content written.

Phase 2 / WP6 (``build_model_change_set``): applies a model-proposed
``candidate_edit_intent`` (exact, *unique* text replacements) to the current
file under server control. The model only supplies the old/new text and a
base hash; the server independently recomputes the new content, its hash and the
diff, so a ChangeSet can never be forged client-side.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.schemas.errors import (
    FILE_TYPE_DENIED,
    MODEL_BUDGET_EXCEEDED,
    MODEL_EDIT_INVALID,
    Phase1Error,
)
from app.security.policy import MAX_DIFF_LINES, MAX_FILE_BYTES

APPEND_MARKER_TEMPLATE = "append-marker"
MARKER_TEXT = "LightCode Phase 1 change marker :: {task_id}"

# A candidate intent is a bounded set of precise edits, not a free patch.
_MAX_MODEL_EDITS = 50


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


def _replace_unique(text: str, expected: str, replacement: str) -> str:
    """Replace the single occurrence of ``expected`` with ``replacement``.

    Fail-closed: an empty ``expected`` or anything other than exactly one
    occurrence is rejected, because the model may only propose *exact, unique*
    text replacements — never a regex, a line range, or an ambiguous anchor.
    """
    if not expected:
        raise Phase1Error(MODEL_EDIT_INVALID, "candidate edit has empty expected text")
    count = text.count(expected)
    if count != 1:
        raise Phase1Error(
            MODEL_EDIT_INVALID,
            "candidate edit is not an exact unique replacement "
            f"(found {count} occurrences)",
        )
    index = text.index(expected)
    return text[:index] + replacement + text[index + len(expected):]


def apply_candidate_edits(base_text: str, edits: list) -> str:
    """Apply a bounded list of exact, unique text replacements to ``base_text``.

    Returns the proposed content. Raises :class:`Phase1Error` for any malformed,
    non-unique, oversized or over-budget intent.
    """
    if not edits:
        raise Phase1Error(MODEL_EDIT_INVALID, "candidate edit intent has no edits")
    if len(edits) > _MAX_MODEL_EDITS:
        raise Phase1Error(MODEL_EDIT_INVALID, "candidate edit intent exceeds edit limit")

    text = base_text
    for edit in edits:
        expected = edit.expectedText if hasattr(edit, "expectedText") else edit.get("expectedText")
        replacement = (
            edit.replacementText if hasattr(edit, "replacementText") else edit.get("replacementText")
        )
        if len(replacement) > MAX_FILE_BYTES:
            raise Phase1Error(
                MODEL_BUDGET_EXCEEDED, "candidate edit replacement exceeds file size budget"
            )
        text = _replace_unique(text, expected, replacement)
    if len(text) > MAX_FILE_BYTES:
        raise Phase1Error(
            MODEL_BUDGET_EXCEEDED, "proposed file exceeds size budget"
        )
    return text


def build_model_change_set(
    *,
    logical_relative_path: str,
    base_text: str,
    edits: list,
    task_id: str,
    policy_version: str,
) -> GeneratedChangeSet:
    """Build an immutable ChangeSet from a model-proposed candidate intent.

    The server independently applies the edits, recomputes the proposed content,
    its hash and the diff, and enforces the diff-line budget. The model never
    supplies the resulting bytes, only the old/new text and a base hash.
    """
    proposed_text = apply_candidate_edits(base_text, edits)

    base_sha = sha256_text(base_text)
    proposed_sha = sha256_text(proposed_text)
    diff_material = f"{base_sha}|{proposed_sha}|{logical_relative_path}"
    diff_hash = "sha256:" + hashlib.sha256(diff_material.encode("utf-8")).hexdigest()

    before = base_text.splitlines()
    after = proposed_text.splitlines()
    additions = max(0, len(after) - len(before))
    deletions = max(0, len(before) - len(after))
    if additions + deletions > MAX_DIFF_LINES:
        raise Phase1Error(
            FILE_TYPE_DENIED, "candidate change set exceeds the maximum diff line limit"
        )

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
