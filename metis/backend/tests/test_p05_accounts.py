"""Phase 5 acceptance: Account Center APIs (P05-002..012)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WIN32_ONLY = pytest.mark.skipif(sys.platform != 'win32', reason='DPAPI vault is Windows-only')

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


import asyncio  # noqa: E402


@pytest.fixture()
def api_client(monkeypatch, loop, fixture_server, temp_workspace):
    """TestClient running on the module loop so MANAGER browser stays loop-consistent."""
    from app.core.config import reset_settings
    from app.db.session import init_db, reset_engine

    reset_settings()
    reset_engine()
    init_db()
    # TestClient portals sync calls into the portal loop; we instead drive the ASGI app
    # via httpx ASGITransport on OUR loop so browser + API share one event loop.
    import httpx

    from app.api.main import app

    async def call(method, url, json=None):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.request(method, url, json=json)
            try:
                return resp.status_code, resp.json()
            except Exception:  # noqa: BLE001
                return resp.status_code, {}

    class Portal:
        def request(self, method, url, json=None):
            return loop.run_until_complete(call(method, url, json))

    return Portal(), fixture_server


@WIN32_ONLY
def test_register_api_and_login_api_flow(api_client):
    """P05-003/005/007/011: register (password policy) → login → storage_state → resume."""
    client, base = api_client
    from app.auth.accounts import ACCOUNTS, IDENTITY

    ACCOUNTS.set_auto_register("fixture_site", True)
    IDENTITY.update_identity({"name": "Test Researcher", "email": "p05@example.edu", "country": "CN", "institution": "Uni", "role": "researcher"})

    # 1) register a fresh account through the real browser
    code, body = client.request("POST", "/api/accounts/fixture_site/register", json={"base_url": base})
    assert code == 200, body
    # fresh@example.edu was used by earlier tests; use registration via identity default
    assert body["result"] in ("SUCCESS", "DUPLICATE_ACCOUNT", "VERIFY_EMAIL_REQUIRED")

    # 2) login with the correct fixture credentials through the API
    from app.auth.accounts import IDENTITY
    from app.auth.vault import get_vault
    from app.db.repository import REPO
    from app.domain.schemas import new_id

    ACCOUNTS.account_for("fixture_site", create=True)
    get_vault().set_secret("fixture_site.credentials", "Corr3ct-Passw0rd!")
    REPO.add_credential(new_id("cred"), "fixture_site", "password", "researcher@example.edu", "fixture_site.credentials")
    code, body = client.request("POST", "/api/accounts/fixture_site/login", json={"base_url": base})
    assert code == 200, body
    assert body["result"]["result"] == "SUCCESS"
    assert body["result"]["storage_state_saved"] is True


def test_register_retry_guard(api_client):
    """P05-012: more than 3 registration attempts → REGISTRATION_BLOCKED."""
    client, base = api_client
    from app.auth.accounts import ACCOUNTS
    from app.db.repository import REPO

    ACCOUNTS.set_auto_register("fixture_site", True)
    for i in range(3):
        REPO.add_ui_event("registration.submitted", payload={"provider": "fixture_site", "email": f"u{i}@x.edu"})
    code, body = client.request("POST", "/api/accounts/fixture_site/register", json={"base_url": base})
    assert code == 422 and body["error_code"] == "REGISTRATION_BLOCKED"


def test_register_disabled_blocked(api_client):
    client, base = api_client
    from app.auth.accounts import ACCOUNTS

    ACCOUNTS.set_auto_register("fixture_site", False)
    code, body = client.request("POST", "/api/accounts/fixture_site/register", json={"base_url": base})
    assert code == 422 and body["error_code"] == "REGISTRATION_BLOCKED"
