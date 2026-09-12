"""P25 agent tools（严格 schema，无 run_shell）+ P27-003 SSRF guard 扩展（redirect 后复验）+ P28-004 quota。"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.errors import MetisError


# ---------------- P25-001: high-level agent tool schemas ----------------
class WebSearchTool(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)
    backend: Literal["auto", "serp", "news"] = "auto"


class WebReadTool(BaseModel):
    url: str = Field(min_length=1)
    prefer_markdown: bool = True


class WebCrawlTool(BaseModel):
    seeds: list[str] = Field(min_length=1)
    allowed_domains: list[str] = Field(min_length=1)
    max_pages: int = Field(default=25, ge=1, le=1000)
    max_depth: int = Field(default=3, ge=1, le=10)


class SocialSearchTool(BaseModel):
    platforms: list[str] = Field(min_length=1)
    keywords: list[str] = Field(min_length=1)
    since: str | None = None
    until: str | None = None
    max_records_per_platform: int = Field(default=50, ge=1, le=500)


class PapersSearchTool(BaseModel):
    query: str = Field(min_length=1)
    max_results: int = Field(default=20, ge=1, le=200)
    sources: list[str] = ["arxiv"]


class PapersWatchTool(BaseModel):
    topics: list[str] = Field(min_length=1)
    keywords: list[str] = []
    cadence: Literal["daily", "weekly"] = "daily"


class WeChatCollectTool(BaseModel):
    accounts: list[str] = Field(min_length=1, max_length=5)
    keywords: list[str] = []
    max_per_account: int = Field(default=10, ge=1, le=50)


class ContentExtractTool(BaseModel):
    artifact_id: str = Field(min_length=1)
    schema_json: dict = Field(min_length=1)


class CrawlStatusTool(BaseModel):
    crawl_job_id: str = Field(min_length=1)


class CrawlControlTool(BaseModel):
    crawl_job_id: str = Field(min_length=1)
    action: Literal["pause", "resume"]


AGENT_TOOLS: dict[str, type[BaseModel]] = {
    "web.search": WebSearchTool,
    "web.read": WebReadTool,
    "web.crawl": WebCrawlTool,
    "social.search": SocialSearchTool,
    "papers.search": PapersSearchTool,
    "papers.watch": PapersWatchTool,
    "wechat.collect": WeChatCollectTool,
    "content.extract": ContentExtractTool,
    "crawl.status": CrawlStatusTool,
    "crawl.pause": CrawlControlTool,
    "crawl.resume": CrawlControlTool,
}


def validate_tool_call(tool: str, args: dict) -> dict:
    """All agent tool calls must validate against a strict schema. No run_shell exists."""
    if tool == "run_shell":
        raise MetisError("STATE_INVALID", "run_shell is not an agent tool (policy)")
    schema = AGENT_TOOLS.get(tool)
    if schema is None:
        raise MetisError("STATE_INVALID", f"unknown agent tool {tool}")
    return schema(**args).model_dump()


# ---------------- P27-003: extended SSRF guard ----------------
def validate_url_strict(url: str, *, allow_private: bool | None = None) -> str:
    """Scheme + host checks + DNS resolve check (before request); block cloud metadata IPs.

    Redirect re-validation is handled by callers re-invoking this on each redirect target.
    allow_private defaults to env METIS_SSRF_ALLOW_PRIVATE (desktop dev = true).
    """
    import ipaddress
    import os
    import socket
    from urllib.parse import urlparse

    from app.core.errors import MetisError

    if allow_private is None:
        allow_private = os.environ.get("METIS_SSRF_ALLOW_PRIVATE", "true").lower() in ("1", "true", "yes")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise MetisError("STATE_INVALID", f"URL scheme not allowed: {parsed.scheme or '(none)'}")
    host = parsed.hostname or ""
    if not host:
        raise MetisError("STATE_INVALID", "URL has no host")
    blocked_hosts = {"169.254.169.254", "metadata.google.internal"}
    if host.lower() in blocked_hosts:
        raise MetisError("STATE_INVALID", f"metadata endpoint blocked: {host}")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise MetisError("PROVIDER_UNAVAILABLE", f"cannot resolve host {host}") from exc
    if not allow_private:
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise MetisError("STATE_INVALID", f"private network target blocked by SSRF guard: {host}")
    return url


# ---------------- P28-004: quota manager ----------------
class QuotaManager:
    """Daily caps for bytes/pages/paid-API units. Exceeded → PAUSED_QUOTA (never auto-buy)."""

    def __init__(self, *, max_bytes_per_day: int = 5 * 1024 * 1024 * 1024, max_crawl_pages_per_day: int = 5000, max_paid_units_per_day: float = 0.0) -> None:
        self.max_bytes_per_day = max_bytes_per_day
        self.max_crawl_pages_per_day = max_crawl_pages_per_day
        self.max_paid_units_per_day = max_paid_units_per_day
        self._used = {"bytes": 0, "pages": 0, "paid_units": 0.0, "day": ""}

    def _roll_day(self) -> None:
        import datetime

        today = datetime.date.today().isoformat()
        if self._used["day"] != today:
            self._used = {"day": today, "bytes": 0, "pages": 0, "paid_units": 0.0}

    def check(self, *, bytes_needed: int = 0, pages: int = 0, paid_units: float = 0.0) -> bool:
        self._roll_day()
        if self._used["bytes"] + bytes_needed > self.max_bytes_per_day:
            raise MetisError("STATE_INVALID", "daily byte quota exceeded → PAUSED_QUOTA", retryable=False)
        if self._used["pages"] + pages > self.max_crawl_pages_per_day:
            raise MetisError("STATE_INVALID", "daily crawl page quota exceeded → PAUSED_QUOTA", retryable=False)
        if self._used["paid_units"] + paid_units > self.max_paid_units_per_day and self.max_paid_units_per_day > 0:
            raise MetisError("STATE_INVALID", "daily paid-API quota exceeded → PAUSED_QUOTA", retryable=False)
        return True

    def record(self, *, bytes_used: int = 0, pages: int = 0, paid_units: float = 0.0) -> None:
        self._roll_day()
        self._used["bytes"] += bytes_used
        self._used["pages"] += pages
        self._used["paid_units"] += paid_units


QUOTA = QuotaManager()
