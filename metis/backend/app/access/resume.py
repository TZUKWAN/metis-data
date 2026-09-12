"""AccessResumeCoordinator (Phase G): resume an AUTHORIZED access job into acquisition.

Closes the Access→Login→Resume→Acquisition loop: after the user completes a manual step
(login/captcha/agreement) the Account Center flow marks the access job AUTHORIZED; this
coordinator then re-attaches the download job, rebuilds staging and drives the unified
AcquisitionService. Idempotent: a download job already COMPLETED is never re-acquired.
"""
from __future__ import annotations

from app.access.machine import AccessJob, AccessState
from app.acquisition.service import ACQUISITION  # module attribute: tests monkeypatch app.access.resume.ACQUISITION
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
            # 此阶段 access_context 传 {}：无已桥接凭据。
            # TODO(Phase F+): cookie bridging — if job.browser_session_id maps to a live
            # browser session, resolve cookies via app.auth.browser_auth_bridge.BRIDGE
            # .to_http_cookies(session) and attach them (transiently, never persisted)
            # under access_payload["access_context"]["cookies"].
            access_payload["access_context"] = {}
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


RESUME_COORDINATOR = AccessResumeCoordinator()
