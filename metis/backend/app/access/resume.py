"""AccessResumeCoordinator (Phase G): resume an AUTHORIZED access job into acquisition.

Closes the Access→Login→Resume→Acquisition loop: after the user completes a manual step
(login/captcha/agreement) the Account Center flow marks the access job AUTHORIZED; this
coordinator then re-attaches the download job, rebuilds staging and drives the unified
AcquisitionService. Idempotent: a download job already COMPLETED is never re-acquired.
"""
from __future__ import annotations

from app.access.machine import AccessJob, AccessState
from app.acquisition.service import ACQUISITION  # module attribute: tests monkeypatch app.access.resume.ACQUISITION
from app.auth.browser_auth_bridge import BRIDGE
from app.core import paths
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import DownloadJobStatus

log = get_logger("access.resume")


class AccessResumeCoordinator:
    async def resume_access_job(self, access_job_id: str) -> dict:
        """Resume acquisition for an AUTHORIZED access job. See module docstring for the contract."""
        data = REPO.get_access_job(access_job_id)
        if not data:
            raise MetisError("NOT_FOUND", f"access job {access_job_id} not found")
        job = AccessJob(**data)
        if job.state != str(AccessState.AUTHORIZED):
            return {"resumed": False, "reason": str(job.state)}

        download_job = REPO.get_download_job(job.download_job_id)
        if download_job is None:
            # rebuild the MANAGER job dict when the row was lost; keep the original id so
            # the access job link and audit trail stay intact
            download_job = {
                "download_job_id": job.download_job_id,
                "provider_id": job.provider_id,
                "dataset_ref": job.candidate_id,
                "dataset_title": "",
                "source_url": "",
                "status": DownloadJobStatus.CREATED,
            }
            REPO.save_download_job(download_job)

        if str(download_job.get("status", "")) == str(DownloadJobStatus.COMPLETED):
            return {"resumed": False, "reason": "already_completed"}

        staging = paths.workspace_root() / "downloads" / job.download_job_id
        staging.mkdir(parents=True, exist_ok=True)

        try:
            access_payload = dict(data)
            # P02-003: resolve REAL auth — live session (by browser_session_id) or a
            # Vault-restored storage_state session, then bridge cookies into the
            # transient transport context. Never an empty context by default.
            from app.access.resolver import AUTH_RESOLVER, RESOLVER

            session, reason = await RESOLVER.resolve(job.provider_id, job.browser_session_id, _make_session)
            access_ctx = await _build_access_context(session, job.provider_id, AUTH_RESOLVER)
            import sys as _sys
            print(f"DBG ctx auth_type={access_ctx.auth_type} cookies={sorted(access_ctx.transient_cookies.keys())} n_sessions={len(session.context.pages if session else [])}", file=_sys.stderr)
            log.info_ctx("resume context built", provider_id=job.provider_id,
                         auth_type=access_ctx.auth_type,
                         cookie_names=sorted(access_ctx.transient_cookies.keys()))
            access_payload["access_context"] = access_ctx.transport()
            files = await ACQUISITION.acquire(access_payload, download_job, staging)
        except Exception as e:  # noqa: BLE001 - persist failure state, then re-raise
            download_job["status"] = DownloadJobStatus.FAILED
            download_job["error_code"] = str(getattr(e, "code", "") or "RESUME_FAILED")
            download_job["error_message"] = str(e)[:300]
            REPO.save_download_job(download_job)
            REPO.add_ui_event(
                "access.resume_failed",
                "ERROR",
                task_id=job.download_job_id or None,
                provider_id=job.provider_id or None,
                payload={"access_job_id": job.access_job_id, "error_code": download_job["error_code"], "error": str(e)[:200]},
            )
            log.info_ctx("access resume failed", job=job.access_job_id, error=str(e)[:160])
            raise
        return {"resumed": True, "files": len(files)}


async def _make_session(task_label: str):
    from app.browser.runtime import MANAGER

    return await MANAGER.new_session(task_label)


async def _build_access_context(session, provider_id: str, auth_resolver):
    """Build the transport context: browser cookies when a session exists,
    plus oauth/api-key/header refs transiently dereferenced from the Vault."""
    from app.access.context import AuthorizedAccessContext

    if session is not None:
        ctx = await AuthorizedAccessContext.from_browser_session(session, provider_id)
        bridge = await BRIDGE.to_http_cookies(session)
        ctx.transient_cookies = bridge
        ctx.transient_headers.update(auth_resolver.resolve_oauth(provider_id))
        ctx.transient_headers.update(auth_resolver.resolve_api_key(provider_id))
        return ctx
    ctx = AuthorizedAccessContext(provider_id=provider_id, auth_type="api_key")
    ctx.transient_headers.update(auth_resolver.resolve_oauth(provider_id))
    ctx.transient_headers.update(auth_resolver.resolve_api_key(provider_id))
    return ctx


RESUME_COORDINATOR = AccessResumeCoordinator()
