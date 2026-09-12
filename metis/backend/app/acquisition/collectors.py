"""P14 社媒统一采集 + P18 论文发现/Digest + P22 采集 provenance（compact core）。

P14-001 SocialSourceAdapter contract；P14-002 SocialQueryPlan；P14-003 raw+normalized
双层存储；P14-004 去重（见 fabric.dedupe_social_posts）。
P18-002 paper search (arXiv real API)；P18-003 ranker；P18-004 digest 增量；
P18-005 watch 调度。P22 fetch/extraction provenance 记录器。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pathlib import Path

from pydantic import BaseModel, Field

from app.acquisition.fabric import PaperRecord, SocialPost, _utcnow

# ---------------- P14-001: SocialSourceAdapter contract ----------------
class SocialSourceAdapter:
    """Read-only contract: search / thread / profile. Implementations return SocialPost."""

    platform: str = ""

    async def search(self, query: str, *, max_records: int = 20, since: str | None = None, until: str | None = None, cursor: str | None = None) -> tuple[list[SocialPost], str | None]:
        raise NotImplementedError

    async def thread(self, post_id: str, *, max_records: int = 50) -> list[SocialPost]:
        raise NotImplementedError

    async def profile(self, account_id: str) -> dict:
        raise NotImplementedError


class InMemorySocialAdapter(SocialSourceAdapter):
    """Fixture/testing adapter (also the reference implementation)."""

    platform = "fixture"
    corpus: list[SocialPost] = []

    async def search(self, query, *, max_records=20, since=None, until=None, cursor=None):
        terms = query.lower().split()
        matched = [p for p in self.corpus if any(t in p.text.lower() for t in terms)]
        start = int(cursor or 0)
        page = matched[start: start + max_records]
        next_cursor = str(start + max_records) if start + max_records < len(matched) else None
        return page, next_cursor


class HackerNewsAdapter(SocialSourceAdapter):
    """Real public platform (no auth): HN search via Algolia public API → SocialPost."""

    platform = "hackernews"

    async def search(self, query, *, max_records=20, since=None, until=None, cursor=None):
        import httpx

        from app.providers.http_client import get

        r = await get("https://hn.algolia.com/api/v1/search", params={"query": query, "hitsPerPage": max_records}, timeout=30)
        if r.status != 200:
            raise RuntimeError(f"hn HTTP {r.status}")
        posts = []
        for hit in (r.json() or {}).get("hits", []):
            posts.append(SocialPost(
                platform=self.platform,
                post_id=str(hit.get("objectID", "")),
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                author=hit.get("author", ""),
                published=str(hit.get("created_at", "")),
                text=hit.get("title") or hit.get("story_title") or "",
                metrics={"likes": None, "replies": hit.get("num_comments"), "reposts": None, "views": None, "collected_at": _utcnow()},
                raw_ref=json.dumps({k: hit.get(k) for k in ("objectID", "title", "url", "points")}, ensure_ascii=False),
            ))
        return posts, None


# ---------------- P14-002: Social Query Planner ----------------
class SocialQueryPlan(BaseModel):
    platforms: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    hashtags: list[str] = []
    accounts: list[str] = []
    since: str | None = None
    until: str | None = None
    max_records_per_platform: int = Field(default=50, ge=1, le=1000)
    comment_depth: int = Field(default=0, ge=0, le=5)


def plan_social_query(text: str, *, default_days: int = 30) -> SocialQueryPlan:
    """Deterministic bounded planner: near-N-days → time window; platforms from mention."""
    import re
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    days = default_days
    m = re.search(r"(?:近|最近|past|last)\s*(\d+)\s*天", text) or re.search(r"(\d+)\s*days?", text)
    if m:
        days = min(int(m.group(1)), 365)
    platforms = []
    for name, pat in [
        ("x", r"(?<![A-Za-z])[Xx](?![A-Za-z])|推特|twitter"),
        ("weibo", r"微博|weibo"),
        ("reddit", r"reddit"),
        ("hackernews", r"HN\b|hacker news"),
        ("xiaohongshu", r"小红书"),
        ("bilibili", r"B站|bilibili"),
    ]:
        if re.search(pat, text, re.I):
            platforms.append(name)
    if not platforms:
        platforms = ["hackernews"]
    keywords = [w for w in re.findall(r"[\w\u4e00-\u9fff]{2,}", text.lower()) if w not in ("分析", "口碑", "数据", "采集")][:5]
    until = now.strftime("%Y-%m-%d")
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    return SocialQueryPlan(platforms=platforms, keywords=keywords, since=since, until=until, max_records_per_platform=50)


# ---------------- P18: Paper search / ranker / digest / watch ----------------
class PaperWatchPlan(BaseModel):
    topics: list[str] = Field(min_length=1)
    keywords: list[str] = []
    negative_keywords: list[str] = []
    sources: list[str] = ["arxiv"]
    since: str | None = None
    cadence: Literal["daily", "weekly"] = "daily"
    max_results: int = Field(default=20, ge=1, le=200)
    ranking_rubric: str = "relevance+recency"


class ArxivPaperSource:
    """Real public arXiv API (Atom XML) → PaperRecord."""

    source = "arxiv"

    async def search(self, query: str, max_results: int = 10) -> list[PaperRecord]:
        import re as _re
        from urllib.parse import quote

        from app.providers.http_client import get

        url = f"http://export.arxiv.org/api/query?search_query=all:{quote(query)}&max_results={max_results}"
        r = await get(url, timeout=60, max_retries=1)
        if r.status != 200:
            raise RuntimeError(f"arxiv HTTP {r.status}")
        text = r.text
        entries = _re.findall(r"<entry>(.*?)</entry>", text, _re.S)
        out = []
        for e in entries:
            title = _re.sub(r"\s+", " ", (_re.search(r"<title>(.*?)</title>", e, _re.S) or [None, ""])[1] if _re.search(r"<title>(.*?)</title>", e, _re.S) else "").strip()
            m = _re.search(r"<id>http://arxiv.org/abs/([^<v]+)(v\d+)?</id>", e)
            arxiv_id = m.group(1) if m else None
            published = (_re.search(r"<published>(.*?)</published>", e, _re.S) or [None, None])[1]
            summary = _re.sub(r"\s+", " ", (_re.search(r"<summary>(.*?)</summary>", e, _re.S) or [None, ""])[1]).strip()
            authors = _re.findall(r"<name>(.*?)</name>", e)
            out.append(PaperRecord(
                title=title, authors=authors, abstract=summary[:1000],
                published=published, venue="arXiv", arxiv_id=arxiv_id,
                url=f"http://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
                pdf_url=f"http://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None,
                topics=[], source="arxiv",
            ))
        return out


class PaperRanker:
    """P18-003: dimensioned recommendation (NOT fact). Every tier carries reasons."""

    def rank(self, papers: list[PaperRecord], plan: PaperWatchPlan) -> list[dict]:
        ranked = []
        for p in papers:
            reasons = []
            score = 0
            for kw in plan.keywords:
                if kw.lower() in p.title.lower():
                    score += 2
                    reasons.append(f"title contains {kw}")
                elif kw.lower() in p.abstract.lower():
                    score += 1
                    reasons.append(f"abstract contains {kw}")
            for neg in plan.negative_keywords:
                if neg.lower() in (p.title + p.abstract).lower():
                    score -= 2
                    reasons.append(f"negative {neg}")
            if p.doi or p.arxiv_id:
                score += 1
                reasons.append("has identifier")
            tier = "must_read" if score >= 3 else "skim" if score >= 1 else "scan"
            ranked.append({"paper": p.model_dump(), "tier": tier, "score": score, "reasons": reasons})
        ranked.sort(key=lambda x: -x["score"])
        return ranked


class PaperDigestService:
    """P18-004/005: run search → rank → only NEW papers are '新增'; persist seen keys."""

    def __init__(self, source) -> None:
        self.source = source
        self.ranker = PaperRanker()
        self.seen_path = None
        self._seen: set[str] = set()

    def attach_store(self, path) -> None:
        self.seen_path = path
        if Path(path).exists():
            self._seen = set(json.loads(Path(path).read_text(encoding="utf-8")))

    def _persist_seen(self) -> None:
        if self.seen_path:
            Path(self.seen_path).write_text(json.dumps(sorted(self._seen)), encoding="utf-8")

    async def run(self, plan: PaperWatchPlan) -> dict:
        papers = await self.source.search(" ".join(plan.keywords or plan.topics), max_results=plan.max_results)
        ranked = self.ranker.rank(papers, plan)
        new_items = []
        for item in ranked:
            key = PaperRecord(**item["paper"]).dedupe_key()
            if key not in self._seen:
                item["is_new"] = True
                new_items.append(item)
            self._seen.add(key)
        self._persist_seen()
        md_lines = [f"# Paper Digest — {plan.topics}", f"新增 {len(new_items)} 篇（共扫描 {len(ranked)}）", ""]
        for item in new_items:
            md_lines.append(f"## [{item['tier']}] {item['paper']['title']}")
            md_lines.append(f"- 作者: {', '.join(item['paper'].get('authors', [])[:5])}")
            md_lines.append(f"- 链接: {item['paper'].get('url')}")
            md_lines.append(f"- 理由: {'; '.join(item['reasons']) or 'n/a'}")
            md_lines.append("")
        digest_md = "\n".join(md_lines)
        return {"digest_md": digest_md, "ranked": ranked, "new_count": len(new_items), "total": len(ranked)}


# ---------------- P22: fetch/extraction provenance ----------------
@dataclass
class FetchProvenance:
    url: str
    final_url: str
    backend: str
    status: int
    fetched_at: str
    duration_ms: int
    headers_hash: str | None = None
    auth_mode: str = "anonymous"
    parent_url: str | None = None
    crawl_job_id: str | None = None

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


class ExtractionProvenance:
    """P22-002: per-field extraction lineage."""

    @staticmethod
    def record(field_name: str, *, extractor: str, version: str, source_artifact: str, locator: str, evidence: str, llm_model: str | None = None) -> dict:
        return {
            "field": field_name,
            "extractor": extractor,
            "extractor_version": version,
            "source_artifact": source_artifact,
            "locator": locator,
            "evidence": evidence[:300],
            "llm_model": llm_model,
            "recorded_at": _utcnow(),
        }


@dataclass
class BackendProvenance:
    """P22-003: external tool identity (distinguish Jina/XCrawl/AgentReach from official APIs)."""
    backend_id: str
    backend_type: str
    version: str = "unknown"
    upstream_url: str | None = None
    license: str = "UNKNOWN"
    cost_units: float | None = None

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)
