"""P20: 自主 Crawl Engine — CrawlJob 状态机 / URL canonicalizer / frontier /
link discovery / sitemap / fetch router / incremental / checkpoint / bounded E2E helpers."""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from app.acquisition.fabric import CrawlPlan
from app.acquisition.fabric_core import CrawlPolicyEngine, DomainRateLimiter
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.domain.enums import StrEnumU

log = get_logger("crawl")


# ---------------- P20-001: CrawlJob state machine ----------------
class CrawlState(StrEnumU):
    CREATED = "CREATED"
    POLICY_CHECK = "POLICY_CHECK"
    DISCOVERING = "DISCOVERING"
    FETCHING = "FETCHING"
    EXTRACTING = "EXTRACTING"
    VALIDATING = "VALIDATING"
    COMPLETE = "COMPLETE"
    WAITING_USER = "WAITING_USER"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


CRAWL_FLOW: dict[str, set[str]] = {
    CrawlState.CREATED: {CrawlState.POLICY_CHECK, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.POLICY_CHECK: {CrawlState.DISCOVERING, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.DISCOVERING: {CrawlState.FETCHING, CrawlState.COMPLETE, CrawlState.PAUSED, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.FETCHING: {CrawlState.EXTRACTING, CrawlState.FETCHING, CrawlState.COMPLETE, CrawlState.PAUSED, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.EXTRACTING: {CrawlState.FETCHING, CrawlState.COMPLETE, CrawlState.PAUSED, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.VALIDATING: {CrawlState.COMPLETE, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.COMPLETE: set(),
    CrawlState.WAITING_USER: {CrawlState.FETCHING, CrawlState.FAILED, CrawlState.CANCELLED},
    CrawlState.PAUSED: {CrawlState.FETCHING, CrawlState.CANCELLED},
    CrawlState.FAILED: set(),
    CrawlState.CANCELLED: set(),
}


def assert_crawl_transition(current: str, target: str) -> None:
    if target not in CRAWL_FLOW.get(CrawlState(current), set()):
        raise MetisError("STATE_INVALID", f"crawl: illegal transition {current} -> {target}")


# ---------------- P20-002: URL canonicalizer ----------------
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "ref", "referrer"}


def canonicalize_url(url: str, *, keep_params: list[str] | None = None) -> str:
    parsed = urlparse(url)
    scheme = "https" if parsed.scheme == "http" else parsed.scheme  # https preferred? keep original for local test servers
    scheme = parsed.scheme
    host = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    path = parsed.path or "/"
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
    params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS or (keep_params and k in keep_params)]
    query = urlencode(params)
    frag = ""
    return urlunparse((scheme, netloc, path, "", query, frag))


# ---------------- P20-003: Frontier ----------------
@dataclass(order=True)
class FrontierItem:
    priority: float
    depth: int
    url: str = field(compare=False)
    parent: str | None = field(default=None, compare=False)


class CrawlFrontier:
    """Priority queue with canonical dedupe + checkpoint snapshot (P20-003/008)."""

    def __init__(self) -> None:
        self._items: list[FrontierItem] = []
        self._seen: set[str] = set()

    def push(self, url: str, depth: int, priority: float = 0.0, parent: str | None = None) -> bool:
        canon = canonicalize_url(url)
        if canon in self._seen:
            return False
        self._seen.add(canon)
        self._items.append(FrontierItem(priority=-priority, depth=depth, url=canon, parent=parent))
        self._items.sort()
        return True

    def pop(self) -> FrontierItem | None:
        return self._items.pop(0) if self._items else None

    def __len__(self) -> int:
        return len(self._items)

    def snapshot(self) -> dict:
        return {
            "seen": sorted(self._seen),
            "pending": [{"url": it.url, "depth": it.depth, "priority": it.priority, "parent": it.parent} for it in self._items],
        }

    def restore(self, snap: dict) -> None:
        self._seen = set(snap.get("seen", []))
        self._items = sorted(
            (FrontierItem(priority=-it["priority"], depth=it["depth"], url=it["url"], parent=it.get("parent")) for it in snap.get("pending", [])),
        )


# ---------------- P20-004: link discovery ----------------
_LINK_HREF_RE = re.compile(r'<a[^>]+href="([^"]+)"', re.I)
_BAD_SCHEMES = ("mailto:", "javascript:", "data:", "tel:", "#")


def discover_links(html: str, base_url: str, plan: CrawlPlan, depth: int) -> list[tuple[str, int, str]]:
    """Extract in-scope links (url, depth, parent). Cross-domain non-allowlist excluded."""
    from app.providers.adapters.common import guess_format_from_url  # noqa: F401

    out: list[tuple[str, int, str]] = []
    parsed_base = urlparse(base_url)
    seed_host = (parsed_base.hostname or "").lower()
    for href in _LINK_HREF_RE.findall(html):
        href = href.strip()
        if not href or href.startswith(_BAD_SCHEMES):
            continue
        absu = urljoin(base_url, href)
        parsed = urlparse(absu)
        host = (parsed.hostname or "").lower()
        allowed = any(host == d.lower() or host.endswith("." + d.lower()) for d in plan.allowed_domains)
        if not allowed:
            continue
        if any(host == d.lower() or host.endswith("." + d.lower()) for d in plan.denied_domains):
            continue
        if plan.link_policy == "same_domain" and host != seed_host:
            continue
        out.append((absu, depth + 1, base_url))
    return out


# ---------------- P20-005: sitemap / RSS ----------------
def parse_sitemap(xml_text: str) -> list[dict]:
    """Return [{url, lastmod?}] from a urlset or sitemapindex."""
    import re as _re

    out = []
    for m in _re.finditer(r"<sitemap>.*?</sitemap>", xml_text, _re.S):
        block = m.group(0)
        loc = _re.search(r"<loc>(.*?)</loc>", block)
        lastmod = _re.search(r"<lastmod>(.*?)</lastmod>", block)
        if loc:
            out.append({"url": loc.group(1).strip(), "lastmod": lastmod.group(1).strip() if lastmod else None, "kind": "sitemap"})
    for m in _re.finditer(r"<url>.*?</url>", xml_text, _re.S):
        block = m.group(0)
        loc = _re.search(r"<loc>(.*?)</loc>", block)
        lastmod = _re.search(r"<lastmod>(.*?)</lastmod>", block)
        if loc:
            out.append({"url": loc.group(1).strip(), "lastmod": lastmod.group(1).strip() if lastmod else None, "kind": "url"})
    for m in _re.finditer(r"<item>.*?</item>", xml_text, _re.S):
        block = m.group(0)
        link = _re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", block, _re.S)
        date = _re.search(r"<pubDate>(.*?)</pubDate>", block)
        if link:
            out.append({"url": link.group(1).strip(), "lastmod": date.group(1).strip() if date else None, "kind": "feed"})
    return out


# ---------------- P20-006/007: fetch router + incremental ----------------


def _default_robots():
    from app.acquisition.fabric_core import ROBOTS

    return ROBOTS

class CrawlFetchRouter:
    """Choose backend per URL: policy → robots → direct reader; fallback quality-based."""

    def __init__(self, reader, robots=None, policy: CrawlPolicyEngine | None = None, rate_limiter: DomainRateLimiter | None = None) -> None:
        import app.acquisition.fabric_core as _fc

        self.reader = reader
        self.robots = robots if robots is not None else _fc.ROBOTS
        self.policy = policy if policy is not None else CrawlPolicyEngine()
        self.limiter = rate_limiter if rate_limiter is not None else DomainRateLimiter(default_interval=0.2)

    async def fetch(self, url: str, *, respect_robots: bool = True):

        if respect_robots:
            allowed, why = await self.robots.allowed(url)
            if not allowed:
                raise MetisError("BLOCKED_ROBOTS", why)
        parsed = urlparse(url)
        await self.limiter.acquire(parsed.hostname or "")
        artifact, content = await self.reader.read(url)
        return artifact, content


class IncrementalCrawlService:
    """P20-007: skip unchanged pages via content hash / ETag / Last-Modified."""

    def __init__(self) -> None:
        self.state: dict[str, dict] = {}  # canonical url → {sha256, etag, last_modified}

    def should_skip(self, url: str, etag: str | None = None, last_modified: str | None = None, text_hash: str | None = None) -> bool:
        prev = self.state.get(canonicalize_url(url))
        if not prev:
            return False
        if etag and prev.get("etag") and etag == prev["etag"]:
            return True
        if last_modified and prev.get("last_modified") and last_modified == prev["last_modified"]:
            return True
        if text_hash and prev.get("sha256") and text_hash == prev["sha256"]:
            return True
        return False

    def record(self, url: str, *, etag: str | None = None, last_modified: str | None = None, sha256: str | None = None) -> None:
        self.state[canonicalize_url(url)] = {"etag": etag, "last_modified": last_modified, "sha256": sha256}


# ---------------- P20-008: CrawlJob runner with checkpoint ----------------
class CrawlJobRunner:
    """Bounded crawler: policy → frontier → fetch → extract links → incremental.

    State persisted as checkpoint snapshots; strong-kill resumes from checkpoint.
    """

    def __init__(self, plan: CrawlPlan, reader, *, respect_robots: bool = True) -> None:
        import app.acquisition.fabric_core as _fc

        self.plan = plan
        self.router = CrawlFetchRouter(reader, policy=_fc.CrawlPolicyEngine(), rate_limiter=_fc.DomainRateLimiter(default_interval=plan.rate_limit_per_domain))
        self.frontier = CrawlFrontier()
        self.incremental = IncrementalCrawlService()
        self.visited: list[dict] = []
        self.state = CrawlState.CREATED
        self.stats = {"fetched": 0, "skipped_robots": 0, "skipped_unchanged": 0, "errors": 0}
        self._cancel = asyncio.Event()
        self.robots = self.router.robots

    def transition(self, target: CrawlState, reason: str = "") -> None:
        assert_crawl_transition(self.state, target)
        self.state = target
        log.info_ctx("crawl state", state=target, reason=reason[:80])

    def cancel(self) -> None:
        self._cancel.set()

    def checkpoint(self, path: Path) -> None:
        path.write_text(json.dumps({"state": self.state, "frontier": self.frontier.snapshot(), "visited": self.visited, "stats": self.stats}), encoding="utf-8")

    def restore(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        self.state = CrawlState(data["state"])
        self.frontier.restore(data["frontier"])
        self.visited = data["visited"]
        self.stats = data["stats"]

    async def run(self, *, checkpoint_path: Path | None = None, on_page=None) -> list[dict]:
        started = time.monotonic()
        self.transition(CrawlState.POLICY_CHECK, "policy gate")
        for seed in self.plan.seeds:
            self.frontier.push(seed, 0)
        self.transition(CrawlState.DISCOVERING, "seeds queued")

        while self.frontier and not self._cancel.is_set():
            if time.monotonic() - started > self.plan.max_duration_s:
                log.info_ctx("crawl duration cap reached", cap=self.plan.max_duration_s)
                break
            if len(self.visited) >= self.plan.max_pages:
                break
            item = self.frontier.pop()
            if item is None or item.depth > self.plan.max_depth:
                continue
            self.transition(CrawlState.FETCHING, f"fetch {item.url[:60]}")
            try:
                allowed, why = await self.robots.allowed(item.url) if self.plan.robots_policy == "respect" else (True, "not_applicable")
                if not allowed:
                    self.stats["skipped_robots"] += 1
                    continue

                artifact, content = await self.router.reader.read(item.url)
                self.transition(CrawlState.EXTRACTING, item.url[:60])
                if self.plan.incremental and self.incremental.should_skip(item.url, text_hash=artifact.text_hash):
                    self.stats["skipped_unchanged"] += 1
                    self.incremental.record(item.url, sha256=artifact.text_hash)
                    continue
                self.incremental.record(item.url, sha256=artifact.text_hash)
                self.visited.append({"url": item.url, "final_url": artifact.final_url, "title": artifact.title, "depth": item.depth, "sha256": artifact.text_hash, "backend": artifact.backend})
                self.stats["fetched"] += 1
                if on_page:
                    on_page(artifact, content)
                # discover links within depth budget
                if item.depth < self.plan.max_depth:
                    link_source = getattr(content, "raw_html", "") or content.text
                    for link, child_depth, _parent in discover_links(link_source, item.url, self.plan, item.depth):
                        self.frontier.push(link, min(child_depth, self.plan.max_depth))
                self.transition(CrawlState.FETCHING, "continue frontier")
                if checkpoint_path:
                    self.checkpoint(checkpoint_path)
            except MetisError as e:
                self.stats["errors"] += 1
                log.warning_ctx("crawl fetch error", url=item.url, code=e.code)
            except Exception as e:  # noqa: BLE001
                self.stats["errors"] += 1
                log.warning_ctx("crawl fetch crashed", url=item.url, error=str(e)[:120])
        self.transition(CrawlState.COMPLETE, f"fetched {len(self.visited)} pages")
        if checkpoint_path:
            self.checkpoint(checkpoint_path)
        return self.visited
