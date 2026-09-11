"""Access State Machine (Phase 4): explicit per-request access resolution bound to downloads.

States/flow per task list P04-001..011 and engineering prompt §8. Every transition is
validated, persisted (with reason + timestamps), and emits a UI event so the run is
auditable and resumable.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.schemas import new_id

log = get_logger("access")


class AccessState(StrEnum):
    ACCESS_PENDING = "ACCESS_PENDING"
    INSPECTING = "INSPECTING"
    PUBLIC = "PUBLIC"
    SESSION_CHECK = "SESSION_CHECK"
    SESSION_VALID = "SESSION_VALID"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    ACCOUNT_REQUIRED = "ACCOUNT_REQUIRED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    LOGGING_IN = "LOGGING_IN"
    REGISTER_REQUIRED = "REGISTER_REQUIRED"
    REGISTERING = "REGISTERING"
    VERIFY_EMAIL_REQUIRED = "VERIFY_EMAIL_REQUIRED"
    WAITING_CAPTCHA = "WAITING_CAPTCHA"
    WAITING_MFA = "WAITING_MFA"
    WAITING_AGREEMENT = "WAITING_AGREEMENT"
    WAITING_USER = "WAITING_USER"
    AUTHORIZED = "AUTHORIZED"
    ACQUIRING = "ACQUIRING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AccessAction(StrEnum):
    """What the executor should do next, derived from the state."""

    ACQUIRE_ANONYMOUS = "ACQUIRE_ANONYMOUS"
    ACQUIRE = "ACQUIRE"
    USE_SESSION = "USE_SESSION"
    DO_LOGIN = "DO_LOGIN"
    DO_REGISTER = "DO_REGISTER"
    WAIT_FOR_USER = "WAIT_FOR_USER"
    FAIL = "FAIL"


FLOW: dict[AccessState, set[AccessState]] = {
    AccessState.ACCESS_PENDING: {AccessState.INSPECTING, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.INSPECTING: {
        AccessState.PUBLIC,
        AccessState.SESSION_CHECK,
        AccessState.ACCOUNT_REQUIRED,
        AccessState.WAITING_USER,
        AccessState.FAILED,
        AccessState.CANCELLED,
    },
    AccessState.PUBLIC: {AccessState.AUTHORIZED},
    AccessState.SESSION_CHECK: {AccessState.SESSION_VALID, AccessState.SESSION_EXPIRED, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.SESSION_VALID: {AccessState.AUTHORIZED},
    AccessState.SESSION_EXPIRED: {AccessState.LOGIN_REQUIRED, AccessState.ACCOUNT_REQUIRED, AccessState.REGISTER_REQUIRED, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.ACCOUNT_REQUIRED: {AccessState.LOGIN_REQUIRED, AccessState.REGISTER_REQUIRED, AccessState.WAITING_USER, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.LOGIN_REQUIRED: {AccessState.LOGGING_IN, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.LOGGING_IN: {
        AccessState.AUTHORIZED,
        AccessState.SESSION_EXPIRED,
        AccessState.WAITING_CAPTCHA,
        AccessState.WAITING_MFA,
        AccessState.WAITING_USER,
        AccessState.FAILED,
        AccessState.CANCELLED,
    },
    AccessState.REGISTER_REQUIRED: {AccessState.REGISTERING, AccessState.WAITING_USER, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.REGISTERING: {
        AccessState.AUTHORIZED,
        AccessState.VERIFY_EMAIL_REQUIRED,
        AccessState.WAITING_CAPTCHA,
        AccessState.WAITING_MFA,
        AccessState.WAITING_USER,
        AccessState.FAILED,
        AccessState.CANCELLED,
    },
    AccessState.VERIFY_EMAIL_REQUIRED: {AccessState.WAITING_USER, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.WAITING_CAPTCHA: {AccessState.WAITING_USER},
    AccessState.WAITING_MFA: {AccessState.WAITING_USER},
    AccessState.WAITING_AGREEMENT: {AccessState.WAITING_USER},
    AccessState.WAITING_USER: {AccessState.INSPECTING, AccessState.LOGGING_IN, AccessState.REGISTERING, AccessState.AUTHORIZED, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.AUTHORIZED: {AccessState.ACQUIRING, AccessState.COMPLETE, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.ACQUIRING: {AccessState.COMPLETE, AccessState.FAILED, AccessState.CANCELLED},
    AccessState.COMPLETE: set(),
    AccessState.FAILED: set(),
    AccessState.CANCELLED: set(),
}


class AccessJob(BaseModel):
    access_job_id: str = ""
    provider_id: str = ""
    candidate_id: str = ""
    download_job_id: str = ""
    state: str = AccessState.ACCESS_PENDING
    reason: str = ""
    account_id: str | None = None
    browser_session_id: str | None = None
    created_at: str = ""
    updated_at: str = ""
    error_code: str | None = None
    history: list[dict] = []


def create_access_job(provider_id: str, candidate_id: str = "", download_job_id: str = "") -> AccessJob:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    job = AccessJob(
        access_job_id=new_id("acc"),
        provider_id=provider_id,
        candidate_id=candidate_id,
        download_job_id=download_job_id,
        state=AccessState.ACCESS_PENDING,
        created_at=now,
        updated_at=now,
        history=[{"state": AccessState.ACCESS_PENDING, "reason": "created", "ts": now}],
    )
    _persist(job)
    REPO.add_ui_event("access.created", provider_id=provider_id, task_id=download_job_id or None, payload={"access_job_id": job.access_job_id})
    return job


def transition(job: AccessJob, target: AccessState, reason: str = "") -> AccessJob:
    current = AccessState(job.state)
    if target not in FLOW.get(current, set()):
        raise MetisError("STATE_INVALID", f"access: illegal transition {current} -> {target}", details={"job": job.access_job_id, "reason": reason})
    from datetime import datetime, timezone

    job.state = target
    job.reason = reason
    job.updated_at = datetime.now(timezone.utc).isoformat()
    job.history.append({"state": target, "reason": reason, "ts": job.updated_at})
    _persist(job)
    REPO.add_ui_event("access.transition", provider_id=job.provider_id, task_id=job.download_job_id or None, payload={"access_job_id": job.access_job_id, "state": target, "reason": reason})
    log.info_ctx("access transition", job=job.access_job_id, state=target, reason=reason[:80])
    return job


def next_action(job: AccessJob) -> AccessAction:
    state = AccessState(job.state)
    mapping = {
        AccessState.AUTHORIZED: AccessAction.ACQUIRE,
        AccessState.PUBLIC: AccessAction.ACQUIRE_ANONYMOUS,
        AccessState.SESSION_VALID: AccessAction.USE_SESSION,
        AccessState.LOGIN_REQUIRED: AccessAction.DO_LOGIN,
        AccessState.REGISTER_REQUIRED: AccessAction.DO_REGISTER,
        AccessState.WAITING_CAPTCHA: AccessAction.WAIT_FOR_USER,
        AccessState.WAITING_MFA: AccessAction.WAIT_FOR_USER,
        AccessState.WAITING_AGREEMENT: AccessAction.WAIT_FOR_USER,
        AccessState.WAITING_USER: AccessAction.WAIT_FOR_USER,
    }
    return mapping.get(state, AccessAction.FAIL)


async def inspect_access_requirements(adapter, dataset_ref: str) -> dict:
    """Normalize adapter access requirements into P04-004 vocabulary:
    public / login_required / registration_possible / agreement_required / restricted / paid / unknown."""
    try:
        req = await adapter.get_access_requirements(dataset_ref)
    except MetisError as e:
        return {"public": False, "login_required": False, "registration_possible": False,
                "agreement_required": False, "restricted": False, "paid": False, "unknown": True, "error": e.code}
    raw = req if isinstance(req, dict) else (req.model_dump() if hasattr(req, "model_dump") else dict(req))
    access_mode = str(raw.get("access_mode", "UNKNOWN")).upper()
    requires_login = bool(raw.get("requires_login"))
    restricted = bool(raw.get("restricted"))
    notes = str(raw.get("notes", ""))
    agreement_required = "agreement" in notes.lower() or "eula" in notes.lower()
    paid = "payment" in notes.lower() or "purchase" in notes.lower() or "$" in notes
    return {
        "public": (not requires_login) and access_mode.startswith("PUBLIC"),
        "login_required": requires_login,
        "registration_possible": bool(raw.get("registration_possible", False)),
        "agreement_required": agreement_required,
        "restricted": restricted,
        "paid": paid,
        "unknown": access_mode == "UNKNOWN" and not requires_login,
        "license": raw.get("license", "UNKNOWN"),
        "notes": notes,
    }


def _persist(job: AccessJob) -> None:
    REPO.upsert_access_job(job.model_dump(mode="json"))
