"""Phase 3 acceptance: real session persistence (P03-001..010)."""
from __future__ import annotations

import json

import pytest

from conftest import browser_run


def test_secret_store_interface(temp_workspace):
    """P03-001/002/003: interface complete; Windows DPAPI roundtrip; import-safe elsewhere."""
    from app.auth.secret_store import SecretStore, get_secret_store

    store = get_secret_store()
    assert isinstance(store, SecretStore)
    for m in ("set_secret", "get_secret", "delete_secret", "exists", "list_keys"):
        assert callable(getattr(store, m))
    store.set_secret("iface.probe", "value-METIS-TEST-SECRET")
    assert store.exists("iface.probe") and store.get_secret("iface.probe") == "value-METIS-TEST-SECRET"
    assert store.delete_secret("iface.probe") is True
    assert store.exists("iface.probe") is False
    # non-Windows path: constructing the DPAPI vault raises VAULT_UNAVAILABLE (import-safe module)
    import sys as _sys

    if _sys.platform != "win32":
        from app.auth.vault import Vault
        from app.core.errors import MetisError

        with pytest.raises(MetisError):
            Vault()


def test_storage_state_persist_restore_login(temp_workspace, fixture_server, loop):
    """P03-005/006/007: login → REAL storage_state saved → close browser → fresh session
    with restored state → probe logged_in_selector present (still logged in)."""
    from app.browser.runtime import MANAGER
    from app.auth.accounts import ACCOUNTS, LoginExecutor
    from app.auth.browser_state import ensure_valid_session, probe_session_valid, restore_browser_storage
    from app.auth.recipes import PROVIDER_RECIPES, resolve_url
    from app.auth.vault import get_vault
    from app.browser.runtime import LocatorTarget
    from app.db.repository import REPO
    from app.domain.schemas import new_id

    async def flow():
        # 1) bind credentials and login via the real fixture flow
        ACCOUNTS.account_for("fixture_site", create=True)
        get_vault().set_secret("fixture_site.credentials", "Corr3ct-Passw0rd!")
        REPO.add_credential(new_id("cred"), "fixture_site", "password", "researcher@example.edu", "fixture_site.credentials")

        sess = await MANAGER.new_session("p03-login")

        class Driver:
            browser_session = sess

            async def open(self, url):
                await sess.navigate(url)

            async def fill(self, selector, value):
                await sess.type_text(LocatorTarget(css=selector), value, secret=("password" in selector))

            async def click(self, selector):
                await sess.click(LocatorTarget(css=selector))

            async def current_url(self):
                return sess.page.url

            async def body_text(self):
                return await sess.page.inner_text("body")

        recipe = PROVIDER_RECIPES["fixture_site"]
        base = fixture_server
        form = {"email": recipe["login"]["email"], "password": recipe["login"]["password"], "_submit": recipe["login"]["submit"]}
        result = await LoginExecutor("fixture_site", Driver()).login(resolve_url(base, recipe["login_url"]), form)
        assert result["result"] == "SUCCESS" and result["storage_state_saved"] is True

        # vault holds a REAL storage state (cookies/localStorage), not a placeholder string
        raw = get_vault().get_secret("fixture_site.storage_state")
        state = json.loads(raw)
        assert "cookies" in state and "origins" in state
        joined = json.dumps(state)
        assert "metis_logged_in" in joined or any(c["name"] for c in state["cookies"])

        # 2) close the browser entirely, open a FRESH session, restore, probe
        await sess.close()
        sess2 = await MANAGER.new_session("p03-restore")
        restored = await restore_browser_storage(sess2.context, "fixture_site")
        assert restored is True
        ok, reason = await probe_session_valid(sess2, "fixture_site", account_url=resolve_url(base, recipe["account_url"]))
        assert ok, f"session should still be valid after restore: {reason}"
        return sess2

    sess2 = loop.run_until_complete(flow())
    loop.run_until_complete(sess2.close())


def test_expired_session_detection(temp_workspace, fixture_server, loop):
    """P03-008: stored state without login marker → probe fails → SESSION_EXPIRED marked."""
    from app.browser.runtime import MANAGER
    from app.auth.browser_state import ensure_valid_session, save_browser_state
    from app.db.repository import REPO

    async def flow():
        sess = await MANAGER.new_session("p03-expired")
        # visit origin so storage_state exists but WITHOUT logging in
        await sess.navigate(f"{fixture_server}/pages/index.html")
        await save_browser_state(sess, "fixture_site")
        await sess.close()
        ok, reason, s2 = await ensure_valid_session("fixture_site", MANAGER.new_session, base_url=fixture_server)
        assert ok is False and "SESSION_EXPIRED" in reason
        assert any(s["status"] == "SESSION_EXPIRED" for s in REPO.list_sessions("fixture_site"))
        return s2

    s2 = loop.run_until_complete(flow())
    loop.run_until_complete(s2.close())


def test_oauth_credential_model(temp_workspace):
    """P03-009/010: oauth tokens in vault, metadata in DB; deletion removes everything."""
    from app.auth.browser_state import OAuthCredential, delete_browser_state
    from app.auth.accounts import ACCOUNTS
    from app.auth.secret_store import get_secret_store
    from app.db.repository import REPO
    from app.domain.schemas import new_id

    cred = OAuthCredential(provider_id="oauth_provider", account_identity="user@example.edu", access_token="at-METIS-TEST-SECRET", refresh_token="rt", expires_at="2027-01-01T00:00:00Z", scope=["datasets"])
    cred.save()
    loaded = OAuthCredential.load("oauth_provider")
    assert loaded and loaded.access_token == "at-METIS-TEST-SECRET"
    assert [c for c in REPO.list_credentials("oauth_provider") if c["kind"] == "oauth"]

    # deletion: credentials + state + sessions
    ACCOUNTS.account_for("oauth_provider", create=True)
    removed = delete_browser_state.__wrapped__ if False else None
    import asyncio

    result = asyncio.new_event_loop().run_until_complete(delete_browser_state("oauth_provider"))
    OAuthCredential.load("oauth_provider") is None
    assert OAuthCredential.load("oauth_provider") is None
    assert all(s["status"] == "REVOKED" for s in REPO.list_sessions("oauth_provider"))
