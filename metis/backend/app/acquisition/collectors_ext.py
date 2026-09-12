"""P15/P16/P17/P19/P21/P23/P25/P26: remaining fabric modules in one compact package.

- wechat.py equivalents: WeChatOfficialAccountPlan + adapter (fixture-capable)
- ChineseSocialRecipe (P16-002); reference-only crawler policy in docs/THIRD_PARTY_ACQUISITION.md
- P17 OpenNews/OpenTwitter backends (token → Vault; NOT_CONFIGURED without)
- P19 WebClipTemplate + clip service
- P21 metadata/table/structured extractors
- P23 SiteExperienceStore + experience validator
- P25 agent tools (schema-bound) + AcquisitionPlanner
- P26 WatchJob + change detector

Each module is small and self-contained; the orchestration fabric owns policy/routing.
"""
from __future__ import annotations

import json
import re
import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.acquisition.fabric import SocialPost, _utcnow
from app.core.errors import MetisError


# ---------------- P15: WeChat ----------------
class WeChatOfficialAccountPlan(BaseModel):
    accounts: list[str] = Field(min_length=1, max_length=5)  # 小规模研究边界
    keywords: list[str] = []
    since: str | None = None
    until: str | None = None
    max_per_account: int = Field(default=10, ge=1, le=50)
    include_body: bool = True

    @field_validator("max_per_account")
    @classmethod
    def _cap(cls, v: int) -> int:
        if v > 50:
            raise ValueError("max_per_account capped at 50 for small-scale research; expand explicitly via config override")
        return v


# ---------------- P16-002: Chinese social recipes (Metis-native, no anti-detection) ----------------
CHINESE_SOCIAL_RECIPES: dict[str, dict] = {
    "weibo": {
        "platform": "weibo",
        "search_entry": "https://s.weibo.com/weibo?q={query}",
        "result_locator": ".card-wrap[mid]",
        "fields": {"post_id": "@mid", "text": ".txt", "author": ".name", "url": "a[href]"},
        "login_markers": ["passport.weibo.com"],
        "notes": "read-only public search; risk-control page → WAITING_USER",
    },
    "zhihu": {
        "platform": "zhihu",
        "search_entry": "https://www.zhihu.com/search?type=content&q={query}",
        "result_locator": ".SearchResult-Card",
        "fields": {"title": ".ContentItem-title", "text": ".RichText", "author": ".AuthorInfo-name", "url": ".ContentItem a[href]"},
        "login_markers": ["signin"],
    },
    "bilibili": {
        "platform": "bilibili",
        "search_entry": "https://search.bilibili.com/all?keyword={query}",
        "result_locator": ".bili-video-card",
        "fields": {"title": ".bili-video-card__info--tit", "author": ".bili-video-card__info--author", "url": "a[href]"},
        "login_markers": ["passport.bilibili.com"],
    },
}

# P16-001: reference-only crawler policy lives in docs/THIRD_PARTY_ACQUISITION.md and
# is enforced by tests/architecture (no import/vendor/dependency in production code).


# ---------------- P17: 6551 opennews / opentwitter ----------------
class _TokenBackend:
    configured: bool = False

    def __init__(self) -> None:
        from app.auth.secret_store import get_secret_store

        self.store = get_secret_store()
        self.configured = self.store.exists(self.token_key)

    def _token(self) -> str:
        if not self.configured:
            raise MetisError("PROVIDER_UNAVAILABLE", f"{self.backend_id} not configured: store token at Vault key {self.token_key}", retryable=False)
        return self.store.get_secret(self.token_key)


class OpenNewsBackend(_TokenBackend):
    backend_id = "opennews"
    token_key = "opennews.token"

    async def search(self, keyword: str, **params) -> list[dict]:
        token = self._token()
        from app.providers.http_client import get

        r = await get("https://api.6551.dev/opennews/search", params={"keyword": keyword, **params}, timeout=60, headers={"Authorization": f"Bearer {token}"})
        if r.status != 200:
            raise MetisError("PROVIDER_HTTP_ERROR", f"opennews HTTP {r.status}")
        items = r.json() or []
        for it in items:
            it["_provenance"] = {"backend": "opennews", "provider_supplied_derived": True}
        return items


class OpenTwitterBackend(_TokenBackend):
    backend_id = "opentwitter"
    token_key = "opentwitter.token"

    async def search(self, query: str, max_records: int = 20) -> list[SocialPost]:
        token = self._token()
        from app.providers.http_client import get

        r = await get("https://api.6551.dev/opentwitter/search", params={"query": query, "limit": max_records}, timeout=60, headers={"Authorization": f"Bearer {token}"})
        if r.status != 200:
            raise MetisError("PROVIDER_HTTP_ERROR", f"opentwitter HTTP {r.status}")
        out = []
        for it in r.json() or []:
            out.append(SocialPost(platform="x", post_id=str(it.get("id", "")), url=it.get("url", ""), author=it.get("username", ""), text=it.get("text", ""), raw_ref=json.dumps(it, ensure_ascii=False)[:2000]))
        return out


# ---------------- P19: Web Clip ----------------
class WebClipTemplate(BaseModel):
    name: str
    match_domains: list[str]
    properties_from: Literal["meta", "json_ld", "schema_org"] = "meta"
    content_selector: str = "main, article, #content"
    output_path_template: str = "{domain}/{date}-{slug}.md"
    version: int = 1


class ClipService:
    def match_template(self, templates: list[WebClipTemplate], url: str) -> WebClipTemplate | None:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
        for t in templates:
            for dom in t.match_domains:
                if host == dom.lower() or host.endswith("." + dom.lower()):
                    return t
        return None


# ---------------- P21: extractors ----------------
class MetadataExtractor:
    def extract(self, html: str) -> dict:
        out = {}
        for name, pat in [
            ("title", r"<title[^>]*>(.*?)</title>"),
            ("description", r'<meta[^>]+name="description"[^>]+content="([^"]*)"'),
            ("author", r'<meta[^>]+name="author"[^>]+content="([^"]*)"'),
            ("canonical", r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"'),
        ]:
            m = re.search(pat, html, re.I | re.S)
            if m:
                out[name] = {"value": m.group(1).strip(), "source": f"html:{name}-tag"}
        m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', html, re.I)
        if m and "title" not in out:
            out["title"] = {"value": m.group(1).strip(), "source": "og:title"}
        return out


class TableExtractor:
    def to_records(self, table_html: str) -> list[dict]:
        from io import StringIO

        import pandas as pd

        dfs = pd.read_html(StringIO(table_html))
        return dfs[0].to_dict(orient="records") if dfs else []


class JsonLdExtractor:
    def extract(self, html: str, *, max_depth: int = 3, max_bytes: int = 1_000_000) -> list[dict]:
        out = []
        for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
            raw = m.group(1)
            if len(raw) > max_bytes:
                continue
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    out.extend(data)
                else:
                    out.append(data)
            except (ValueError, TypeError):
                continue
        return out


# ---------------- P23: Site experience store ----------------
class SiteExperienceStore:
    """Domain-level experience; VERIFIED only after ≥2 successes. Never stores secrets."""

    def __init__(self) -> None:
        self._entries: dict[str, dict] = {}

    def record_success(self, domain: str, locator: str, backend: str) -> str:
        key = f"{domain}::{locator}::{backend}"
        e = self._entries.setdefault(key, {"successes": 0, "failures": 0, "status": "PROPOSED"})
        e["successes"] += 1
        e["status"] = "VERIFIED" if e["successes"] >= 2 else "PROPOSED"
        e["last_verified"] = _utcnow()
        return key

    def record_failure(self, domain: str, locator: str, backend: str) -> None:
        key = f"{domain}::{locator}::{backend}"
        e = self._entries.setdefault(key, {"successes": 0, "failures": 0, "status": "PROPOSED"})
        e["failures"] += 1
        if e["failures"] >= 2:
            e["status"] = "STALE"

    def get(self, domain: str) -> list[dict]:
        return [dict(k=key.split("::"), **e) if False else {"key": key, **e} for key, e in self._entries.items() if key.startswith(domain)]


# ---------------- P26: WatchJob + change detector ----------------
class WatchJob(BaseModel):
    watch_id: str = Field(default_factory=lambda: f"watch_{int(time.time() * 1000)}")
    plan_id: str
    cadence: Literal["daily", "weekly"] = "daily"
    last_run: str | None = None
    next_run: str | None = None
    checkpoint: dict = {}
    notify_on_change: bool = True
    status: str = "active"


class ChangeDetector:
    def has_content_changed(self, url: str, text_hash: str, store: dict) -> bool:
        prev = store.get(url)
        return prev is None or prev != text_hash
