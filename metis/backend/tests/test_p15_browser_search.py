"""P15 acceptance: Browser Search Worker (P15-001..006) — search without an HTTP API."""
from __future__ import annotations

import logging

import pytest
from conftest import browser_run


@pytest.fixture()
def quiet_browser_logs():
    logging.getLogger("app.browser.runtime").setLevel(logging.WARNING)
    yield


def _worker(fixture_server):
    from app.auth.recipes import BROWSER_SEARCH_RECIPES
    from app.search.browser_worker import BrowserSearchWorker

    return BrowserSearchWorker("fixture_catalog", BROWSER_SEARCH_RECIPES["fixture_catalog"], base_url=fixture_server)


def test_browser_search_fixture(temp_workspace, fixture_server, loop, quiet_browser_logs):
    """P15-001/002/006: recipe-driven search on the local catalog yields normalized candidates + evidence."""
    async def go():
        w = _worker(fixture_server)
        try:
            cands = await w.search("unemployment")
        finally:
            await w.close()
        assert cands, "expected at least one candidate for 'unemployment'"
        assert any("Youth unemployment" in c.title for c in cands)
        return cands

    cands = browser_run(go())

    from app.db.repository import REPO

    events = REPO.list_ui_events(limit=100)
    hit = next(e for e in events if e["kind"] == "browser_search.completed")
    assert hit["provider_id"] == "fixture_catalog"
    assert hit["payload"]["n_results"] == len(cands) >= 1
    assert any(u.lower().endswith("dataset_a.html") for u in hit["payload"]["urls"])


def test_browser_search_login_wall(temp_workspace, fixture_server, loop, quiet_browser_logs):
    """P15-004: intervention (CAPTCHA) mid-flow → USER_INTERVENTION_REQUIRED, never keep typing."""
    from app.core.errors import MetisError

    async def go():
        w = _worker(fixture_server)
        try:
            # worker opens the wall: A9 detection flips the session to WAITING_USER mid-open
            with pytest.raises(MetisError) as ei:
                await w.open_result(f"{fixture_server}/pages/captcha.html")
            assert ei.value.code == "USER_INTERVENTION_REQUIRED"
            assert w.session.state.value == "WAITING_USER"
            # a follow-up search must refuse to type/act, not push through the wall
            with pytest.raises(MetisError) as ei2:
                await w.search("unemployment")
            assert ei2.value.code == "USER_INTERVENTION_REQUIRED"
            assert not [e for e in w.session.events if e.action == "type"], "agent must not type after intervention"
        finally:
            await w.close()

    browser_run(go())


def test_normalize_candidates(temp_workspace, fixture_server, loop, quiet_browser_logs):
    """P15-005: candidates carry provider_id, absolute source_url, source_ref (last path segment)."""
    async def go():
        w = _worker(fixture_server)
        try:
            return await w.search("GDP")
        finally:
            await w.close()

    cands = browser_run(go())
    assert len(cands) == 1
    c = cands[0]
    assert c.provider_id == "fixture_catalog"
    src = c.sources[0]
    assert src.source_url == f"{fixture_server}/pages/dataset_b.html"
    assert src.source_ref == "dataset_b.html"
    assert c.files[0].source_url == src.source_url
    # detail page metadata enrichment: h1 title + direct data file link
    assert c.title == "GDP per capita world table"
    assert src.direct_file_url == f"{fixture_server}/data/panel_data.csv"
    assert src.file_format == "CSV"
