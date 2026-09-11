"""P08/P09 E2E acceptance against local fixture pages (A6-A9, A12, A13, A16).

Runs a real Playwright Chromium (headless in CI via env; headed on desktop).
"""
from __future__ import annotations

import asyncio
import os

import pytest

from conftest import browser_run


def _url(fixture_server, page: str) -> str:
    return f"{fixture_server}/pages/{page}"


@pytest.mark.parametrize(
    "page,kind",
    [
        ("captcha.html", "CAPTCHA"),
        ("mfa.html", "MFA"),
        ("phone_otp.html", "PHONE_OTP"),
        ("institution.html", "INSTITUTION_VERIFICATION"),
        ("identity.html", "IDENTITY_VERIFICATION"),
        ("agreement.html", "RESTRICTED_DATA_AGREEMENT"),
        ("payment.html", "PAYMENT"),
    ],
)
def test_intervention_detection(browser_session, fixture_server, page, kind):
    """A9: agent auto-detects, stops, WAITING_USER with reason; resume works after user finishes."""
    async def go():
        from app.browser.runtime import DispatcherBlocked, LocatorTarget

        s = browser_session
        await s.navigate(_url(fixture_server, page))
        assert s.state.value == "WAITING_USER", f"{page}: state {s.state}"
        assert s.intervention and s.intervention["kind"] == kind
        # further agent input refused
        with pytest.raises(DispatcherBlocked):
            await s.click(LocatorTarget(role="button", name="CHECK"))
        # user completes manually then returns control
        ret = await s.return_to_agent()
        assert ret["url"] and s.state.value == "IDLE"
        await s.navigate(_url(fixture_server, "index.html"))  # agent continues from current page

    browser_run(go())


def test_login_executor_existing_account(browser_session, fixture_server):
    """A12: wrong password → invalid credentials (no infinite retry); right → session stored."""

    async def go():
        from app.auth.accounts import ACCOUNTS, LoginExecutor
        from app.auth.vault import get_vault
        from app.db.repository import REPO
        from app.domain.schemas import new_id

        ACCOUNTS.account_for("fixture_site", create=True)
        vault = get_vault()
        vault.set_secret("fixture_site.credentials", "WrongPass!123")
        REPO.add_credential(new_id("cred"), "fixture_site", "password", "researcher@example.edu", "fixture_site.credentials")

        class Driver:

            async def open(self, url):
                await browser_session.navigate(url)

            async def fill(self, selector, value):
                await browser_session.type_text(__import__("app.browser.runtime", fromlist=["LocatorTarget"]).LocatorTarget(css=selector), value, secret=("password" in selector))

            async def click(self, selector):
                await browser_session.click(__import__("app.browser.runtime", fromlist=["LocatorTarget"]).LocatorTarget(css=selector))

            async def current_url(self):
                return browser_session.page.url

            async def body_text(self):
                return await browser_session.page.inner_text("body")

        Driver.browser_session = browser_session  # P03-005: real storage_state save path

        form = {"email": "#email", "password": "#password", "_submit": "#login-btn"}
        result = await LoginExecutor("fixture_site", Driver()).login(_url(fixture_server, "login.html"), form)
        assert result["result"] == "INVALID_CREDENTIALS" and result["attempts"] == 1

        # now store the correct password → success + session persisted in vault
        vault.set_secret("fixture_site.credentials", "Corr3ct-Passw0rd!")
        result2 = await LoginExecutor("fixture_site", Driver()).login(_url(fixture_server, "login.html"), form)
        assert result2["result"] == "SUCCESS" and result2["storage_state_saved"] is True
        sessions = REPO.list_sessions("fixture_site")
        assert sessions and sessions[-1]["status"] == "VALID"
        # vault holds real storage state, not a placeholder
        assert get_vault().exists("fixture_site.storage_state")
        # account deletion revokes: next access must re-auth
        ACCOUNTS.delete_account("fixture_site")
        assert all(s["status"] == "REVOKED" for s in REPO.list_sessions("fixture_site"))
        assert not get_vault().exists("fixture_site.credentials")

    browser_run(go())


def test_registration_executor(browser_session, fixture_server):
    """A13: disabled switch → 0 submits; enabled → success/duplicate/password-rule/verify/captcha classified."""
    from app.auth.accounts import ACCOUNTS, IDENTITY, RegistrationExecutor

    IDENTITY.update_identity({"name": "Test Researcher", "email": "new@example.edu", "country": "CN", "institution": "Uni", "role": "researcher"})

    class Driver:
        async def open(self, url):
            await browser_session.navigate(url)

        async def fill(self, selector, value):
            from app.browser.runtime import LocatorTarget

            await browser_session.type_text(LocatorTarget(css=selector), value, secret=("password" in selector))

        async def click(self, selector):
            from app.browser.runtime import LocatorTarget

            await browser_session.click(LocatorTarget(css=selector))

        async def current_url(self):
            return browser_session.page.url

        async def body_text(self):
            return await browser_session.page.inner_text("body")

    async def go():
        form = {"name": "#name", "email": "#email", "password": "#password", "_submit": "#reg-btn"}
        ex = RegistrationExecutor("fixture_reg", Driver())

        # 1) switch off → nothing submitted
        ACCOUNTS.set_auto_register("fixture_reg", enabled=False)
        r0 = await ex.run(_url(fixture_server, "register.html"), form)
        assert r0["submitted"] is False

        # 2) enabled → success
        ACCOUNTS.set_auto_register("fixture_reg", enabled=True)
        IDENTITY.update_identity({"email": "fresh@example.edu"})
        r1 = await ex.run(_url(fixture_server, "register.html"), form)
        print("R1_RESULT:", r1)
        assert r1["result"] == "SUCCESS" and r1["submitted"] is True

        # 3) duplicate email detected
        IDENTITY.update_identity({"email": "taken@example.edu"})
        r2 = await ex.run(_url(fixture_server, "register.html"), form)
        assert r2["result"] == "DUPLICATE_ACCOUNT"

        # 4) password rule failed (fixture requires 8+; generated pw is 16+ strong, so
        #    force the failure path via provider rules weaker than fixture check)
        from app.auth.passwords import generate_password

        weak = generate_password({"min_length": 16})
        IDENTITY.update_identity({"email": "weakpw@example.edu"})
        # fixture rejects passwords missing upper/digit — patch generator output via monkey
        import app.auth.accounts as acc

        orig = acc.generate_password
        acc.generate_password = lambda rules=None: "alllowercasepw!!"
        try:
            r3 = await ex.run(_url(fixture_server, "register.html"), form)
        finally:
            acc.generate_password = orig
        assert r3["result"] == "PASSWORD_RULE_FAILED"

        # 5) verify email required
        IDENTITY.update_identity({"email": "verify@example.edu"})
        r4 = await ex.run(_url(fixture_server, "register.html"), form)
        assert r4["result"] == "VERIFY_EMAIL_REQUIRED"
        acct = next(a for a in __import__("app.db.repository", fromlist=["REPO"]).REPO.list_accounts() if a["provider_id"] == "fixture_reg")
        # pending email verification must NOT be fully active
        assert acct["status"] == "PENDING_EMAIL_VERIFICATION"

        # 6) CAPTCHA → stop, user intervention
        IDENTITY.update_identity({"email": "capt@example.edu"})

        async def click_captcha_box():
            pass

        # enable the checkbox (fixture simulates CAPTCHA) then submit
        from app.browser.runtime import LocatorTarget

        orig_click = Driver.click

        async def click_with_captcha(self, selector):
            if selector == "#reg-btn":
                await browser_session.click(LocatorTarget(css="#captcha"))
            await orig_click(self, selector)

        Driver.click = click_with_captcha
        r5 = await ex.run(_url(fixture_server, "register.html"), form)
        assert r5["result"] == "CAPTCHA_REQUIRED"

    browser_run(go())


def test_browser_download_capture(browser_session, fixture_server, temp_workspace):
    """A16: real download event captured, bound to job, verified; page 'success' text alone not trusted."""
    from app.downloads.service import MANAGER

    async def go():
        job = MANAGER.create_job("fixture_site", "panel_data", f"{fixture_server}/data/panel_data.csv", license="CC0-1.0")
        MANAGER.attach_to_browser_session(job, browser_session)
        await browser_session.navigate(_url(fixture_server, "downloads.html"))
        from app.browser.runtime import LocatorTarget

        await browser_session.click(LocatorTarget(role="link", name="Download"))
        await asyncio.sleep(1.5)
        results = await MANAGER.collect_browser_downloads(job, browser_session)
        assert results and results[0]["sha256"]
        assert results[0]["size"] > 0
        # suggested filename + source tab URL recorded
        dl = browser_session.downloads[0]
        assert dl["suggested_filename"] == "panel_data.csv"
        assert dl["source_url"].endswith("/pages/downloads.html")

    browser_run(go())
