"""Browser Search Worker (P15): dataset discovery on platforms without an HTTP API.

The EXECUTION layer is shared; per-provider locators live in
app/auth/recipes.py (BROWSER_SEARCH_RECIPES). The worker drives the real browser
runtime (P08): open the catalog search page, type the query, submit, extract
result links (href + text), optionally paginate (P15-003), then open each result
page for minimal metadata (h1 / meta description / direct file link).

- Login-aware (P15-004): the runtime's intervention detection (A9) flips the
  session to WAITING_USER on CAPTCHA/MFA/OTP/... — the worker refuses to type or
  act any further and raises USER_INTERVENTION_REQUIRED.
- Normalization (P15-005): every result becomes a DatasetCandidate with
  provider_id, title, absolute source_url and source_ref (last path segment).
- Evidence (P15-006): a browser_search.completed ui_event is persisted after
  each completed search (P15-006).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urljoin, urlparse

from app.auth.recipes import resolve_url
from app.browser.runtime import MANAGER, BrowserSession, LocatorTarget
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import BrowserSessionState
from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import guess_format_from_url, mk_candidate

log = get_logger("search.browser")


class BrowserSearchWorker:
    """Drives one real browser session through a declarative search recipe."""

    def __init__(self, provider_id: str, recipe: dict, base_url: str = "", ownership: str = "worker") -> None:
        self.provider_id = provider_id
        self.recipe = dict(recipe or {})
        self.base_url = (base_url or "").rstrip("/")
        self.session: BrowserSession | None = None
        self.ownership: str = ownership  # P03-001: worker | task | user
        self._closed = False

    # ---------- session lifecycle ----------
    async def _ensure_session(self) -> BrowserSession:
        if self.session is None or not await self.session.is_alive():
            self.session = await MANAGER.new_session(task_label=f"browser-search:{self.provider_id}")
        return self.session

    async def close(self) -> None:
        """P03-001: idempotent close; never closes a user-owned session."""
        if self._closed or self.ownership == "user":
            return
        self._closed = True
        if self.session is not None:
            sess, self.session = self.session, None
            await sess.close()

    def transfer_ownership(self, to: str) -> None:
        """P03-002: e.g. the user takes over mid-search — worker must NOT auto-close."""
        self.ownership = to
        if to == "user":
            self._closed = True  # keep session alive, worker no longer owns it

    # ---------- helpers ----------
    def _abs(self, path_or_url: str) -> str:
        return resolve_url(self.base_url, path_or_url)

    @staticmethod
    def _target(css: str) -> LocatorTarget:
        return LocatorTarget(css=css)

    def _raise_if_intervention(self, where: str) -> None:
        """P15-004: never keep acting once the page demands a human step."""
        s = self.session
        if s is not None and s.state is BrowserSessionState.WAITING_USER:
            iv = s.intervention or {}
            raise MetisError(
                "USER_INTERVENTION_REQUIRED",
                f"browser search stopped: {iv.get('kind', 'intervention')} detected ({where}); "
                "complete the step manually, then retry",
                provider_id=self.provider_id,
                details={"where": where, "trigger": iv.get("trigger"), "url": iv.get("url")},
            )

    # ---------- recipe execution ----------
    async def search(self, query: str, limit: int = 10) -> list[DatasetCandidate]:
        """Full recipe run: open search page -> submit query -> collect -> normalize."""
        await self._ensure_session()
        self._raise_if_intervention("before search")  # a hijacked session must never be driven
        await self._submit_query(query)

        max_pages = max(1, int(self.recipe.get("max_pages") or 1))
        links: list[dict] = []
        seen: set[str] = set()
        for page_no in range(max_pages):
            found = await self.extract_results()
            new = [r for r in found if r["href"] not in seen]
            if not new:  # no fresh results on this page -> stop paging
                break
            seen.update(r["href"] for r in new)
            links.extend(new)
            self._raise_if_intervention("reading results")
            if page_no + 1 >= max_pages or not await self.next_page():
                break
            self._raise_if_intervention("pagination")

        candidates: list[DatasetCandidate] = []
        for link in links[:limit]:
            meta: dict[str, Any] = {}
            try:
                meta = await self.extract_metadata(link["href"])
            except MetisError:
                raise
            except Exception as e:  # noqa: BLE001 — one bad detail page never kills the search
                self._raise_if_intervention("result detail page")
                log.warning_ctx("result metadata extraction failed", provider_id=self.provider_id, url=link["href"], error=str(e)[:200])
            candidates.append(self._to_candidate(link, meta))

        REPO.add_ui_event(
            "browser_search.completed",
            provider_id=self.provider_id,
            payload={"n_results": len(candidates), "urls": [c.sources[0].source_url for c in candidates], "query": query[:200]},
        )
        return candidates

    async def _submit_query(self, query: str) -> None:
        s = await self._ensure_session()
        template = self.recipe.get("search_url")
        if template:  # direct-result URL template: navigate, no typing needed
            await s.navigate(self._abs(template).replace("{query}", quote(query, safe="")))
            self._raise_if_intervention("search page loaded")
            return
        home = self.recipe.get("home_url")
        if not home:
            raise MetisError("STATE_INVALID", f"browser search recipe for {self.provider_id} lacks home_url/search_url", provider_id=self.provider_id)
        await s.navigate(self._abs(home))
        self._raise_if_intervention("search page loaded")
        box = self.recipe.get("search_box")
        if box:
            await s.type_text(self._target(box), query)
            self._raise_if_intervention("typing query")
        submit = self.recipe.get("submit")
        if submit:
            await s.click(self._target(submit))
        else:
            await s.press_key("Enter")
        self._raise_if_intervention("submitting query")

    async def extract_results(self) -> list[dict]:
        """Read the current result list as {href, text} pairs (recipe: result_card)."""
        s = await self._ensure_session()
        css = self.recipe.get("result_card") or "a"
        rows = await s.page.evaluate(
            r"""(css) => Array.from(document.querySelectorAll(css))
                .map(a => ({href: a.href || '', text: (a.textContent || '').trim().replace(/\s+/g, ' ')}))
                .filter(r => r.href && r.href.startsWith('http') && !r.href.endsWith('#'))""",
            css,
        )
        return [{"href": r["href"], "text": r.get("text", "")} for r in rows]

    async def next_page(self) -> bool:
        """P15-003: follow the recipe's next-page control; False when exhausted/absent."""
        s = self.session
        css = self.recipe.get("next_page")
        if not css or s is None:
            return False
        try:
            if await s.page.locator(css).count() == 0:
                return False
        except Exception:  # noqa: BLE001
            return False
        await s.click(self._target(css))
        self._raise_if_intervention("pagination")
        return True

    async def open_result(self, url: str) -> dict:
        """Navigate to one result/detail page (absolute or recipe-relative URL)."""
        s = await self._ensure_session()
        self._raise_if_intervention("opening result")
        info = await s.navigate(self._abs(url))
        self._raise_if_intervention("result page loaded")
        return {"url": s.page.url, "title": await s.page.title(), "status": info.get("status")}

    async def extract_metadata(self, url: str) -> dict:
        """Open a result page and pull title/description/direct file link (P15-005)."""
        info = await self.open_result(url)
        s = self.session
        assert s is not None
        data = await s.page.evaluate(
            r"""() => {
                const h1 = document.querySelector('h1');
                const desc = document.querySelector('meta[name="description"]');
                const fileLink = Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.getAttribute('href') || '')
                    .find(h => /\.(csv|tsv|xlsx?|json|jsonl|parquet|dta|sav|zip|gz|tar|nc)([?#]|$)/i.test(h));
                return {h1: h1 ? h1.textContent.trim() : '', description: desc ? desc.content : '', file: fileLink || null};
            }"""
        )
        meta = {
            "url": info["url"],
            "title": data.get("h1") or info["title"],
            "description": data.get("description") or "",
            "direct_file_url": None,
            "file_format": None,
        }
        if data.get("file"):
            furl = urljoin(info["url"], data["file"])
            meta["direct_file_url"] = furl
            meta["file_format"] = guess_format_from_url(furl)
        return meta

    def _to_candidate(self, link: dict, meta: dict | None = None) -> DatasetCandidate:
        url = link["href"]
        ref = urlparse(url).path.rsplit("/", 1)[-1] or url
        meta = meta or {}
        return mk_candidate(
            self.provider_id,
            meta.get("title") or link.get("text") or ref,
            url,
            description=meta.get("description") or "",
            source_ref=ref,
            direct_file_url=meta.get("direct_file_url"),
            file_format=meta.get("file_format"),
            access_mode="browser",
        )
