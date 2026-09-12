"""P03-004: concurrent browser search lifecycle stress — no orphan sessions.

10 parallel browser searches on the fixture catalog; 30% get cancelled mid-flight.
After all settle, every worker-owned session must be closed (no orphans).
"""
from __future__ import annotations

import asyncio
import asyncio
import random

from conftest import browser_run

import pytest

from conftest import browser_run


def test_concurrent_browser_search_no_orphans(temp_workspace, fixture_server, loop):
    from app.auth.recipes import BROWSER_SEARCH_RECIPES
    from app.browser.runtime import MANAGER
    from app.search.browser_worker import BrowserSearchWorker

    recipe = BROWSER_SEARCH_RECIPES["fixture_catalog"]

    async def one(i: int, cancel: bool):
        worker = BrowserSearchWorker("fixture_catalog", recipe, base_url=fixture_server)
        try:
            task = asyncio.ensure_future(worker.search("unemployment", limit=5))
            await asyncio.sleep(random.uniform(0.02, 0.25))
            if cancel:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return "cancelled"
            cands = await task
            return len(cands)
        finally:
            await worker.close()  # P03-002 guarantee (normally in orchestrator finally)

    async def run_all():
        random.seed(7)
        jobs = [one(i, cancel=(i % 3 == 0)) for i in range(10)]
        return await asyncio.gather(*jobs, return_exceptions=True)

    results = browser_run(run_all())
    ok = [r for r in results if isinstance(r, (int, str)) and not isinstance(r, BaseException)]
    assert any(isinstance(r, int) and r >= 1 for r in results), f"at least some searches must succeed: {results}"
    # no orphan LIVE sessions: every worker-owned session must be CLOSED (registry
    # retains the closed record for audit; the process/context is gone)
    live = [s for s in MANAGER.sessions()
            if str(s.get("task_label", "")).startswith("browser-search:") and s.get("state") != "CLOSED"]
    assert not live, f"orphan live sessions: {live}"
    assert len(results) == 10


def test_user_takeover_prevents_close(temp_workspace, fixture_server, loop):
    """P03-001: user-owned session survives worker.close()."""
    from app.auth.recipes import BROWSER_SEARCH_RECIPES
    from app.browser.runtime import MANAGER
    from app.search.browser_worker import BrowserSearchWorker

    recipe = BROWSER_SEARCH_RECIPES["fixture_catalog"]

    async def flow():
        w = BrowserSearchWorker("fixture_catalog", recipe, base_url=fixture_server, ownership="user")
        await w._ensure_session()
        sid = w.session.session_id
        await w.close()
        assert MANAGER.get(sid) is not None, "user-owned session must stay alive"
        await MANAGER.get(sid).close()

    import app.browser.runtime as rt

    recipe = BROWSER_SEARCH_RECIPES["fixture_catalog"]
    browser_run(flow())
