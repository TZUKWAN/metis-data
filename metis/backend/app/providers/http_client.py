"""Shared async HTTP client with timeout / retry / exponential backoff / rate-limit awareness."""
from __future__ import annotations

import asyncio
import random
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("http")

_USER_AGENT = "MetisData/1.0 (+https://localhost; research data acquisition agent)"


class HttpResponse:
    def __init__(self, status: int, content: bytes, headers: dict[str, str], url: str) -> None:
        self.status = status
        self.content = content
        self.headers = headers
        self.url = url

    def json(self) -> Any:
        import json

        return json.loads(self.content)

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


async def request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    respect_retry_after: bool = True,
) -> HttpResponse:
    """GET/POST with retries on 429/5xx and exponential backoff + jitter."""
    cfg = get_settings()
    timeout = timeout or cfg.http_timeout_s
    retries = cfg.http_max_retries if max_retries is None else max_retries
    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)

    attempt = 0
    last_exc: Exception | None = None
    while attempt <= retries:
        attempt += 1
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.request(method, url, params=params, headers=hdrs)
            if resp.status_code == 429 and respect_retry_after:
                retry_after = float(resp.headers.get("Retry-After", "2"))
                log.warning_ctx("rate limited, backing off", url=url, retry_after=retry_after)
                await asyncio.sleep(min(retry_after, 30))
                continue
            if resp.status_code >= 500 and attempt <= retries:
                await asyncio.sleep(min(2 ** attempt + random.random(), 20))
                continue
            return HttpResponse(resp.status_code, resp.content, dict(resp.headers), str(resp.url))
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt <= retries:
                await asyncio.sleep(min(2 ** attempt + random.random(), 20))
                continue
            break
    raise TimeoutError(f"{method} {url} failed after {attempt} attempts: {last_exc}")


async def get(url: str, **kw: Any) -> HttpResponse:
    return await request("GET", url, **kw)


class RateLimiter:
    """Simple per-provider min-interval limiter."""

    def __init__(self) -> None:
        self._last: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, provider_id: str, min_interval_s: float = 0.0) -> None:
        async with self._lock:
            now = time.monotonic()
            last = self._last.get(provider_id, 0.0)
            wait = last + min_interval_s - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[provider_id] = time.monotonic()


RATE_LIMITER = RateLimiter()
