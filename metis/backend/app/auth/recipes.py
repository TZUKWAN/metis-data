"""Provider recipes (P05-004/P05-006/P03-007): provider-specific locators + flows.

These are DATA, provider-specific by necessity; the EXECUTION layer is shared
(LoginExecutor / RegistrationExecutor / browser search worker).
`fixture_site` recipes point at the local test fixture pages used in CI.
"""
from __future__ import annotations

PROVIDER_RECIPES: dict[str, dict] = {
    # ---- CI fixture (real flows against local pages) ----
    "fixture_site": {
        "login_url": "/pages/login.html",
        "login": {
            "email": "#email",
            "password": "#password",
            "submit": "#login-btn",
            "success_url_contains": "login_success",
            "failure_text": "invalid credentials",
        },
        "login_success_url": "/pages/login_success.html",
        "logged_in_selector": "#welcome-user",
        "logged_out_selector": "#login-form",
        "account_url": "/pages/login_success.html",
        "registration": {
            "url": "/pages/register.html",
            "fields": {"name": "#name", "email": "#email", "password": "#password"},
            "submit": "#reg-btn",
        },
        "password_policy": {"min_length": 8, "min_upper": 1, "min_lower": 1, "min_digit": 1},
    },
    # ---- real platform examples (used only with user-authorized accounts) ----
    "kaggle": {
        "login_url": "https://www.kaggle.com/account/login",
        "login": {
            "email": "input[name='email']",
            "password": "input[name='password']",
            "submit": "button[type='submit']",
            "success_url_contains": "kaggle.com",
            "failure_text": "invalid email or password",
        },
        "account_url": "https://www.kaggle.com/settings",
        "logged_in_selector": "div[data-e2e='avatar']",
        "password_policy": {"min_length": 8, "min_upper": 1, "min_lower": 1, "min_digit": 1},
        "notes": "registration uses CAPTCHA → auto-registration not attempted; existing account only",
    },
}


def resolve_url(base: str, path_or_url: str) -> str:
    if path_or_url.startswith("http"):
        return path_or_url
    return base.rstrip("/") + path_or_url
