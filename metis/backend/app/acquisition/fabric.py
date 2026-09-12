"""Autonomous Acquisition Fabric — domain schemas (P05).

统一领域模型：网页 / 社媒 / 论文 / 公众号 / 通用爬取全部进入同一采集层，
共享 Raw 不可变、Provenance、Policy 与 Backend 合同。
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


# ---------------- P05-001: AcquisitionTaskType ----------------
class AcquisitionTaskType(str, Enum):
    DATASET_DISCOVERY = "dataset_discovery"
    DATASET_ACQUIRE = "dataset_acquire"
    WEB_READ = "web_read"
    WEB_CRAWL = "web_crawl"
    SITE_MAP = "site_map"
    SOCIAL_SEARCH = "social_search"
    SOCIAL_THREAD = "social_thread"
    SOCIAL_PROFILE = "social_profile"
    WECHAT_ACCOUNT = "wechat_account"
    PAPER_SEARCH = "paper_search"
    PAPER_WATCH = "paper_watch"
    NEWS_SEARCH = "news_search"
    USER_CLIP = "user_clip"
    STRUCTURED_EXTRACT = "structured_extract"


# ---------------- P05-002: CrawlPlan ----------------
class CrawlPlan(BaseModel):
    """Bounded crawl plan — unlimited plans are rejected at validation time."""

    seeds: list[str] = Field(min_length=1)
    allowed_domains: list[str] = Field(min_length=1)
    denied_domains: list[str] = []
    max_pages: int = Field(default=25, ge=1, le=100000)
    max_depth: int = Field(default=3, ge=1, le=20)
    max_duration_s: int = Field(default=600, ge=1)
    max_bytes: int = Field(default=512 * 1024 * 1024, ge=1)
    rate_limit_per_domain: float = Field(default=2.0, ge=0.1, description="min seconds between requests per domain")
    concurrency: int = Field(default=2, ge=1, le=16)
    rendering_policy: Literal["direct", "auto", "browser"] = "auto"
    auth_scope: list[str] = []
    robots_policy: Literal["respect", "not_applicable"] = "respect"
    link_policy: Literal["same_domain", "allowed_domains"] = "same_domain"
    content_types: list[str] = ["text/html"]
    extractors: list[str] = ["metadata", "links"]
    incremental: bool = True
    schedule: str | None = None

    @field_validator("seeds")
    @classmethod
    def _seeds_http(cls, v: list[str]) -> list[str]:
        for seed in v:
            if not seed.startswith(("http://", "https://")):
                raise ValueError(f"seed must be http(s): {seed}")
        return v


# ---------------- P05-003: WebDocumentArtifact ----------------
class WebDocumentArtifact(BaseModel):
    url: str
    final_url: str = ""
    title: str = ""
    fetched_at: str = Field(default_factory=_utcnow)
    status_code: int = 0
    content_type: str = ""
    html_raw_path: str = ""          # immutable raw HTML (relative to raw root)
    markdown_path: str = ""
    text_hash: str = ""              # sha256 of extracted text
    http_headers_ref: str | None = None
    screenshot_ref: str | None = None
    canonical_url: str | None = None
    backend: str = "direct"
    license_hint: str = "UNKNOWN"    # UNKNOWN never treated as open
    auth_mode: Literal["anonymous", "browser_session", "cookie", "oauth", "api_key"] = "anonymous"
    # P06-005: usage metadata
    terms_url: str | None = None
    redistribution_unknown: bool = True
    restricted_access: bool = False


# ---------------- P05-004: Social records ----------------
class SocialMetrics(BaseModel):
    likes: int | None = None
    replies: int | None = None
    reposts: int | None = None
    views: int | None = None
    collected_at: str = Field(default_factory=_utcnow)


class SocialPost(BaseModel):
    platform: str = Field(min_length=1)  # x | reddit | weibo | xiaohongshu | bilibili | ...
    post_id: str = Field(min_length=1)   # platform-unique
    url: str = ""
    author: str = ""
    published: str | None = None
    text: str = ""
    media: list[str] = []
    metrics: SocialMetrics | None = None
    hashtags: list[str] = []
    reply_to_post_id: str | None = None
    repost_of_post_id: str | None = None
    raw_ref: str = ""                    # immutable raw JSON/HTML reference


class SocialComment(BaseModel):
    platform: str
    comment_id: str
    post_id: str
    author: str = ""
    text: str = ""
    published: str | None = None
    raw_ref: str = ""


class SocialProfile(BaseModel):
    platform: str
    account_id: str
    display_name: str = ""
    url: str = ""
    followers: int | None = None
    raw_ref: str = ""


def dedupe_social_posts(posts: list[SocialPost]) -> tuple[list[SocialPost], list[dict]]:
    """P14-004: platform-internal post_id is the primary key; cross-platform similar
    text is only FLAGGED (probable_duplicate), never silently merged or dropped."""
    seen: set[tuple[str, str]] = set()
    unique: list[SocialPost] = []
    dropped: list[dict] = []
    for p in posts:
        key = (p.platform, p.post_id)
        if key in seen:
            dropped.append({"platform": p.platform, "post_id": p.post_id, "reason": "duplicate post_id"})
            continue
        seen.add(key)
        unique.append(p)
    flags = []
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            a, b = unique[i], unique[j]
            if a.platform != b.platform and a.text and b.text and a.text == b.text:
                flags.append({
                    "a": f"{a.platform}:{a.post_id}", "b": f"{b.platform}:{b.post_id}",
                    "relation": "probable_duplicate", "action": "kept_separate",
                })
    return unique, flags


# ---------------- P05-005: PaperRecord ----------------
class PaperRecord(BaseModel):
    title: str = Field(min_length=1)
    authors: list[str] = []
    abstract: str = ""
    published: str | None = None
    venue: str = ""
    doi: str | None = None
    arxiv_id: str | None = None
    url: str = ""
    pdf_url: str | None = None
    code_url: str | None = None
    datasets: list[str] = []
    topics: list[str] = []
    source: str = ""                 # arxiv | zenodo | openalex | web_search ...
    raw_ref: str = ""
    version: str | None = None

    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower()}"
        if self.arxiv_id:
            return f"arxiv:{self.arxiv_id}"
        return f"title:{self.title.lower().strip()}"


# ---------------- P05-006: BackendCapability ----------------
class BackendCapability(str, Enum):
    SEARCH = "search"
    READ = "read"
    CRAWL = "crawl"
    MAP = "map"
    BROWSER = "browser"
    AUTH = "auth"
    SOCIAL = "social"
    PAPER = "paper"
    NEWS = "news"
    MARKDOWN = "markdown"
    STRUCTURED_OUTPUT = "structured_output"
    SCREENSHOT = "screenshot"


class BackendStatus(str, Enum):
    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    NOT_CONFIGURED = "not_configured"
    UNHEALTHY = "unhealthy"


class BackendDescriptor(BaseModel):
    backend_id: str = Field(min_length=1)
    type: Literal["builtin", "cli_bridge", "external_api", "reader", "browser_bridge"]
    version: str = "unknown"
    license: str = "UNKNOWN"
    installed: bool = False
    healthy: bool | None = None
    auth_required: bool = False
    configured: bool = True
    cost_model: str = "free"         # free | paid | metered
    read_only: bool = True
    capabilities: list[BackendCapability] = []

    @property
    def status(self) -> BackendStatus:
        if not self.installed:
            return BackendStatus.NOT_INSTALLED
        if self.auth_required and not self.configured:
            return BackendStatus.NOT_CONFIGURED
        if self.healthy is False:
            return BackendStatus.UNHEALTHY
        return BackendStatus.AVAILABLE
