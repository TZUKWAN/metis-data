"""P16 security acceptance (A10/A37): secrets scan rules, log redaction regression, vault semantics."""
from __future__ import annotations

import importlib.util
import logging

import pytest

import sys

from conftest import browser_run

WIN32_ONLY = pytest.mark.skipif(sys.platform != 'win32', reason='DPAPI vault is Windows-only')


def test_secrets_scan_rules_trigger():
    """A37: test secrets MUST trigger scan rules (and be classified as test triggers)."""
    spec = importlib.util.spec_from_file_location("secrets_scan", Path(__file__).resolve().parents[3] / "scripts" / "secrets_scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # each planted test secret triggers exactly the right rule
    assert mod.PATTERNS["aws_access_key"].search("key = AKIAIOSFODNN7EXAMPLE")
    assert mod.PATTERNS["github_pat"].search("token ghp_abc" + "0" * 36)
    pem_header = "-----BEGIN " + "RSA PRIVATE " + "KEY-----"  # built at runtime; never a real key
    assert mod.PATTERNS["private_key_block"].search(pem_header)
    assert mod.PATTERNS["generic_api_key_assignment"].search('api_key = "METIS-TEST-SECRET-0123456789"')

    # allowlist classifies the declared test marker as expected, not real
    snippet = 'api_key = "METIS-TEST-SECRET-0123456789"'
    m = mod.PATTERNS["generic_api_key_assignment"].search(snippet)
    assert m and any(marker.lower() in m.group(0).lower() for marker in mod.ALLOWLIST_MARKERS)


from pathlib import Path  # noqa: E402


def test_secrets_scan_repo_clean():
    """A37: current work tree + git-tracked files scan clean (exit 0)."""
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "scripts/secrets_scan.py"], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[3])
    assert r.returncode == 0, f"real secret findings:\n{r.stdout}"


def test_log_redaction_all_categories(temp_workspace, caplog):
    """A10: password / api key / token / cookie / Authorization / OTP masked in logs."""
    from app.core.logging import get_logger, redact, register_secret

    register_secret("Bearer live_token_abcdef012345")
    samples = [
        ("password=hunter2000x", "hunter2000x"),
        ("api_key: sk-1234567890abcdef", "sk-1234567890abcdef"),
        ('{"access_token": "tok_abcdef123456"}', "tok_abcdef123456"),
        ("cookie=SESSIONID=xyz999", "SESSIONID=xyz999"),
        ("Authorization: Bearer live_token_abcdef012345", "live_token_abcdef012345"),
        ("otp=998877", "998877"),
    ]
    for text, secret in samples:
        assert secret not in redact(text), f"leaked: {text}"
        assert "***MASKED***" in redact(text)

    logger = get_logger("sec")
    with caplog.at_level(logging.INFO):
        logger.info_ctx("browser typed", value="SuperSecret99!")
        logger.error_ctx("failed request", headers="Authorization: Bearer live_token_abcdef012345")
    assert "SuperSecret99!" not in caplog.text
    assert "live_token_abcdef012345" not in caplog.text


def test_browser_event_never_contains_secret(browser_session, fixture_server):
    """A10: typed password values are masked in the persisted browser action events."""
    from app.browser.runtime import LocatorTarget

    async def go():
        s = browser_session
        await s.navigate(f"{fixture_server}/pages/login.html")
        await s.type_text(LocatorTarget(css="#password"), "TopSecretPass42!", secret=True)
        events = [e.public(__import__("app.core.logging", fromlist=["redact"]).redact) for e in s.events if e.action == "type"]
        assert events and "TopSecretPass42!" not in str(events)

    browser_run(go())


@WIN32_ONLY
def test_vault_delete_and_unique_passwords(temp_workspace):
    """A10/A11: vault delete → unreadable; per-provider passwords unique & strong."""
    from app.auth.passwords import check_policy, generate_password
    from app.auth.vault import get_vault

    v = get_vault()
    v.set_secret("prov_a.password", "OneUniquePass-AAA-99")
    v.set_secret("prov_b.password", "TwoUniquePass-BBB-77")
    assert v.get_secret("prov_a.password") == "OneUniquePass-AAA-99"
    v.delete_secret("prov_a.password")
    with pytest.raises(Exception):
        v.get_secret("prov_a.password")

    passwords = {generate_password() for _ in range(8)}
    assert len(passwords) == 8  # no reuse
    assert all(check_policy(p) for p in passwords)
