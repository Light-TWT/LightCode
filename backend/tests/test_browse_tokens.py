"""Unit tests for the opaque, HMAC-signed browse tokens.

The browser must never construct or submit a free-form relative path. These
tests prove the token is verifiable, tamper-evident, bound to workspace +
operation, and short-lived.
"""

import base64
import json

import pytest

from app.schemas.errors import BROWSE_TOKEN_EXPIRED, BROWSE_TOKEN_INVALID, Phase1Error
from app.services.browse_tokens import issue, verify


def test_issue_and_verify_roundtrip() -> None:
    tok = issue("ws1", "read", "a/b.txt")
    assert verify(tok, "ws1", "read") == "a/b.txt"


def test_verify_wrong_workspace_rejected() -> None:
    tok = issue("ws1", "read", "a/b.txt")
    with pytest.raises(Phase1Error) as exc:
        verify(tok, "ws2", "read")
    assert exc.value.code == BROWSE_TOKEN_INVALID


def test_verify_wrong_operation_rejected() -> None:
    tok = issue("ws1", "list", "a")
    with pytest.raises(Phase1Error) as exc:
        verify(tok, "ws1", "read")
    assert exc.value.code == BROWSE_TOKEN_INVALID


def test_verify_malformed_token_rejected() -> None:
    with pytest.raises(Phase1Error) as exc:
        verify("not-a-real-token", "ws1", "read")
    assert exc.value.code == BROWSE_TOKEN_INVALID


def test_verify_tampered_payload_rejected(monkeypatch) -> None:
    # Flip a field in the signed payload; the HMAC must no longer match.
    tok = issue("ws1", "read", "a/b.txt")
    body_b64, sig_b64 = tok.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body_b64))
    payload["p"] = "../../etc/passwd"
    new_body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).decode()
    with pytest.raises(Phase1Error) as exc:
        verify(f"{new_body}.{sig_b64}", "ws1", "read")
    assert exc.value.code == BROWSE_TOKEN_INVALID


def test_verify_expired_token_rejected(monkeypatch) -> None:
    monkeypatch.setattr("app.services.browse_tokens._TOKEN_TTL_SECONDS", -1)
    tok = issue("ws1", "read", "a/b.txt")
    with pytest.raises(Phase1Error) as exc:
        verify(tok, "ws1", "read")
    assert exc.value.code == BROWSE_TOKEN_EXPIRED
