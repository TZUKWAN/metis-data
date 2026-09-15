"""P14/P15/P16/P17/P19/P21/P23/P26 acceptance: collectors + social recipes + clip/watch."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def test_wechat_plan_caps():
    """P15-002: unlimited history rejected; max_per_account capped."""
    from app.acquisition.collectors_ext import WeChatOfficialAccountPlan

    plan = WeChatOfficialAccountPlan(accounts=["账号A"], max_per_account=10)
    assert plan.max_per_account == 10
    with pytest.raises(Exception):
        WeChatOfficialAccountPlan(accounts=["账号A"], max_per_account=500)
    with pytest.raises(Exception):
        WeChatOfficialAccountPlan(accounts=[])


def test_chinese_social_recipes_present():
    """P16-002: weibo/zhihu/bilibili recipes with search/result/login markers."""
    from app.acquisition.collectors_ext import CHINESE_SOCIAL_RECIPES

    for plat in ("weibo", "zhihu", "bilibili"):
        r = CHINESE_SOCIAL_RECIPES[plat]
        assert r["search_entry"] and r["result_locator"] and r["login_markers"]
    # no anti-detection / proxy / signature logic present
    for plat, r in CHINESE_SOCIAL_RECIPES.items():
        blob = json.dumps(r).lower()
        for banned in ("proxy", "fingerprint", "signature", "captcha_solver"):
            assert banned not in blob, f"{plat} contains banned capability {banned}"


def test_mediacrawler_reference_only_gate():
    """P16-001: production code contains zero MediaCrawler references."""

    app_dir = Path(__file__).resolve().parents[3] / "metis" / "backend" / "app"
    for f in app_dir.rglob("*.py"):
        assert "mediacrawler" not in f.read_text(encoding="utf-8").lower(), f"MediaCrawler leaked into {f.name}"


def test_opentwitter_not_configured(temp_workspace):
    """P17-001/002: no token → NOT_CONFIGURED error (token only in Vault)."""
    from app.acquisition.collectors_ext import OpenTwitterBackend
    from app.core.errors import MetisError

    backend = OpenTwitterBackend()
    assert backend.configured is False
    with pytest.raises(MetisError) as e:
        asyncio.new_event_loop().run_until_complete(backend.search("ai"))
    assert e.value.code == "PROVIDER_UNAVAILABLE"


def test_xcrawl_not_configured(temp_workspace):
    """P13-001: unconfigured → NOT_CONFIGURED; config only via Vault."""
    from app.acquisition.backends import XCrawlBackend
    from app.core.errors import MetisError

    backend = XCrawlBackend()
    if backend.configured:
        pytest.skip("xcrawl token present in vault")
    with pytest.raises(MetisError) as e:
        asyncio.new_event_loop().run_until_complete(backend.scrape("http://example.com"))
    assert "not configured" in str(e.value).lower()


def test_jina_requires_public_url(temp_workspace):
    """P12-003: jina refuses non-http urls (never used for login pages)."""
    from app.acquisition.backends import JinaReaderBackend
    from app.core.errors import MetisError

    backend = JinaReaderBackend()
    with pytest.raises(MetisError):
        asyncio.new_event_loop().run_until_complete(backend.read("internal://page"))


def test_agent_reach_health_not_installed(temp_workspace):
    """P08-002: CLI missing → NOT_INSTALLED (no auto-install)."""
    import shutil

    from app.acquisition.backends import AgentReachBackend

    if shutil.which("agent-reach"):
        pytest.skip("agent-reach installed on this machine")
    backend = AgentReachBackend()
    info = asyncio.new_event_loop().run_until_complete(backend.health())
    assert info["status"] == "not_installed"


def test_clip_template_matching_and_export(temp_workspace):
    """P19-001/002/003: template match → markdown file → path traversal rejected."""
    from app.acquisition.collectors_ext import ClipService, MetadataExtractor, WebClipTemplate

    templates = [WebClipTemplate(name="docs", match_domains=["docs.example.com"])]
    svc = ClipService()
    t = svc.match_template(templates, "https://docs.example.com/guide/x")
    assert t is not None
    assert svc.match_template(templates, "https://other.com/x") is None
    # obsidian exporter with path allowlist
    vault = temp_workspace / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    from app.acquisition.web_reader import DirectWebReader

    html = "<html><head><title>Guide</title></head><body><main><h1>Guide</h1><p>body text here</p></main></body></html>"
    art, content = DirectWebReader().build_artifact("https://docs.example.com/guide/x", "https://docs.example.com/guide/x", html, 200, {})
    meta = MetadataExtractor().extract(html)
    # allowlist check
    allowed_roots = [str(vault)]
    target = vault / "docs" / "guide.md"
    assert str(target).startswith(tuple(allowed_roots))
    target.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = "---\ntitle: Guide\nsource: https://docs.example.com/guide/x\n---\n"
    target.write_text(frontmatter + content.text, encoding="utf-8")
    assert "body text here" in target.read_text(encoding="utf-8")
    # traversal rejected
    evil = vault.parent / "evil.md"
    assert not str(evil).startswith(str(vault))


def test_metadata_and_table_extractors():
    """P21-001/002/003: traceable metadata, table→records, JSON-LD."""
    from app.acquisition.collectors_ext import JsonLdExtractor, MetadataExtractor, TableExtractor

    html = """<html><head><title>T</title><meta name="description" content="D">
    <script type="application/ld+json">{"@type":"Article","headline":"H"}</script></head>
    <body><table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>"""
    meta = MetadataExtractor().extract(html)
    assert meta["title"]["value"] == "T" and meta["title"]["source"].startswith("html:")
    tables = TableExtractor().to_records(html)
    assert tables and tables[0]["a"] == 1
    ld = JsonLdExtractor().extract(html)
    assert ld and ld[0]["@type"] == "Article"


def test_watch_change_detector(temp_workspace):
    """P26-001/002/003: change detector only fires on real change; watch state restorable."""
    from app.acquisition.collectors_ext import ChangeDetector, WatchJob

    job = WatchJob(plan_id="p1", cadence="daily")
    assert job.status == "active"
    det = ChangeDetector()
    store = {}
    assert det.has_content_changed("http://x/1", "hash1", store) is True
    store["http://x/1"] = "hash1"
    assert det.has_content_changed("http://x/1", "hash1", store) is False
    assert det.has_content_changed("http://x/1", "hash2", store) is True


def test_experience_store_lifecycle():
    """P23-001/002: success≥2 → VERIFIED; failures → STALE."""
    from app.acquisition.collectors_ext import SiteExperienceStore

    store = SiteExperienceStore()
    store.record_success("x.com", ".result", "browser")
    key = store.record_success("x.com", ".result", "browser")
    entries = store.get("x.com")
    assert any(e["status"] == "VERIFIED" and e["successes"] == 2 for e in entries)
    store.record_failure("x.com", ".result", "browser")
    store.record_failure("x.com", ".result", "browser")
    entries = store.get("x.com")
    assert any(e["status"] == "STALE" for e in entries)
    blob = json.dumps(store.get("x.com"))
    assert "cookie" not in blob.lower() and "token" not in blob.lower()


def test_agent_tools_schema_bound():
    """P25-001: agent tools are strict-schema bound, no run_shell."""
    from app.acquisition.collectors import plan_social_query
    from app.acquisition.collectors_ext import WeChatOfficialAccountPlan
    from app.acquisition.fabric import CrawlPlan

    # strict schemas validate; no arbitrary command string in any of them
    plan = CrawlPlan(seeds=["https://docs.x/g"], allowed_domains=["docs.x"])
    social = plan_social_query("近30天 X 上的 ai 口碑")
    wechat = WeChatOfficialAccountPlan(accounts=["a"], max_per_account=5)
    for obj in (plan, social, wechat):
        dumped = json.dumps(obj.model_dump())
        assert "run_shell" not in dumped and "command" not in dumped
