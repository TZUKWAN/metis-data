"""BrowserAuthBridge (Phase F): bridges a live browser session into HTTP transport credentials.

The bridge is the ONLY place where browser cookie values are read for acquisition:
- to_http_cookies(): name/value pairs for httpx cookie injection (in-memory, never persisted);
- export_storage_state(): Playwright storage_state dict (same serialization idea as
  app.auth.browser_state.save_browser_state, but pure — returns the dict, writes nothing).
"""
from __future__ import annotations


class BrowserAuthBridge:
    async def to_http_cookies(self, session) -> dict[str, str]:
        """Extract cookie name/value pairs from the live browser context for an HTTP client."""
        cookies = await session.context.cookies()
        out: dict[str, str] = {}
        for c in cookies:
            name = c.get("name")
            if not name:
                continue
            out[str(name)] = str(c.get("value") or "")
        return out

    async def export_storage_state(self, session) -> dict:
        """Return the context storage_state (cookies + localStorage) as a plain dict.

        Mirrors browser_state.save_browser_state's serialization (settle waits, then
        context.storage_state()) but performs no vault write and no DB update.
        """
        try:
            await session.page.wait_for_load_state("domcontentloaded")
            await session.page.wait_for_timeout(300)
        except Exception:  # noqa: BLE001 - page may already be gone; snapshot what we can
            pass
        state = await session.context.storage_state()
        return state if isinstance(state, dict) else dict(state)


BRIDGE = BrowserAuthBridge()
