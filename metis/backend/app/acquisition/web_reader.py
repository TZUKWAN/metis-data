"""P12: 通用网页读取 — DirectWebReader (P12-001) + HtmlExtractor (P12-002) +
quality evaluator with fallback decision (P12-004). Jina backend (P12-003) in
readers_backends.py. All raw bytes immutable, content is UntrustedContent.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.acquisition.fabric import WebDocumentArtifact
from app.acquisition.injection_guard import UntrustedContent
from app.core import paths
from app.core.errors import MetisError
from app.core.logging import get_logger

log = get_logger("web.reader")


class DirectWebReader:
    """Plain HTTP reader for public pages: raw body saved, metadata extracted."""

    def __init__(self, backend: str = "direct") -> None:
        self.backend = backend

    async def read(self, url: str, *, timeout: float = 60.0, max_bytes: int = 32 * 1024 * 1024) -> tuple[WebDocumentArtifact, UntrustedContent]:
        from app.providers.http_client import get

        r = await get(url, timeout=timeout, max_retries=1)
        if r.status >= 400:
            raise MetisError("PROVIDER_HTTP_ERROR", f"fetch {url} HTTP {r.status}", details={"url": url})
        body = r.content
        if len(body) > max_bytes:
            raise MetisError("DOWNLOAD_TOO_LARGE", f"page {len(body)} > {max_bytes}")
        html = body.decode("utf-8", errors="replace")
        final_url = str(r.url) if hasattr(r, "url") else url
        return self.build_artifact(url, final_url, html, r.status, dict(r.headers))

    def build_artifact(self, url: str, final_url: str, html: str, status: int, headers: dict) -> tuple[WebDocumentArtifact, UntrustedContent]:
        title = _extract_title(html)
        text, markdown = _html_to_text_markdown(html)
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        raw_rel = _save_raw(url, html)
        md_rel = _save_markdown(url, markdown)
        art = WebDocumentArtifact(
            url=url,
            final_url=final_url or url,
            title=title,
            status_code=status,
            content_type=headers.get("Content-Type", headers.get("content-type", "")),
            html_raw_path=raw_rel,
            markdown_path=md_rel,
            text_hash=text_hash,
            backend=self.backend,
        )
        return art, UntrustedContent(text=text, source_url=url, backend=self.backend)


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return m.group(1).strip() if m else ""


_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_MULTIBLANK = re.compile(r"\n{3,}")


def _html_to_text_markdown(html: str) -> tuple[str, str]:
    """P12-002: local main-content extraction (no external service).

    Strategy: drop script/style/noscript, capture title + main/article/#content when
    present, convert headings/links/paragraphs to markdown-ish output."""
    title = _extract_title(html)
    body = html
    m = re.search(r"<(main|article)[^>]*>(.*?)</\1>", body, re.S | re.I)
    if m:
        body = m.group(2)
    else:
        m = re.search(r'<div[^>]+(?:id|class)="[^"]*(?:content|main)[^"]*"[^>]*>(.*?)</div>\s*(?:<footer|<script|</body)', body, re.S | re.I)
        if m:
            body = m.group(1)
    # headings → markdown
    body = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>", lambda m: "\n" + "#" * int(m.group(1)) + " " + re.sub(r"<[^>]+>", "", m.group(2)) + "\n", body, flags=re.S | re.I)
    # links → [text](href)
    body = re.sub(r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>', lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2))}]({m.group(1)})", body, flags=re.S | re.I)
    body = _SCRIPT_RE.sub("", body)
    text = _MULTIBLANK.sub("\n\n", _TAG_RE.sub(" ", body))
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    md = f"# {title}\n\n" + text if title else text
    return text, md


def _save_raw(url: str, html: str) -> str:
    from app.core import paths

    host = (urlparse(url).hostname or "site").replace(".", "_")
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]
    rel = f"{host}/{digest}.html"
    dest = paths.raw_root() / "_web" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return f"_web/{rel}"


def _save_markdown(url: str, markdown: str) -> str:
    from app.core import paths

    host = (urlparse(url).hostname or "site").replace(".", "_")
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:16]
    rel = f"{host}/{digest}.md"
    dest = paths.raw_root() / "_web" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(markdown, encoding="utf-8")
    return f"_web/{rel}"


# ---------------- P12-004: quality evaluator ----------------
@dataclass
class ReadQuality:
    sufficient: bool
    reasons: list[str] = field(default_factory=list)


def evaluate_read_quality(artifact: WebDocumentArtifact, text: str) -> ReadQuality:
    """Deterministic signals only: length, boilerplate ratio, JS-shell detection."""
    reasons: list[str] = []
    if len(text) < 500:
        reasons.append(f"thin text ({len(text)} chars)")
    n_tags = len(_TAG_RE.findall(text))
    if n_tags > len(text) / 10:
        reasons.append("unstripped tags remain")
    if re.search(r"enable javascript|requires javascript|please upgrade your browser", text, re.I):
        reasons.append("JS-shell page")
    if artifact.title and artifact.title.lower() not in text.lower() and len(text) > 200:
        pass  # title mismatch alone is not fatal
    return ReadQuality(sufficient=not reasons, reasons=reasons)


def should_fallback_to_reader_or_browser(quality: ReadQuality) -> bool:
    return not quality.sufficient
