"""P02-002/P02-004: BrowserSessionResolver + AuthContextResolver.

BrowserSessionResolver: live session first, else restore storage_state from the Vault
into a short-lived context and probe login; expired → SESSION_EXPIRED (never fake-auth).
AuthContextResolver: transiently dereference oauth/api_key/header vault refs at transport
time; expiry checked; values never logged or persisted.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.auth.browser_state import restore_browser_storage
from app.auth.secret_store import get_secret_store
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import AccountStatusKind

log = get_logger("access.resolver")


class BrowserSessionResolver:
    async def resolve(self, provider_id: str, browser_session_id: str | None, make_session) -> tuple[object | None, str]:
        """Returns (session|None, reason). Live session wins; otherwise Vault restore + probe."""
        from app.browser.runtime import MANAGER

        if browser_session_id:
            try:
                sess = MANAGER.get(browser_session_id)
                if await sess.is_alive():
                    return sess, "live_session"
            except MetisError:
                pass
        sess = await make_session(f"resume:{provider_id}")
        restored = await restore_browser_storage(sess.context, provider_id)
        if not restored:
            await sess.close()
            return None, "no_stored_state"
        from app.auth.browser_state import probe_session_valid

        ok, reason = await probe_session_valid(sess, provider_id)
        if not ok:
            for srow in REPO.list_sessions(provider_id):
                REPO.upsert_session(srow["session_id"], provider_id, srow["vault_key"], status="SESSION_EXPIRED")
            for acc in REPO.list_accounts():
                if acc["provider_id"] == provider_id:
                    REPO.upsert_account(acc["account_id"], provider_id, status=AccountStatusKind.SESSION_EXPIRED)
            await sess.close()
            return None, f"SESSION_EXPIRED: {reason}"
        return sess, "restored_session_valid"


class AuthContextResolver:
    """Transiently dereference vault refs for the HTTP client. Values never logged."""

    def resolve_oauth(self, provider_id: str) -> dict:
        from app.auth.browser_state import OAuthCredential

        cred = OAuthCredential.load(provider_id)
        if cred is None:
            return {}
        if cred.expires_at:
            try:
                exp = datetime.fromisoformat(cred.expires_at.replace("Z", "+00:00"))
                if exp <= datetime.now(UTC):
                    return {}
            except ValueError:
                pass
        return {"Authorization": f"Bearer {cred.access_token}"}

    def resolve_api_key(self, provider_id: str) -> dict:
        store = get_secret_store()
        for key in (f"{provider_id}.api_key", f"{provider_id}.apikey"):
            if store.exists(key):
                return {"X-API-Key": store.get_secret(key)}
        return {}

    def resolve_header_refs(self, provider_id: str, header_ref: str | None) -> dict:
        if not header_ref:
            return {}
        store = get_secret_store()
        if not store.exists(header_ref):
            return {}
        import json

        try:
            data = json.loads(store.get_secret(header_ref))
            return {str(k): str(v) for k, v in data.items() if str(k).lower() != "cookie"}
        except (ValueError, TypeError):
            return {}


RESOLVER = BrowserSessionResolver()
AUTH_RESOLVER = AuthContextResolver()
