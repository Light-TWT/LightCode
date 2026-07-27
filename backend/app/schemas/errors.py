from __future__ import annotations

from fastapi import HTTPException


class Phase1Error(Exception):
    """Domain error carrying a stable machine code and HTTP status.

    Routes map this to a JSON error body that never includes the real root
    path, internal stack, secrets or policy implementation details.
    """

    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# Stable error codes (from phase1-safety-contract.md)
WORKSPACE_NOT_REGISTERED = "WORKSPACE_NOT_REGISTERED"
WORKSPACE_DISABLED = "WORKSPACE_DISABLED"
CHANGESET_NOT_ACTIVE = "CHANGESET_NOT_ACTIVE"
CHANGESET_EXPIRED = "CHANGESET_EXPIRED"
CHANGESET_REVISION_MISMATCH = "CHANGESET_REVISION_MISMATCH"
APPROVAL_ALREADY_PROCESSED = "APPROVAL_ALREADY_PROCESSED"
INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
STALE_BASE = "STALE_BASE"
PATH_POLICY_DENIED = "PATH_POLICY_DENIED"
SECRET_FILE_DENIED = "SECRET_FILE_DENIED"
SYMLINK_DENIED = "SYMLINK_DENIED"
FILE_TYPE_DENIED = "FILE_TYPE_DENIED"
FILE_SIZE_DENIED = "FILE_SIZE_DENIED"
APPLY_OUTCOME_UNKNOWN = "APPLY_OUTCOME_UNKNOWN"
USER_REJECTED = "USER_REJECTED"
VERIFICATION_FAILED = "VERIFICATION_FAILED"


def to_http_error(exc: Phase1Error) -> HTTPException:
    return HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.message},
    )
