"""Unified error code system (PRD §31: error code, message, retryable, task id, provider id, safe details)."""
from __future__ import annotations

from typing import Any

# Error code registry: code -> (default retryable, description)
ERROR_CODES: dict[str, tuple[bool, str]] = {
    # requirement / search
    "REQUIREMENT_PARSE_FAILED": (False, "natural language requirement could not be parsed"),
    "REQUIREMENT_CONFLICT": (False, "requirement constraints conflict"),
    "PROVIDER_TIMEOUT": (True, "provider did not respond in time"),
    "PROVIDER_UNAVAILABLE": (True, "provider endpoint unreachable"),
    "PROVIDER_HTTP_ERROR": (True, "provider returned an HTTP error"),
    "PROVIDER_SCHEMA_CHANGED": (True, "provider response schema unexpected"),
    "PROVIDER_RATE_LIMITED": (True, "provider rate limited the request"),
    "PROVIDER_CAPABILITY_MISSING": (False, "provider does not declare required capability"),
    "PROVIDER_DISABLED": (False, "provider disabled by configuration"),
    "SEARCH_CANCELLED": (False, "search cancelled by user"),
    # download / content
    "DOWNLOAD_JOB_REQUIRED": (False, "downloads must be attached to a DownloadJob"),
    "DOWNLOAD_FAILED": (True, "download failed"),
    "DOWNLOAD_CANCELLED": (False, "download cancelled"),
    "DOWNLOAD_TOO_LARGE": (False, "download exceeds configured size limit"),
    "INVALID_DOWNLOAD_CONTENT": (False, "downloaded content is not the claimed data format"),
    "CHECKSUM_MISMATCH": (False, "checksum mismatch after download"),
    "ARCHIVE_UNSAFE": (False, "archive rejected by safe-extraction policy"),
    "RAW_WRITE_BLOCKED": (False, "attempt to write into immutable raw/ was blocked"),
    "PARSE_UNSUPPORTED_FORMAT": (False, "format has no parser"),
    "PARSE_FAILED": (False, "existing parser failed on file"),
    # auth / vault
    "VAULT_UNAVAILABLE": (False, "secure vault backend not available"),
    "INVALID_CREDENTIALS": (False, "login rejected credentials"),
    "LOGIN_FAILED": (True, "login did not succeed"),
    "SESSION_EXPIRED": (True, "stored session no longer valid"),
    "CAPTCHA_REQUIRED": (False, "CAPTCHA encountered; user intervention required"),
    "MFA_REQUIRED": (False, "MFA/OTP encountered; user intervention required"),
    "USER_INTERVENTION_REQUIRED": (False, "user must complete a protected step"),
    "REGISTRATION_BLOCKED": (False, "auto registration not allowed or blocked"),
    "PASSWORD_RULE_FAILED": (False, "generated/reported password violates provider rules"),
    "DUPLICATE_ACCOUNT": (False, "provider reports account already exists"),
    "VERIFY_EMAIL_REQUIRED": (False, "provider requires email verification"),
    # synthesis
    "JOIN_CARDINALITY_BLOCKED": (False, "join blocked by cardinality policy"),
    "JOIN_KEY_MISSING": (False, "join keys missing or not unique as declared"),
    "SEMANTIC_CONFLICT": (False, "variable semantics conflict; merge refused"),
    "ENTITY_UNRESOLVED": (True, "entity could not be resolved confidently"),
    "TIME_FREQUENCY_CONFLICT": (True, "frequency mismatch requires explicit alignment"),
    "BUILD_FAILED": (True, "build step failed"),
    "BUILD_CANCELLED": (False, "build cancelled"),
    # generic
    "INTERNAL_ERROR": (True, "unexpected internal error"),
    "NOT_FOUND": (False, "requested object not found"),
    "STATE_INVALID": (False, "operation not allowed in current state"),
}


class MetisError(Exception):
    """All business errors carry code/retryable/context; never swallow silently."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        retryable: bool | None = None,
        task_id: str | None = None,
        provider_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        default_retryable, desc = ERROR_CODES.get(code, (True, "unregistered error code"))
        self.code = code
        self.message = message or desc
        self.retryable = default_retryable if retryable is None else retryable
        self.task_id = task_id
        self.provider_id = provider_id
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "details": self.details,
        }
