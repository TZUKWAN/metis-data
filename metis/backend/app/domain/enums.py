"""Domain enums & state machines (PRD §29). Transitions are enforced, persisted, and recoverable."""
from __future__ import annotations

from enum import IntEnum, StrEnum


class StrEnumU(StrEnum):
    def __str__(self) -> str:  # pragma: no cover
        return self.value


# ---------------- Search ----------------
class SearchRunStatus(StrEnumU):
    CREATED = "CREATED"
    REQUIREMENT_PARSED = "REQUIREMENT_PARSED"
    PROVIDERS_SELECTED = "PROVIDERS_SELECTED"
    SEARCHING = "SEARCHING"
    CANDIDATES_NORMALIZED = "CANDIDATES_NORMALIZED"
    CANDIDATES_EVALUATED = "CANDIDATES_EVALUATED"
    WAITING_USER_SELECTION = "WAITING_USER_SELECTION"
    AUTO_SELECTED = "AUTO_SELECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ProviderTaskStatus(StrEnumU):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# ---------------- Access / acquisition ----------------
class AccessState(StrEnumU):
    ACCESS_CHECK = "ACCESS_CHECK"
    PUBLIC_DOWNLOAD = "PUBLIC_DOWNLOAD"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_CHECK = "SESSION_CHECK"
    LOGIN = "LOGIN"
    REGISTER = "REGISTER"
    USER_INTERVENTION = "USER_INTERVENTION"
    DOWNLOADING = "DOWNLOADING"
    VERIFYING = "VERIFYING"
    PROFILING = "PROFILING"
    ACQUIRED = "ACQUIRED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AccessMode(StrEnumU):
    PUBLIC_ANONYMOUS_API = "PUBLIC_ANONYMOUS_API"
    PUBLIC_ANONYMOUS_HTTP = "PUBLIC_ANONYMOUS_HTTP"
    EXISTING_SESSION = "EXISTING_SESSION"
    EXISTING_ACCOUNT = "EXISTING_ACCOUNT"
    AUTO_REGISTRATION = "AUTO_REGISTRATION"
    USER_INTERVENTION = "USER_INTERVENTION"
    UNKNOWN = "UNKNOWN"


# ---------------- Download ----------------
class DownloadJobStatus(StrEnumU):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INVALID_CONTENT = "INVALID_CONTENT"


# ---------------- Build ----------------
class BuildStatus(StrEnumU):
    BUILD_CREATED = "BUILD_CREATED"
    INPUTS_READY = "INPUTS_READY"
    SCHEMA_ANALYSIS = "SCHEMA_ANALYSIS"
    SEMANTIC_ALIGNMENT = "SEMANTIC_ALIGNMENT"
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"
    TEMPORAL_ALIGNMENT = "TEMPORAL_ALIGNMENT"
    TRANSFORM = "TRANSFORM"
    JOIN = "JOIN"
    QA = "QA"
    PROVENANCE_FINALIZE = "PROVENANCE_FINALIZE"
    EXPORT = "EXPORT"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# ---------------- Browser ----------------
class BrowserOwner(StrEnumU):
    AGENT = "agent"
    HUMAN = "human"


class BrowserSessionState(StrEnumU):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_USER = "WAITING_USER"
    TAKEN_OVER = "TAKEN_OVER"
    CRASHED = "CRASHED"
    CLOSED = "CLOSED"


class InterventionKind(StrEnumU):
    CAPTCHA = "CAPTCHA"
    MFA = "MFA"
    PHONE_OTP = "PHONE_OTP"
    INSTITUTION_VERIFICATION = "INSTITUTION_VERIFICATION"
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    RESTRICTED_DATA_AGREEMENT = "RESTRICTED_DATA_AGREEMENT"
    PAYMENT = "PAYMENT"
    HIGH_RISK_TERMS = "HIGH_RISK_TERMS"


# ---------------- Accounts ----------------
class AccountStatusKind(StrEnumU):
    NONE = "NONE"
    CREDENTIALS_STORED = "CREDENTIALS_STORED"
    SESSION_VALID = "SESSION_VALID"
    LOGIN_FAILED = "LOGIN_FAILED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    PENDING_EMAIL_VERIFICATION = "PENDING_EMAIL_VERIFICATION"
    FULLY_ACTIVE = "FULLY_ACTIVE"
    DELETED = "DELETED"


class RegistrationResult(StrEnumU):
    SUCCESS = "SUCCESS"
    VERIFY_EMAIL_REQUIRED = "VERIFY_EMAIL_REQUIRED"
    DUPLICATE_ACCOUNT = "DUPLICATE_ACCOUNT"
    PASSWORD_RULE_FAILED = "PASSWORD_RULE_FAILED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    MFA_REQUIRED = "MFA_REQUIRED"
    USER_INTERVENTION = "USER_INTERVENTION"
    FAILED = "FAILED"


# ---------------- Validation ----------------
class Severity(StrEnumU):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKING = "BLOCKING"


# ---------------- Provider integration levels (PRD §7) ----------------
class IntegrationLevel(IntEnum):
    P0 = 0  # registered / navigation only
    P1 = 1  # searchable
    P2 = 2  # standard metadata
    P3 = 3  # previewable
    P4 = 4  # public download
    P5 = 5  # authenticated download
    P6 = 6  # ordinary auto-registration
    P7 = 7  # full provider-specific parsing/versioning


SEARCH_RUN_FLOW: dict[str, set[str]] = {
    SearchRunStatus.CREATED: {SearchRunStatus.REQUIREMENT_PARSED, SearchRunStatus.FAILED, SearchRunStatus.CANCELLED},
    SearchRunStatus.REQUIREMENT_PARSED: {SearchRunStatus.PROVIDERS_SELECTED, SearchRunStatus.FAILED, SearchRunStatus.CANCELLED},
    SearchRunStatus.PROVIDERS_SELECTED: {SearchRunStatus.SEARCHING, SearchRunStatus.FAILED, SearchRunStatus.CANCELLED},
    SearchRunStatus.SEARCHING: {
        SearchRunStatus.CANDIDATES_NORMALIZED,
        SearchRunStatus.FAILED,
        SearchRunStatus.CANCELLED,
    },
    SearchRunStatus.CANDIDATES_NORMALIZED: {SearchRunStatus.CANDIDATES_EVALUATED, SearchRunStatus.FAILED, SearchRunStatus.CANCELLED},
    SearchRunStatus.CANDIDATES_EVALUATED: {
        SearchRunStatus.WAITING_USER_SELECTION,
        SearchRunStatus.AUTO_SELECTED,
        SearchRunStatus.COMPLETED,
        SearchRunStatus.FAILED,
        SearchRunStatus.CANCELLED,
    },
    SearchRunStatus.WAITING_USER_SELECTION: {SearchRunStatus.AUTO_SELECTED, SearchRunStatus.COMPLETED, SearchRunStatus.CANCELLED},
    SearchRunStatus.AUTO_SELECTED: {SearchRunStatus.COMPLETED, SearchRunStatus.CANCELLED},
    SearchRunStatus.COMPLETED: set(),
    SearchRunStatus.FAILED: set(),
    SearchRunStatus.CANCELLED: set(),
}

ACCESS_FLOW: dict[str, set[str]] = {
    AccessState.ACCESS_CHECK: {
        AccessState.PUBLIC_DOWNLOAD,
        AccessState.AUTH_REQUIRED,
        AccessState.FAILED,
        AccessState.CANCELLED,
    },
    AccessState.PUBLIC_DOWNLOAD: {AccessState.DOWNLOADING, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.AUTH_REQUIRED: {AccessState.SESSION_CHECK, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.SESSION_CHECK: {AccessState.DOWNLOADING, AccessState.LOGIN, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.LOGIN: {AccessState.DOWNLOADING, AccessState.REGISTER, AccessState.USER_INTERVENTION, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.REGISTER: {AccessState.DOWNLOADING, AccessState.USER_INTERVENTION, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.USER_INTERVENTION: {AccessState.DOWNLOADING, AccessState.FAILED, AccessState.CANCELLED, AccessState.NEEDS_REVIEW},
    AccessState.DOWNLOADING: {AccessState.VERIFYING, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.VERIFYING: {AccessState.PROFILING, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.PROFILING: {AccessState.ACQUIRED, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.ACQUIRED: set(),
    AccessState.FAILED: set(),
    AccessState.CANCELLED: set(),
    AccessState.NEEDS_REVIEW: set(),
}

BUILD_FLOW: dict[str, set[str]] = {
    BuildStatus.BUILD_CREATED: {BuildStatus.INPUTS_READY, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.INPUTS_READY: {BuildStatus.SCHEMA_ANALYSIS, BuildStatus.NEEDS_REVIEW, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.SCHEMA_ANALYSIS: {BuildStatus.SEMANTIC_ALIGNMENT, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.SEMANTIC_ALIGNMENT: {BuildStatus.ENTITY_RESOLUTION, BuildStatus.NEEDS_REVIEW, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.ENTITY_RESOLUTION: {BuildStatus.TEMPORAL_ALIGNMENT, BuildStatus.NEEDS_REVIEW, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.TEMPORAL_ALIGNMENT: {BuildStatus.TRANSFORM, BuildStatus.NEEDS_REVIEW, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.TRANSFORM: {BuildStatus.JOIN, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.JOIN: {BuildStatus.QA, BuildStatus.NEEDS_REVIEW, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.QA: {BuildStatus.PROVENANCE_FINALIZE, BuildStatus.NEEDS_REVIEW, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.PROVENANCE_FINALIZE: {BuildStatus.EXPORT, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.EXPORT: {BuildStatus.COMPLETE, BuildStatus.FAILED, BuildStatus.CANCELLED},
    BuildStatus.COMPLETE: set(),
    BuildStatus.FAILED: set(),
    BuildStatus.CANCELLED: set(),
    BuildStatus.NEEDS_REVIEW: set(),
}


def can_transition(flow: dict[str, set[str]], current: str, target: str) -> bool:
    return target in flow.get(current, set())


def assert_transition(flow: dict[str, set[str]], current: str, target: str, what: str) -> None:
    if not can_transition(flow, current, target):
        from app.core.errors import MetisError

        raise MetisError("STATE_INVALID", f"{what}: illegal transition {current} -> {target}", details={"from": current, "to": target})
