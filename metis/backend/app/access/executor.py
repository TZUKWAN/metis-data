"""Access executor (P04-005..012): resolves a dataset access request through the state machine.

主链路（engineering prompt §3.3）:
  Download Request → AccessJob → inspect → PUBLIC / SESSION / LOGIN / REGISTER /
  WAITING_USER → Authorized → Acquisition.

Only reachability logic lives here; all actual browser work delegates to the
auth executors (login/registration) and DownloadManager.
"""
from __future__ import annotations

from app.access.machine import AccessJob, AccessState, create_access_job, transition
from app.auth.browser_state import ensure_valid_session
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.providers.base import get_adapter

log = get_logger("access.executor")


async def resolve_access(
    provider_id: str,
    dataset_ref: str,
    *,
    candidate_id: str = "",
    download_job_id: str = "",
    auto_register_enabled: bool | None = None,
    base_url: str | None = None,
) -> AccessJob:
    """Advance an AccessJob as far as possible without user interaction.

    Terminal-quiet states (WAITING_USER etc.) are returned for the UI to act on;
    AUTHORIZED means the caller may proceed to acquisition.
    """
    job = create_access_job(provider_id, candidate_id=candidate_id, download_job_id=download_job_id)
    adapter = get_adapter(provider_id)

    # ---- inspect ----
    transition(job, AccessState.INSPECTING, "inspecting provider access requirements")
    from app.access.machine import inspect_access_requirements

    req = await inspect_access_requirements(adapter, dataset_ref)

    if req.get("public"):
        transition(job, AccessState.PUBLIC, "anonymous access available")
        transition(job, AccessState.AUTHORIZED, "public data — acquisition authorized")
        return job

    # ---- needs auth ----
    if req.get("unknown") and not req.get("login_required"):
        transition(job, AccessState.INSPECTING, "access mode unknown; trying public path")
        # optimistically attempt anonymous acquisition for UNKNOWN providers (adapter raises if it fails)
        transition(job, AccessState.PUBLIC, "UNKNOWN access mode; anonymous attempt allowed")
        transition(job, AccessState.AUTHORIZED, "authorized for anonymous attempt (verify on acquire)")
        return job

    # real session check (P03-007/008)
    transition(job, AccessState.SESSION_CHECK, "probing stored session")
    valid, reason, session = await ensure_valid_session(provider_id, _make_session, base_url=base_url)
    if valid:
        job.browser_session_id = session.session_id
        transition(job, AccessState.SESSION_VALID, f"stored session valid: {reason}")
        transition(job, AccessState.AUTHORIZED, "existing session authorized")
        return job
    transition(job, AccessState.SESSION_EXPIRED, f"no valid session: {reason}")

    # ---- stored account? ----
    creds = [c for c in REPO.list_credentials(provider_id) if c["kind"] in ("password", "oauth")]
    if not creds:
        transition(job, AccessState.ACCOUNT_REQUIRED, "no stored account for provider")
        if not auto_register_enabled:
            transition(job, AccessState.WAITING_USER, "user must bind an account, register, or take over")
            return job
        transition(job, AccessState.REGISTER_REQUIRED, "auto registration enabled by user")
        transition(job, AccessState.REGISTERING, "registration executor dispatched")
        # registration runs via Account Center API (browser flow); stop here and wait
        transition(job, AccessState.WAITING_USER, "registration in progress — continue after user confirms")
        return job

    transition(job, AccessState.LOGIN_REQUIRED, f"stored account present ({creds[0]['account_label']})")
    transition(job, AccessState.LOGGING_IN, "login executor dispatched via Account Center/browser flow")
    # Actual login needs the browser + user visibility; the Account Center login API
    # drives it (P05-003) and continues this job (P04-010 resume). Stop at LOGGING_IN.
    REPO.add_ui_event("access.login_dispatched", provider_id=provider_id, task_id=download_job_id or None, payload={"access_job_id": job.access_job_id})
    return job


async def resume_after_user(job_id: str, outcome: str) -> AccessJob:
    """P04-010: user completed the manual step (login/captcha/agreement) — resume."""
    data = REPO.get_access_job(job_id)
    if not data:
        raise MetisError("NOT_FOUND", f"access job {job_id} not found")
    job = AccessJob(**data)
    if outcome == "success":
        transition(job, AccessState.AUTHORIZED, "user completed the manual step")
    elif outcome == "captcha":
        transition(job, AccessState.WAITING_CAPTCHA, "CAPTCHA encountered")
        transition(job, AccessState.WAITING_USER, "user takeover required")
    elif outcome == "mfa":
        transition(job, AccessState.WAITING_MFA, "MFA encountered")
        transition(job, AccessState.WAITING_USER, "user takeover required")
    elif outcome == "agreement":
        transition(job, AccessState.WAITING_AGREEMENT, "agreement requires explicit user acceptance")
        transition(job, AccessState.WAITING_USER, "user takeover required")
    else:
        transition(job, AccessState.FAILED, f"user reported failure: {outcome}")
    return job


async def _make_session(task_label: str):
    from app.browser.runtime import MANAGER

    return await MANAGER.new_session(task_label)


async def acquire_authorized(job: AccessJob, download_job: dict, staging_dir) -> list[str]:
    """AUTHORIZED → ACQUIRING → adapter acquire into staging (DownloadManager verifies/commits)."""
    transition(job, AccessState.ACQUIRING, "authorized — acquiring")
    adapter = get_adapter(job.provider_id)
    files = await adapter.acquire_dataset(download_job["dataset_ref"], staging_dir, {})
    return files
