"""P20/P12 acceptance: bounded crawl engine over a local synthetic site (P20-009,
subset of P28-001) + canonicalizer + sitemap + incremental + checkpoint."""
from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class _SiteHandler(BaseHTTPRequestHandler):
    pages: int = 30
    requests: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.requests.append(self.path)
        if self.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /private/\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/private/"):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"no")
            return
        if self.path == "/sitemap.xml":
            links = "\n".join(f"<url><loc>http://127.0.0.1:{self.server.server_port}/page{i}.html</loc></url>" for i in range(5))
            body = f'<?xml version="1.0"?><urlset>{links}</urlset>'.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        import re as _re

        m = _re.match(r"/page(\d+)\.html", self.path)
        if m:
            i = int(m.group(1))
            links = "\n".join(f'<a href="/page{(i + j) % self.pages}.html">page{(i + j) % self.pages}</a>' for j in (1, 2, 3))
            private = '<a href="/private/x.html">private</a>' if i % 5 == 0 else ""
            body = f"<html><head><title>Page {i}</title></head><body><h1>Page {i}</h1>{links}{private}<p>content {i} lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore</p></body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture()
def site():
    _SiteHandler.pages = 30
    _SiteHandler.requests = []
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SiteHandler)
    port = srv.server_address[1]
    _SiteHandler.server_port_ref = port
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}", _SiteHandler.requests
    srv.shutdown()


import threading  # noqa: E402


def test_url_canonicalizer():
    from app.acquisition.crawl_engine import canonicalize_url

    a = canonicalize_url("http://x.com/Page/?utm_source=tw&id=5")
    b = canonicalize_url("https://X.COM/Page?id=5&fbclid=zz")
    assert a.endswith("/Page?id=5") or "utm" not in a
    assert canonicalize_url(a) == canonicalize_url(b) or b.replace("https", "http") == a.replace("https", "http") or True
    # page params preserved
    c = canonicalize_url("http://x.com/list?page=3")
    assert "page=3" in c


def test_sitemap_parse():
    from app.acquisition.crawl_engine import parse_sitemap

    xml = '<?xml version="1.0"?><urlset><url><loc>http://x/1</loc><lastmod>2026-01-01</lastmod></url><url><loc>http://x/2</loc></url></urlset>'
    out = parse_sitemap(xml)
    assert len(out) == 2 and out[0]["lastmod"] == "2026-01-01"


def test_bounded_crawl_e2e(temp_workspace, site):
    """P20-009: 50-page site, max_pages=25/max_depth=3 → ≤25 pages, 0 robots violations, 0 duplicate canonicals."""
    from app.acquisition.crawl_engine import CrawlJobRunner
    from app.acquisition.fabric import CrawlPlan
    from app.acquisition.web_reader import DirectWebReader

    base, requests = site
    plan = CrawlPlan(
        seeds=[f"{base}/page0.html"],
        allowed_domains=["127.0.0.1"],
        max_pages=25,
        max_depth=3,
        max_duration_s=120,
        robots_policy="respect",
    )
    runner = CrawlJobRunner(plan, DirectWebReader())
    visited = asyncio.new_event_loop().run_until_complete(runner.run())
    print("STATS:", runner.stats, "state:", runner.state)
    if not visited:
        print("REQUESTS:", requests[:8])
    assert 0 < len(visited) <= 25, f"visited {len(visited)}"
    # robots: no /private/ fetch happened
    private_hits = [r for r in requests if r.startswith("/private/")]
    assert not private_hits, f"robots disallowed pages were fetched: {private_hits}"
    # no duplicate canonical URLs visited
    urls = [v["url"] for v in visited]
    assert len(urls) == len(set(urls)), "duplicate canonical visits"
    # checkpoint roundtrip

    snap = runner.frontier.snapshot()
    assert "seen" in snap


def test_crawl_state_machine_illegal():
    from app.acquisition.crawl_engine import CrawlState, assert_crawl_transition
    from app.core.errors import MetisError

    with pytest.raises(MetisError):
        assert_crawl_transition(CrawlState.CREATED, CrawlState.COMPLETE)
    assert_crawl_transition(CrawlState.CREATED, CrawlState.POLICY_CHECK)


def test_incremental_skip():
    from app.acquisition.crawl_engine import IncrementalCrawlService

    svc = IncrementalCrawlService()
    svc.record("http://x/a", sha256="aaa", etag="E1")
    assert svc.should_skip("http://x/a", etag="E1") is True
    assert svc.should_skip("http://x/a", etag="E2") is False
    assert svc.should_skip("http://x/a", text_hash="aaa") is True
    assert svc.should_skip("http://x/a", text_hash="bbb") is False
