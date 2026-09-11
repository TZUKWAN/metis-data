"""Phase 2 acceptance: browser productization (P02-002..014)."""
from __future__ import annotations

import asyncio
import base64
import json

import pytest

from conftest import browser_run


def test_live_stream_frames_and_meta(browser_session, fixture_server):
    """P02-002: WS-less unit path — get_frame yields JPEG frames + cursor meta at usable rate."""
    async def go():
        s = browser_session
        await s.navigate(f"{fixture_server}/pages/index.html")
        t0 = asyncio.get_event_loop().time()
        frames = 0
        while asyncio.get_event_loop().time() - t0 < 1.5:
            f = await s.get_frame()
            assert f["alive"]
            raw = base64.b64decode(f["img"])
            assert raw[:2] == b"\xff\xd8"  # JPEG magic
            frames += 1
        fps = frames / 1.5
        assert fps >= 8, f"frame rate too low: {fps:.1f} fps (target ~15)"

    browser_run(go())


def test_visible_cursor_and_click_feedback(browser_session, fixture_server):
    """P02-004/005/006: semantic click moves cursor with interpolation + records click."""
    from app.browser.runtime import LocatorTarget

    async def go():
        s = browser_session
        await s.navigate(f"{fixture_server}/pages/locator_test.html")
        before = dict(s.cursor)
        await s.click(LocatorTarget(role="button", name="Move Button Now"))
        assert s.cursor != before, "cursor must have moved to the element"
        assert s.last_click and s.last_click["x"] == s.cursor["x"]
        # frame carries cursor + recent click
        f = await s.get_frame()
        assert f["cursor"] == s.cursor and f["click"]["x"] == s.cursor["x"]

    browser_run(go())


def test_keyboard_typing_visible_not_fill(browser_session, fixture_server):
    """P02-007/008: normal input uses real keyboard typing (visible), secrets use fill."""
    from app.browser.runtime import LocatorTarget

    async def go():
        s = browser_session
        await s.navigate(f"{fixture_server}/pages/login.html")
        r = await s.type_text(LocatorTarget(css="#email"), "researcher@example.edu")
        assert r["typed_by"] == "keyboard"  # default: real typing, char-by-char visible
        assert (await s.page.input_value("#email")) == "researcher@example.edu"
        r2 = await s.type_text(LocatorTarget(css="#password"), "Corr3ct-Passw0rd!", secret=True)
        assert r2["typed_by"] == "fill" and r2["secret"]
        # typed value never lands in events
        events = json.dumps([e.public(__import__("app.core.logging", fromlist=["redact"]).redact) for e in s.events])
        assert "Corr3ct-Passw0rd!" not in events

    browser_run(go())


def test_tab_model(browser_session, fixture_server):
    """P02-010: tabs enumerable with url/active; switching works."""
    async def go():
        s = browser_session
        await s.navigate(f"{fixture_server}/pages/index.html")
        await s.new_tab(f"{fixture_server}/pages/login.html")
        assert len(s._pages) == 2
        from app.api.main import browser_tabs

        tabs = await browser_tabs(s.session_id)
        assert len(tabs["tabs"]) == 2
        assert tabs["tabs"][1]["active"] is True
        assert "login.html" in tabs["tabs"][1]["url"]
        await s.switch_tab(0)
        assert "index.html" in s.page.url

    browser_run(go())


def test_crash_detection_marks_crashed(browser_session, fixture_server):
    """P02-013: killed page/browser → CRASHED state, never fake IDLE."""
    async def go():
        s = browser_session
        await s.navigate(f"{fixture_server}/pages/index.html")
        await s.context.close()  # simulate death of the underlying browser context
        crashed = await s.check_crashed()
        assert crashed and s.state.value == "CRASHED"
        f = await s.get_frame()
        assert f == {"alive": False}

    browser_run(go())


def test_url_sanitization():
    """P02-014: sensitive query values masked in URLs surfaced to events/UI."""
    from app.browser.runtime import sanitize_url

    masked = sanitize_url("https://x.com/data?token=abc123&size=10&otp=999")
    assert "abc123" not in masked and "999" not in masked
    assert "size=10" in masked and "token=***" in masked
    assert sanitize_url(None) is None
