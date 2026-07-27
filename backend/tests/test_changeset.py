from __future__ import annotations

import pytest

from app.services.changeset import (
    APPEND_MARKER_TEMPLATE,
    generate_change_set,
    sha256_text,
)


def _gen(base_text: str, task_id: str = "task-1"):
    return generate_change_set(
        logical_relative_path="notes.txt",
        base_text=base_text,
        task_id=task_id,
        policy_version="phase1-single-text-file",
        template_id=APPEND_MARKER_TEMPLATE,
    )


def test_deterministic_for_same_inputs() -> None:
    a = _gen("hello\n")
    b = _gen("hello\n")
    assert a.proposed_sha256 == b.proposed_sha256
    assert a.diff_hash == b.diff_hash


def test_diff_hash_changes_with_task_id() -> None:
    a = _gen("hello\n", "task-1")
    b = _gen("hello\n", "task-2")
    # different task_id => different appended marker => different proposed hash
    assert a.proposed_sha256 != b.proposed_sha256
    assert a.diff_hash != b.diff_hash


def test_base_sha_matches_input() -> None:
    cs = _gen("hello\n")
    assert cs.base_sha256 == sha256_text("hello\n")


def test_append_adds_one_line() -> None:
    cs = _gen("line one\nline two\n")
    assert cs.additions == 1
    assert cs.deletions == 0
    assert cs.after[-1].startswith("LightCode Phase 1 change marker")


def test_appends_newline_when_missing() -> None:
    cs = _gen("no trailing newline")
    # proposed text must normalise to have the base line then the marker line
    assert cs.proposed_text.startswith("no trailing newline\n")
    assert cs.proposed_text.endswith("\n")


def test_unsupported_template_rejected() -> None:
    with pytest.raises(ValueError):
        generate_change_set(
            logical_relative_path="notes.txt",
            base_text="x\n",
            task_id="t",
            policy_version="p",
            template_id="delete-everything",
        )
