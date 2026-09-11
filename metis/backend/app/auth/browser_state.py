"""Real browser session persistence (P03-004..008).

- storage_state (cookies + localStorage + origin storage) saved encrypted in the OS vault;
- restored into a fresh BrowserContext on next visit;
- real validity probing via provider recipe (logged_in_selector), not DB status;
- expired → SESSION_EXPIRED;
- OAuth credential model (P03-009).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel

from app.auth.secret_store import get_secret_store
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import AccountStatusKind
from app.domain.schemas import new_id

log = get_logger("auth.session")


# ---------------- P03-004: storage state record ----------------
class BrowserStateRecord(BaseModel):
    provider_id: str
    account_id: str | None = None
    created_at: str
    last_verified_at: str | None = None
    expires_hint: str | None = None
    vault_key: str


# ---------------- P03-005: save real storage_state ----------------
async def save_browser_state(session, provider_id: str, account_id: str | None = None, expires_hint: str | None = None) -> BrowserStateRecord:
    """Serialize the real Playwright context storage_state into the OS vault."""
    state = await session.context.storage_state()  # cookies + localStorage
    vault_key = f"{provider_id}.storage_state"
    get_secret_store().set_secret(vault_key, json.dumps(state))
    record = BrowserStateRecord(
        provider_id=provider_id,
        account_id=account_id,
        created_at=datetime.now(UTC).isoformat(),
        last_verified_at=datetime.now(UTC).isoformat(),
        expires_hint=expires_hint,
        vault_key=vault_key,
    )
    session_id = new_id("sess")
    REPO.upsert_session(session_id, provider_id, vault_key, status="VALID", account_id=account_id)
    REPO.add_ui_event("auth.storage_state_saved", payload={"provider": provider_id, "cookies": len(state.get("cookies", [])), "origins": len(state.get("origins", []))})
    log.info_ctx("storage state saved", provider_id=provider_id)
    return record


# ---------------- P03-006: restore into a fresh context ----------------
async def restore_browser_storage(context, provider_id: str) -> bool:
    """Load a previously saved storage_state into a (fresh) context. Returns True if restored."""
    vault_key = f"{provider_id}.storage_state"
    store = get_secret_store()
    if not store.exists(vault_key):
        return False
    state = json.loads(store.get_secret(vault_key))
    if hasattr(context, "add_cookies"):
        cookies = state.get("cookies", [])
        if cookies:
            await context.add_cookies(cookies)
        # localStorage / origin storage: inject via init script per origin
        for origin_block in state.get("origins", []):
            for item in origin_block.get("localStorage", []):
                script = (
                    f"try {{ window.localStorage.setItem({json.dumps(item['name'])}, {json.dumps(item['value'])}); }} catch (e) {{}}"
                )
                await context.add_init_script(script)
    log.info_ctx("storage state restored", provider_id=provider_id, cookies=len(state.get("cookies", [])))
    return True


# ---------------- P03-007/008: real validity probing ----------------
def get_recipe(provider_id: str) -> dict:
    from app.auth.recipes import PROVIDER_RECIPES

    return PROVIDER_RECIPES.get(provider_id, {})


async def probe_session_valid(session, provider_id: str, account_url: str | None = None, base_url: str | None = None) -> tuple[bool, str]:
    """Real probe: open the account page and check logged_in/logged_out selectors.

    Never trusts the DB status alone. Returns (valid, reason).
    Relative recipe URLs are resolved against base_url (fixture/test servers).
    """
    from app.auth.recipes import resolve_url

    recipe = get_recipe(provider_id)
    logged_in_sel = recipe.get("logged_in_selector")
    account_page = account_url or recipe.get("account_url") or recipe.get("login_success_url")
    if not logged_in_sel or not account_page:
        return False, "no recipe for provider; cannot probe"
    account_page = resolve_url(base_url, account_page) if not account_page.startswith("http") else account_page
    await session.page.goto(account_page, wait_until="domcontentloaded")
    await session._post_action_intervention_check()  # probe can hit login walls
    if await session.page.locator(logged_in_sel).count() > 0:
        return True, "logged_in_selector present"
    logged_out_sel = recipe.get("logged_out_selector")
    if logged_out_sel and await session.page.locator(logged_out_sel).count() > 0:
        return False, "logged_out_selector present"
    return False, "logged_in_selector absent"


async def ensure_valid_session(provider_id: str, make_session, base_url: str | None = None) -> tuple[bool, str, object | None]:
    """Full check: restore stored state into a fresh session and probe it.

    Returns (valid, reason, session). Marks SESSION_EXPIRED in DB when stale.
    """
    session = await make_session(f"session-check:{provider_id}")
    restored = await restore_browser_storage(session.context, provider_id)
    if not restored:
        return False, "no stored state", session
    valid, reason = await probe_session_valid(session, provider_id, base_url=base_url)
    if valid:
        return True, reason, session
    _mark_expired(provider_id, reason)
    return False, f"SESSION_EXPIRED: {reason}", session


def _mark_expired(provider_id: str, reason: str) -> None:
    for srow in REPO.list_sessions(provider_id):
        REPO.upsert_session(srow["session_id"], provider_id, srow["vault_key"], status="SESSION_EXPIRED")
    for acc in REPO.list_accounts():
        if acc["provider_id"] == provider_id:
            REPO.upsert_account(acc["account_id"], provider_id, status=AccountStatusKind.SESSION_EXPIRED)
    REPO.add_ui_event("auth.session_expired", "WARNING", payload={"provider": provider_id, "reason": reason})


# ---------------- P03-009: OAuth credential model ----------------
class OAuthCredential(BaseModel):
    provider_id: str
    account_identity: str
    access_token: str
    refresh_token: str | None = None
    expires_at: str | None = None
    scope: list[str] = []

    def save(self) -> None:
        get_secret_store().set_secret(f"{self.provider_id}.oauth", self.model_dump_json())
        REPO.add_credential(new_id("cred"), self.provider_id, "oauth", self.account_identity, f"{self.provider_id}.oauth")

    @classmethod
    def load(cls, provider_id: str) -> OAuthCredential | None:
        store = get_secret_store()
        if not store.exists(f"{provider_id}.oauth"):
            return None
        return cls(**json.loads(store.get_secret(f"{provider_id}.oauth")))

    def delete(self) -> None:
        get_secret_store().delete_secret(f"{self.provider_id}.oauth")


# ---------------- P03-010: full deletion ----------------
async def delete_browser_state(provider_id: str) -> dict:
    store = get_secret_store()
    removed = store.delete_secret(f"{provider_id}.storage_state")
    OAuthCredential.load(provider_id) and OAuthCredential.load(provider_id).delete()  # noqa: B018
    for srow in REPO.list_sessions(provider_id):
        store.delete_secret(srow["vault_key"])
        REPO.upsert_session(srow["session_id"], provider_id, srow["vault_key"], status="REVOKED")
    return {"storage_state_deleted": removed}
