"""Phase 4 acceptance: Access State Machine + download main path (P04-001..012)."""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest


def _setup_ws():
    ws = tempfile.mkdtemp()
    os.environ["METIS_WORKSPACE_DIR"] = ws
    os.environ["METIS_DB_URL"] = "sqlite:///" + ws.replace("\\", "/") + "/metis.db"
    from app.core.config import reset_settings

    reset_settings()
    from app.db.session import init_db, reset_engine

    reset_engine()
    init_db()
    return ws


class _Adapter:
    """Stub adapter for access-flow tests."""

    def __init__(self, access: dict) -> None:
        self._access = access
        self.provider_id = "stub"

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return self._access


def _patch_adapter(monkeypatch, adapter):
    import app.access.executor as ex

    monkeypatch.setattr(ex, "get_adapter", lambda pid: adapter)


def test_public_flow_authorized(monkeypatch):
    _setup_ws()
    _patch_adapter(monkeypatch, _Adapter({"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "notes": "public API"}))
    from app.access.executor import resolve_access

    job = asyncio.new_event_loop().run_until_complete(resolve_access("stub", "ds1"))
    assert job.state == "AUTHORIZED"
    assert [h["state"] for h in job.history] == ["ACCESS_PENDING", "INSPECTING", "PUBLIC", "AUTHORIZED"]


def test_login_required_no_account_waiting_user(monkeypatch):
    """No stored account + no auto-register → WAITING_USER (P04-009)."""
    _setup_ws()
    _patch_adapter(monkeypatch, _Adapter({"access_mode": "EXISTING_ACCOUNT", "requires_login": True, "notes": ""}))
    # stub out the real browser session probing (no browser in this unit test)
    import app.access.executor as ex

    async def fake_ensure(provider_id, make_session, base_url=None):
        return False, "no stored state", None

    monkeypatch.setattr(ex, "ensure_valid_session", fake_ensure)
    from app.access.executor import resolve_access

    job = asyncio.new_event_loop().run_until_complete(resolve_access("stub", "ds1", auto_register_enabled=False))
    assert job.state == "WAITING_USER"
    states = [h["state"] for h in job.history]
    assert "SESSION_EXPIRED" in states and "ACCOUNT_REQUIRED" in states


def test_stored_account_goes_to_login_dispatch(monkeypatch):
    _setup_ws()
    _patch_adapter(monkeypatch, _Adapter({"access_mode": "EXISTING_ACCOUNT", "requires_login": True, "notes": ""}))
    import app.access.executor as ex
    from app.db.repository import REPO
    from app.domain.schemas import new_id

    async def fake_ensure(provider_id, make_session, base_url=None):
        return False, "no stored state", None

    monkeypatch.setattr(ex, "ensure_valid_session", fake_ensure)
    REPO.add_credential(new_id("cred"), "stub", "password", "user@example.edu", "stub.credentials")
    from app.access.executor import resolve_access

    job = asyncio.new_event_loop().run_until_complete(resolve_access("stub", "ds1"))
    assert job.state == "LOGGING_IN"


def test_session_valid_authorized(monkeypatch):
    _setup_ws()
    _patch_adapter(monkeypatch, _Adapter({"access_mode": "EXISTING_ACCOUNT", "requires_login": True, "notes": ""}))
    import app.access.executor as ex

    class FakeSession:
        session_id = "sess_fake"

    async def fake_ensure(provider_id, make_session, base_url=None):
        return True, "logged_in_selector present", FakeSession()

    monkeypatch.setattr(ex, "ensure_valid_session", fake_ensure)
    from app.access.executor import resolve_access

    job = asyncio.new_event_loop().run_until_complete(resolve_access("stub", "ds1"))
    assert job.state == "AUTHORIZED"
    assert job.browser_session_id == "sess_fake"
    assert [h["state"] for h in job.history].count("SESSION_VALID") == 1


def test_illegal_transition_rejected():
    from app.access.machine import AccessJob, AccessState, transition
    from app.core.errors import MetisError

    job = AccessJob(access_job_id="x", state="ACCESS_PENDING")
    with pytest.raises(MetisError):
        transition(job, AccessState.AUTHORIZED, "skip everything")


def test_resume_after_user(monkeypatch):
    _setup_ws()
    from app.access.executor import resolve_access, resume_after_user

    # build a waiting job via the no-account path
    _patch_adapter(monkeypatch, _Adapter({"access_mode": "EXISTING_ACCOUNT", "requires_login": True, "notes": ""}))
    import app.access.executor as ex

    async def fake_ensure(provider_id, make_session, base_url=None):
        return False, "no stored state", None

    monkeypatch.setattr(ex, "ensure_valid_session", fake_ensure)
    job = asyncio.new_event_loop().run_until_complete(resolve_access("stub", "ds1"))
    assert job.state == "WAITING_USER"
    resumed = asyncio.new_event_loop().run_until_complete(resume_after_user(job.access_job_id, "success"))
    assert resumed.state == "AUTHORIZED"


def test_resume_nonexistent_job_raises():
    from app.access.executor import resume_after_user
    from app.core.errors import MetisError

    _setup_ws()
    with pytest.raises(MetisError):
        asyncio.new_event_loop().run_until_complete(resume_after_user("nonexistent", "agreement"))
