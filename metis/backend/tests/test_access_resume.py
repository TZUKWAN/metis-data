"""Phase G acceptance: AccessResumeCoordinator — AUTHORIZED → acquisition, idempotent, failure-safe.

Also covers the secret-free access context (cookie digest) and the browser→HTTP auth bridge
with a stub browser session (no real Playwright needed).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def _authorized_job(download_job_id: str) -> str:
    from app.access.machine import AccessState, create_access_job, transition

    job = create_access_job("stub", candidate_id="panel", download_job_id=download_job_id)
    transition(job, AccessState.INSPECTING, "test: inspecting")
    transition(job, AccessState.PUBLIC, "test: public source")
    transition(job, AccessState.AUTHORIZED, "test: authorized")
    return job.access_job_id


def _download_job() -> dict:
    from app.core import paths
    from app.db.repository import REPO
    from app.downloads.service import MANAGER

    created = MANAGER.create_job("stub", "panel", "https://example.invalid/panel.csv", license="CC0-1.0")
    (paths.workspace_root() / "downloads").mkdir(parents=True, exist_ok=True)
    return REPO.get_download_job(created.download_job_id)


class CommittingFakeAcquisition:
    """Fake ACQUISITION: stages a real file and commits it via the real MANAGER path."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, dict, Path]] = []

    async def acquire(self, access_job, download_job, staging_dir):
        from app.downloads.service import MANAGER

        self.calls.append((access_job, download_job, Path(staging_dir)))
        f = Path(staging_dir) / "resume_out.csv"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("a,b\n1,2\n", encoding="utf-8")
        info = await MANAGER._verify_and_commit(f, download_job, f.stat().st_size)
        return [str(info["raw_path"])]


def test_resume_authorized_then_idempotent(temp_workspace, monkeypatch):
    import app.access.resume as resume_mod
    from app.access.resume import RESUME_COORDINATOR
    from app.db.repository import REPO

    fake = CommittingFakeAcquisition()
    monkeypatch.setattr(resume_mod, "ACQUISITION", fake)

    dl = _download_job()
    acc_id = _authorized_job(dl["download_job_id"])

    res = asyncio.run(RESUME_COORDINATOR.resume_access_job(acc_id))
    assert res == {"resumed": True, "files": 1}
    assert len(fake.calls) == 1
    # access_context is empty at this stage (cookie bridging is a later phase)
    assert fake.calls[0][0].get("access_context") == {}
    saved = REPO.get_download_job(dl["download_job_id"])
    assert saved["status"] == "COMPLETED"

    # second call: download already COMPLETED → idempotent no-op
    res2 = asyncio.run(RESUME_COORDINATOR.resume_access_job(acc_id))
    assert res2 == {"resumed": False, "reason": "already_completed"}
    assert len(fake.calls) == 1, "must not re-acquire a completed download"


def test_resume_refuses_non_authorized(temp_workspace, monkeypatch):
    import app.access.resume as resume_mod
    from app.access.machine import AccessState, create_access_job, transition
    from app.access.resume import RESUME_COORDINATOR

    monkeypatch.setattr(resume_mod, "ACQUISITION", CommittingFakeAcquisition())
    job = create_access_job("stub", candidate_id="panel", download_job_id="dl-none")
    transition(job, AccessState.INSPECTING, "test")
    transition(job, AccessState.WAITING_USER, "test: waiting for user")

    res = asyncio.run(RESUME_COORDINATOR.resume_access_job(job.access_job_id))
    assert res["resumed"] is False
    assert res["reason"] == str(AccessState.WAITING_USER)


def test_resume_failure_marks_download_failed_and_reraises(temp_workspace, monkeypatch):
    import app.access.resume as resume_mod
    from app.access.resume import RESUME_COORDINATOR
    from app.core.errors import MetisError
    from app.db.repository import REPO
    from app.domain.enums import DownloadJobStatus

    class ExplodingAcquisition:
        async def acquire(self, access_job, download_job, staging_dir):
            raise MetisError("PROVIDER_HTTP_ERROR", "download HTTP 500")

    monkeypatch.setattr(resume_mod, "ACQUISITION", ExplodingAcquisition())

    dl = _download_job()
    acc_id = _authorized_job(dl["download_job_id"])

    with pytest.raises(MetisError) as e:
        asyncio.run(RESUME_COORDINATOR.resume_access_job(acc_id))
    assert e.value.code == "PROVIDER_HTTP_ERROR"

    saved = REPO.get_download_job(dl["download_job_id"])
    assert saved["status"] == DownloadJobStatus.FAILED
    assert saved["error_code"] == "PROVIDER_HTTP_ERROR"
    assert "HTTP 500" in (saved["error_message"] or "")
    events = [ev for ev in REPO.list_ui_events(limit=200) if ev["kind"] == "access.resume_failed"]
    assert events, "resume failure must be auditable via UI event"
    assert events[0]["payload"]["access_job_id"] == acc_id


def test_access_context_digest_and_bridge_no_secret_leak():
    """AuthorizedAccessContext stores only cookie names/counts; bridge resolves values on demand."""

    class FakeContext:
        async def cookies(self):
            return [
                {"name": "sid", "value": "SECRET-A", "domain": "x"},
                {"name": "sid", "value": "SECRET-A", "domain": "y"},
                {"name": "pref", "value": "SECRET-B", "domain": "x"},
            ]

        async def storage_state(self):
            return {"cookies": self._c, "origins": []}

        _c = [
            {"name": "sid", "value": "SECRET-A"},
            {"name": "pref", "value": "SECRET-B"},
        ]

    class FakeSession:
        session_id = "sess-test"

        def __init__(self):
            self.context = FakeContext()
            self.page = None

    from app.access.context import AuthorizedAccessContext
    from app.auth.browser_auth_bridge import BRIDGE

    session = FakeSession()
    ctx = asyncio.run(AuthorizedAccessContext.from_browser_session(session, "stub", account_id="acc-1"))
    assert ctx.provider_id == "stub"
    assert ctx.auth_type == "browser_session"
    assert ctx.browser_session_id == "sess-test"
    assert ctx.account_id == "acc-1"
    assert ctx.cookie_jar_ref == "stub.storage_state"
    assert ctx.cookie_summary == {"sid": 2, "pref": 1}
    dumped = ctx.model_dump_json()
    assert "SECRET-A" not in dumped and "SECRET-B" not in dumped, "context must never carry cookie values"

    cookies = asyncio.run(BRIDGE.to_http_cookies(session))
    assert cookies == {"sid": "SECRET-A", "pref": "SECRET-B"}
    state = asyncio.run(BRIDGE.export_storage_state(session))
    assert set(state) == {"cookies", "origins"} and len(state["cookies"]) == 2
