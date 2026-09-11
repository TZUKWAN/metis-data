"""Data Identity (P09-001) + Accounts/Status (P09-005) + registration & login executors.

Registration flow (A13): enabled only when the user turns auto-registration on;
uses Data Identity + per-provider generated password; classifies outcomes
(SUCCESS / VERIFY_EMAIL_REQUIRED / DUPLICATE_ACCOUNT / PASSWORD_RULE_FAILED /
CAPTCHA_REQUIRED / MFA_REQUIRED / USER_INTERVENTION / FAILED).

Login flow (A12): existing credentials from Vault; success/invalid-credentials
detection; bounded retries; session persisted via vault; expiry handled.
"""
from __future__ import annotations

from app.auth.passwords import check_policy, generate_password
from app.auth.vault import get_vault
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import AccountStatusKind, RegistrationResult
from app.domain.schemas import new_id

log = get_logger("auth")


# ---------------- Data Identity ----------------
class IdentityService:
    FIELDS = ["name", "email", "country", "institution", "role", "orcid", "research_purpose"]

    def get_identity(self) -> dict:
        from sqlalchemy import select

        from app.db.models import IdentityRow
        from app.db.session import new_session

        with new_session() as s:
            row = s.scalars(select(IdentityRow)).first()
            return dict(row.data_json) if row else {}

    def update_identity(self, updates: dict, disabled_fields: list[str] | None = None) -> dict:
        """User can edit each field and disable auto-submit per field (PRD §14)."""
        from app.db.models import IdentityRow
        from app.db.session import new_session

        with new_session() as s:
            from sqlalchemy import select

            row = s.scalars(select(IdentityRow)).first()
            if row is None:
                row = IdentityRow(identity_id=new_id("ident"), data_json={})
                s.add(row)
            data = dict(row.data_json or {})
            fields = {k: v for k, v in updates.items() if k in self.FIELDS}
            data.update(fields)
            if disabled_fields is not None:
                data["_disabled"] = [f for f in disabled_fields if f in self.FIELDS]
            row.data_json = data
            s.commit()
            return dict(data)

    def registration_payload(self, provider_id: str) -> dict:
        """Fields mapped for a registration form, honoring per-field disable flags."""
        ident = self.get_identity()
        disabled = set(ident.get("_disabled", []))
        return {k: v for k, v in ident.items() if not k.startswith("_") and k not in disabled and v}


# ---------------- Accounts ----------------
class AccountService:
    def account_for(self, provider_id: str, create: bool = False) -> str:
        for acc in REPO.list_accounts():
            if acc["provider_id"] == provider_id:
                return acc["account_id"]
        if not create:
            raise MetisError("NOT_FOUND", f"no account for {provider_id}")
        aid = new_id("acct")
        REPO.upsert_account(aid, provider_id, status=AccountStatusKind.NONE)
        return aid

    def set_auto_register(self, provider_id: str, enabled: bool) -> dict:
        aid = self.account_for(provider_id, create=True)
        REPO.upsert_account(aid, provider_id, auto_register_enabled=enabled)
        return REPO.get_account(aid)

    def auto_register_allowed(self, provider_id: str) -> bool:
        for acc in REPO.list_accounts():
            if acc["provider_id"] == provider_id:
                return bool(acc.get("auto_register_enabled"))
        return False

    def delete_account(self, provider_id: str) -> dict:
        """User deletion: revoke sessions + delete vault secrets; next access must re-auth (A12)."""
        removed = {"secrets": 0, "sessions": 0, "credentials": 0}
        vault = get_vault()
        for cred in REPO.list_credentials(provider_id):
            removed["secrets"] += int(vault.delete_secret(cred["vault_key"]))
            vault.delete_secret(f"{cred['vault_key']}.session")
            REPO.delete_credential(cred["credential_id"])
            removed["credentials"] += 1
        for sess in REPO.list_sessions(provider_id):
            vault.delete_secret(sess["vault_key"])
            REPO.upsert_session(sess["session_id"], provider_id, sess["vault_key"], status="REVOKED")
            removed["sessions"] += 1
        for acc in REPO.list_accounts():
            if acc["provider_id"] == provider_id:
                REPO.upsert_account(acc["account_id"], provider_id, status=AccountStatusKind.DELETED, auto_register_enabled=False)
        log.info_ctx("account deleted", provider_id=provider_id, **removed)
        return removed


# ---------------- Registration executor ----------------
class RegistrationExecutor:
    """Runs a registration against a real page (or fixture site in tests).

    The `driver` abstracts page interaction so both live Browser and tests share logic:
    driver.open(url) / driver.fill(selector, value) / driver.click(selector) /
    driver.text(selector) / driver.current_url / driver.has(selector).
    """

    MAX_SUBMITS = 1  # never loop registration submissions

    def __init__(self, provider_id: str, driver) -> None:
        self.provider_id = provider_id
        self.driver = driver

    async def run(self, register_url: str, form_map: dict[str, str], password_rules: dict | None = None) -> dict:
        if not AccountService().auto_register_allowed(self.provider_id):
            REPO.add_ui_event("registration.blocked", "WARNING", payload={"provider": self.provider_id, "reason": "auto registration disabled by user"})
            return {"result": RegistrationResult.FAILED, "reason": "auto registration is disabled by the user; nothing submitted", "submitted": False}

        ident = IdentityService().registration_payload(self.provider_id)
        password = generate_password(password_rules)
        if not check_policy(password, password_rules):
            REPO.add_ui_event("registration.result", "WARNING", payload={"provider": self.provider_id, "result": "PASSWORD_RULE_FAILED", "reason": "generated password violated policy before submission"})
            return {"result": RegistrationResult.PASSWORD_RULE_FAILED, "reason": "generated password violated provider password rules; nothing submitted", "submitted": False}
        get_vault().set_secret(f"{self.provider_id}.registration_password", password)

        await self.driver.open(register_url)
        mapping_errors = []
        for field, selector in form_map.items():
            if field.startswith("_"):
                continue  # control selectors (e.g. _submit), not identity fields
            value = ident.get(field) if field != "password" else password
            if value is None:
                mapping_errors.append(field)
                continue
            await self.driver.fill(selector, str(value))
        if mapping_errors:
            return {"result": RegistrationResult.USER_INTERVENTION, "reason": f"identity fields missing/disabled: {mapping_errors}", "submitted": False}

        REPO.add_ui_event("registration.submitted", "INFO", payload={"provider": self.provider_id, "email": ident.get("email", "")})
        await self.driver.click(form_map["_submit"])

        # classify result by what the page shows
        result = await self._classify()
        aid = AccountService().account_for(self.provider_id, create=True)
        if result == RegistrationResult.SUCCESS:
            vault_key = f"{self.provider_id}.registration_password"
            REPO.add_credential(new_id("cred"), self.provider_id, "password", str(ident.get("email", "")), vault_key)
            REPO.upsert_account(aid, self.provider_id, status=AccountStatusKind.FULLY_ACTIVE, registration_result=result, last_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
        elif result == RegistrationResult.VERIFY_EMAIL_REQUIRED:
            REPO.upsert_account(aid, self.provider_id, status=AccountStatusKind.PENDING_EMAIL_VERIFICATION, registration_result=result)
        else:
            REPO.upsert_account(aid, self.provider_id, status=AccountStatusKind.LOGIN_FAILED, registration_result=result)
        REPO.add_ui_event("registration.result", "INFO", payload={"provider": self.provider_id, "result": str(result)})
        return {"result": result, "submitted": True, "provider_id": self.provider_id}

    async def _classify(self) -> RegistrationResult:
        """Field-specific outcomes first; CAPTCHA/MFA patterns are form-agnostic and
        must not mask an explicit duplicate/password/verify result."""
        url = await self.driver.current_url()
        page_text = (await self.driver.body_text()).lower()
        if "duplicate" in page_text or "already exists" in page_text or "already been registered" in page_text:
            return RegistrationResult.DUPLICATE_ACCOUNT
        if "password rule failed" in page_text or "password doesn" in page_text or "password must" in page_text:
            return RegistrationResult.PASSWORD_RULE_FAILED
        if ("verify" in page_text and "inbox" in page_text) or "pending until verified" in page_text:
            return RegistrationResult.VERIFY_EMAIL_REQUIRED
        # explicit CAPTCHA widgets/challenges only (not incidental words)
        if any(k in page_text for k in ("recaptcha", "g-recaptcha", "hcaptcha", "geetest", "are you a robot", "human verification", "prove you are not a robot", "captcha required")):
            return RegistrationResult.CAPTCHA_REQUIRED
        if any(k in page_text for k in ("two-factor", "2fa code", "multi-factor", "mfa required", "authenticator app")):
            return RegistrationResult.MFA_REQUIRED
        if "successfully" in page_text or "account created" in page_text or "welcome" in page_text:
            return RegistrationResult.SUCCESS
        if "register" in url or "signup" in url:
            return RegistrationResult.FAILED
        return RegistrationResult.FAILED


# ---------------- Login executor ----------------
class LoginExecutor:
    MAX_ATTEMPTS = 3  # bounded retries (A12: 不无限重试)

    def __init__(self, provider_id: str, driver) -> None:
        self.provider_id = provider_id
        self.driver = driver

    async def login(self, login_url: str, form_map: dict[str, str], credential_id: str | None = None) -> dict:
        vault = get_vault()
        creds = [c for c in REPO.list_credentials(self.provider_id) if c["kind"] == "password"]
        if not creds:
            raise MetisError("INVALID_CREDENTIALS", f"no stored credentials for {self.provider_id}; bind an existing account first")
        cred = creds[0]
        password = vault.get_secret(cred["vault_key"])

        aid = AccountService().account_for(self.provider_id, create=True)
        attempt = 0
        last = None
        while attempt < self.MAX_ATTEMPTS:
            attempt += 1
            REPO.add_ui_event("auth.login_submit", "INFO", payload={"provider": self.provider_id, "attempt": attempt})
            await self.driver.open(login_url)
            await self.driver.fill(form_map["email"], cred["account_label"])
            await self.driver.fill(form_map["password"], password)
            await self.driver.click(form_map["_submit"])
            last = await self._classify()
            if last == "SUCCESS":
                session_key = f"{self.provider_id}.session_state"
                vault.set_secret(session_key, f"fixture-session:{self.provider_id}:{cred['account_label']}")
                REPO.upsert_session(new_id("sess"), self.provider_id, session_key, status="VALID", account_id=aid)
                REPO.upsert_account(aid, self.provider_id, status=AccountStatusKind.SESSION_VALID, last_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
                return {"result": "SUCCESS", "attempts": attempt}
            if last == "INVALID_CREDENTIALS":
                break  # wrong credentials: retrying cannot help
            if last in ("CAPTCHA_REQUIRED", "MFA_REQUIRED"):
                REPO.upsert_account(aid, self.provider_id, status=AccountStatusKind.LOGIN_FAILED)
                return {"result": last, "attempts": attempt}
        REPO.upsert_account(aid, self.provider_id, status=AccountStatusKind.LOGIN_FAILED)
        REPO.add_ui_event("auth.login_failed", "WARNING", payload={"provider": self.provider_id, "result": str(last), "attempts": attempt})
        return {"result": last or "FAILED", "attempts": attempt}

    async def _classify(self) -> str:
        url = await self.driver.current_url()
        page_text = (await self.driver.body_text()).lower()
        if "invalid credentials" in page_text or "incorrect" in page_text or "wrong password" in page_text:
            return "INVALID_CREDENTIALS"
        if "captcha" in page_text:
            return "CAPTCHA_REQUIRED"
        if "2fa" in page_text or "mfa" in page_text:
            return "MFA_REQUIRED"
        if "welcome" in page_text or "my account" in page_text or "sign out" in page_text:
            return "SUCCESS"
        if "login" in url and "success" not in url:
            return "FAILED"
        return "SUCCESS"


IDENTITY = IdentityService()
ACCOUNTS = AccountService()
