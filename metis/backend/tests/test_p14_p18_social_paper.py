"""P14/P18/P22 acceptance: social adapters, social query planner, paper search/digest, provenance records."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def test_social_query_plan_bounded():
    """P14-002: '分析近30天口碑' → explicit window + caps."""
    from app.acquisition.collectors import plan_social_query

    plan = plan_social_query("分析近30天某产品在X和微博的口碑")
    assert plan.since and plan.until
    assert "x" in plan.platforms and "weibo" in plan.platforms
    assert 1 <= plan.max_records_per_platform <= 1000
    # no time window mentioned → default 30 days still bounded
    plan2 = plan_social_query("某产品口碑")
    assert plan2.since and plan2.until


def test_social_adapter_contract():
    """P14-001: read-only adapter with cursor pagination → uniform SocialPost."""
    from app.acquisition.collectors import InMemorySocialAdapter
    from app.acquisition.fabric import SocialPost

    adapter = InMemorySocialAdapter()
    adapter.corpus = [
        SocialPost(platform="fixture", post_id=str(i), text=f"post about unemployment {i}")
        for i in range(7)
    ]
    page1, cursor = asyncio.new_event_loop().run_until_complete(adapter.search("unemployment", max_records=3))
    assert len(page1) == 3 and cursor is not None
    page2, cursor2 = asyncio.new_event_loop().run_until_complete(adapter.search("unemployment", max_records=3, cursor=cursor))
    assert len(page2) == 3
    ids = {p.post_id for p in page1} & {p.post_id for p in page2}
    assert not ids, "cursor pagination must not overlap"


def test_hackernews_real_adapter():
    """P30-005 subset: real public social/news platform (HN) → SocialPost list."""
    from app.acquisition.collectors import HackerNewsAdapter

    try:
        posts, _ = asyncio.new_event_loop().run_until_complete(HackerNewsAdapter().search("language models", max_records=5))
    except Exception as e:  # noqa: BLE001 — network flake: record, don't fail CI
        pytest.skip(f"HN unreachable: {e}")
    assert len(posts) >= 1
    p = posts[0]
    assert p.platform == "hackernews" and p.post_id and (p.url or p.text)


def test_paper_search_arxiv_real():
    """P18-002: real arXiv API → PaperRecord with identifiers."""
    from app.acquisition.collectors import ArxivPaperSource

    try:
        papers = asyncio.new_event_loop().run_until_complete(ArxivPaperSource().search("youth unemployment", max_results=5))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"arXiv unreachable: {e}")
    assert len(papers) >= 1 and papers[0].title
    assert any(p.arxiv_id for p in papers)


def test_paper_digest_incremental(temp_workspace):
    """P18-004/005: second run must not re-flag old papers as 新增."""
    from app.acquisition.collectors import PaperDigestService, PaperWatchPlan
    from app.acquisition.fabric import PaperRecord

    class StaticSource:
        async def search(self, query, max_results=10):
            return [
                PaperRecord(title="Old Paper on AI Labor", doi="10.1/old", source="arxiv"),
                PaperRecord(title="Brand New AI Labor Study", doi="10.1/new", source="arxiv"),
            ]

    plan = PaperWatchPlan(topics=["ai labor"], keywords=["ai labor"], max_results=10)
    svc = PaperDigestService(StaticSource())
    svc.attach_store(Path(temp_workspace) / "seen.json")
    run1 = asyncio.new_event_loop().run_until_complete(svc.run(plan))
    assert run1["new_count"] == 2  # both new on first run
    run2 = asyncio.new_event_loop().run_until_complete(svc.run(plan))
    assert run2["new_count"] == 0, "second run must not re-flag old papers"
    assert "digest_md" in run1 and "新增" in run1["digest_md"]


def test_paper_ranker_tiers_with_reasons():
    from app.acquisition.collectors import PaperRanker, PaperWatchPlan
    from app.acquisition.fabric import PaperRecord

    plan = PaperWatchPlan(topics=["ai"], keywords=["ai labor"], negative_keywords=["survey"])
    papers = [
        PaperRecord(title="AI labor demand shift", abstract="wage effects of ai labor", doi="10.1/1"),
        PaperRecord(title="A survey of everything", abstract="survey", doi="10.1/2"),
    ]
    ranked = PaperRanker().rank(papers, plan)
    assert ranked[0]["tier"] in ("must_read", "skim")
    assert all("reasons" in r for r in ranked)
    survey = next(r for r in ranked if "survey" in r["paper"]["title"].lower())
    assert any("negative" in reason for reason in survey["reasons"])


def test_fetch_and_extraction_provenance():
    """P22-001/002/003: provenance records with backend + field-level evidence."""
    from app.acquisition.collectors import BackendProvenance, ExtractionProvenance, FetchProvenance

    fp = FetchProvenance(url="http://x/a", final_url="http://x/a?", backend="direct", status=200,
                         fetched_at="2026-09-13T00:00:00Z", duration_ms=120, auth_mode="anonymous")
    assert fp.backend == "direct" and "headers_hash" in fp.to_json()

    ep = ExtractionProvenance.record("author", extractor="metadata_extractor", version="1.0",
                                     source_artifact="art_1", locator="meta[name=author]",
                                     evidence='<meta name="author" content="Zhang">')
    assert ep["field"] == "author" and ep["evidence"]

    bp = BackendProvenance(backend_id="jina", backend_type="reader", version="1.0",
                           upstream_url="https://r.jina.ai", license="commercial-terms")
    assert bp.backend_type == "reader" and bp.upstream_url
