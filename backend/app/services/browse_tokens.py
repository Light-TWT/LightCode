"""Short-lived, opaque browse tokens for the Phase 1 registered-workspace UX.

The browser must never submit a free-form relative path. Instead the server
issues signed tokens that bind ``(workspace_id, operation, relative_path)`` and
a short expiry. The browser only ever echoes a token back; the server verifies
the HMAC signature, TTL, workspace and operation before resolving the path via
``WorkspaceGuard``. This keeps path construction server-authoritative and
prevents path traversal / sensitive-path enumeration from the client.

Tokens are *opaque*: the payload is base64url-encoded and HMAC-signed, so a
client cannot forge a path, change the workspace, or extend the operation. The
secret is process-local (or ``LIGHTCODE_BROWSE_TOKEN_SECRET`` in tests); it is
not a user credential and never leaves the server.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Literal

from app.schemas.errors import BROWSE_TOKEN_EXPIRED, BROWSE_TOKEN_INVALID, Phase1Error

BrowseOp = Literal["list", "read", "search"]

_TOKEN_TTL_SECONDS = int(os.environ.get("LIGHTCODE_BROWSE_TOKEN_TTL_SECONDS", "30"))

_secret_cache: bytes | None = None


def _secret() -> bytes:
    global _secret_cache
    if _secret_cache is None:
        env = os.environ.get("LIGHTCODE_BROWSE_TOKEN_SECRET")
        _secret_cache = env.encode("utf-8") if env else os.urandom(32)
    return _secret_cache


def issue(workspace_id: str, operation: BrowseOp, relative_path: str) -> str:
    """Mint a signed, short-TTL browse token for one operation on one path."""
    exp = int(time.time()) + _TOKEN_TTL_SECONDS
    payload = {"ws": workspace_id, "op": operation, "p": relative_path, "exp": exp}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_b64 = base64.urlsafe_b64encode(body).decode("ascii")
    sig = hmac.new(_secret(), body_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii")
    return f"{body_b64}.{sig_b64}"


def verify(token: str, expected_workspace_id: str, expected_operation: BrowseOp) -> str:
    """Return the bound relative_path, or raise a stable ``Phase1Error``.

    Fails closed on any malformed token, signature mismatch, workspace/operation
    mismatch, or expiry. The relative_path is only ever revealed to the server
    after a verified token is presented.
    """
    if not token or "." not in token:
        raise Phase1Error(BROWSE_TOKEN_INVALID, "malformed browse token")
    body_b64, _, sig_b64 = token.partition(".")
    expected_sig = hmac.new(_secret(), body_b64.encode("ascii"), hashlib.sha256).digest()
    try:
        provided_sig = base64.urlsafe_b64decode(sig_b64)
    except Exception:  # noqa: BLE001
        raise Phase1Error(BROWSE_TOKEN_INVALID, "malformed browse token signature") from None
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise Phase1Error(BROWSE_TOKEN_INVALID, "browse token signature mismatch")
    try:
        payload = json.loads(base64.urlsafe_b64decode(body_b64))
    except Exception:  # noqa: BLE001
        raise Phase1Error(BROWSE_TOKEN_INVALID, "malformed browse token payload") from None
    if payload.get("ws") != expected_workspace_id:
        raise Phase1Error(BROWSE_TOKEN_INVALID, "browse token workspace mismatch")
    if payload.get("op") != expected_operation:
        raise Phase1Error(BROWSE_TOKEN_INVALID, "browse token operation mismatch")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise Phase1Error(BROWSE_TOKEN_EXPIRED, "browse token expired")
    return str(payload.get("p", ""))
