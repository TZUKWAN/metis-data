"""AuthorizedAccessContext (Phase E): secret-free, normalized access credentials for acquisition.

Hard rules:
- the context NEVER carries secret values (passwords, raw cookie values, tokens);
  it carries vault key references (`*_ref`) plus a non-sensitive cookie digest
  (names + counts only) so the run stays auditable without leaking credentials;
- actual HTTP credential material is resolved at transport time by
  app.auth.browser_auth_bridge.BrowserAuthBridge from the live browser session.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AuthType = Literal["anonymous", "browser_session", "cookie", "oauth", "api_key", "password_session"]


class AuthorizedAccessContext(BaseModel):
    """What acquisition may use to authenticate, without any secret material."""

    provider_id: str
    auth_type: AuthType = "anonymous"
    browser_session_id: str | None = None
    account_id: str | None = None
    cookie_jar_ref: str | None = None  # vault key reference (e.g. "<provider>.storage_state"), never plaintext
    token_ref: str | None = None  # vault key reference to an OAuth/bearer token
    api_key_ref: str | None = None  # vault key reference to an API key
    headers: dict[str, str] = Field(default_factory=dict)  # non-secret transport headers
    # cookie digest: name -> occurrence count in the session jar. Values are never stored here.
    cookie_summary: dict[str, int] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @classmethod
    async def from_browser_session(
        cls, session, provider_id: str, account_id: str | None = None
    ) -> AuthorizedAccessContext:
        """Build the context from a live browser session.

        Reads the session cookie jar only to record names + counts (digest);
        values stay in the browser/vault and are bridged at request time.
        """
        cookies: list[dict[str, Any]] = []
        try:
            cookies = await session.context.cookies()
        except Exception:  # noqa: BLE001 - session may be closed; digest stays empty
            cookies = []
        summary: dict[str, int] = {}
        for c in cookies:
            name = str(c.get("name") or "?")
            summary[name] = summary.get(name, 0) + 1
        return cls(
            provider_id=provider_id,
            auth_type="browser_session",
            browser_session_id=getattr(session, "session_id", None),
            account_id=account_id,
            cookie_jar_ref=f"{provider_id}.storage_state",
            cookie_summary=summary,
        )
