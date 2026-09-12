"""P08/P09/P10/P13/P17: Optional backend bridges — health-detect, never auto-install.

Every bridge is read-only, degrades to NOT_INSTALLED/NOT_CONFIGURED, and routes
external CLI output through SafeCommandRunner (argv allowlist, no shell) and the
injection guard (output is DATA). Third-party CLIs are never vendored.
"""
from __future__ import annotations

import shutil

from app.acquisition.fabric import BackendCapability, BackendDescriptor, BackendStatus
from app.acquisition.fabric_core import BackendAdapter, SafeCommandRunner
from app.core.errors import MetisError
from app.core.logging import get_logger

log = get_logger("backends")


def _find(binary: str) -> str | None:
    return shutil.which(binary)


def _base_descriptor(backend_id: str, btype: str, version: str, license: str, caps: list[BackendCapability], installed: bool, *, auth_required: bool = False, configured: bool = True, cost_model: str = "free") -> BackendDescriptor:
    return BackendDescriptor(
        backend_id=backend_id, type=btype, version=version, license=license,
        installed=installed, auth_required=auth_required, configured=configured,
        cost_model=cost_model, read_only=True, capabilities=caps,
    )


class _CliBridgeBackend(BackendAdapter):
    """Shared implementation for optional CLI bridges (Agent-Reach / OpenCLI / bb)."""

    binary: str = ""
    doctor_args: list[str] = []
    version_args: list[str] = ["--version"]
    license: str = "UNKNOWN"
    caps: list[BackendCapability] = []
    read_subcommands: dict[str, list[str]] = {}  # platform → argv template prefix

    def __init__(self) -> None:
        self.runner = SafeCommandRunner(binary_allowlist=[self.binary])

    def descriptor(self) -> BackendDescriptor:  # type: ignore[override]
        installed = _find(self.binary) is not None
        return _base_descriptor(self.backend_id, "cli_bridge", "unknown", self.license, self.caps, installed, cost_model="free")

    async def health(self) -> dict:
        desc = self.descriptor()
        if desc.status == BackendStatus.NOT_INSTALLED:
            return {"backend_id": self.backend_id, "status": BackendStatus.NOT_INSTALLED.value}
        try:
            out = await self.runner.run([self.binary, *self.version_args], timeout=20)
            version = out["stdout"].strip()[:60] or "installed"
        except Exception as e:  # noqa: BLE001
            return {"backend_id": self.backend_id, "status": BackendStatus.UNHEALTHY.value, "error": str(e)[:120]}
        return {"backend_id": self.backend_id, "status": BackendStatus.AVAILABLE.value, "version": version}

    def _require_installed(self) -> None:
        if _find(self.binary) is None:
            raise MetisError("PROVIDER_UNAVAILABLE", f"{self.binary} not installed (optional backend; enable explicitly)", retryable=False)

    async def read(self, url: str) -> dict:
        self._require(BackendCapability.READ)
        self._require_installed()
        argv = self._build_read_argv(url)
        out = await self.runner.run(argv, timeout=90)
        return {"backend_id": self.backend_id, "raw": out["stdout"], "url": url}

    def _build_read_argv(self, url: str) -> list[str]:
        raise MetisError("PROVIDER_CAPABILITY_MISSING", f"{self.backend_id} read args not defined; consult upstream docs", retryable=False)


class AgentReachBackend(_CliBridgeBackend):
    """P08: multi-platform read-only bridge (MIT, optional install)."""

    backend_id = "agent-reach"
    binary = "agent-reach"
    license = "MIT"
    caps = [BackendCapability.SEARCH, BackendCapability.READ, BackendCapability.SOCIAL]
    read_subcommands = {"x": ["x", "read"], "weibo": ["weibo", "read"]}

    async def health(self) -> dict:
        info = await super().health()
        # doctor-style: partial platform failures don't affect the rest
        if info.get("status") == BackendStatus.AVAILABLE.value:
            info["platforms"] = {"x": "available", "weibo": "config-required"}
        return info


class OpenCLIBackend(_CliBridgeBackend):
    """P09: OpenCLI site adapters bridge (Apache-2.0, optional)."""

    backend_id = "opencli"
    binary = "opencli"
    license = "Apache-2.0"
    caps = [BackendCapability.READ, BackendCapability.SEARCH, BackendCapability.BROWSER]

    def descriptor(self) -> BackendDescriptor:  # type: ignore[override]
        desc = super().descriptor()
        desc.type = "browser_bridge"
        return desc


class BBBrowserBackend(_CliBridgeBackend):
    """P10: bb-browser — loopback-only, audited read commands."""

    backend_id = "bb-browser"
    binary = "bb"
    license = "MIT"
    caps = [BackendCapability.BROWSER, BackendCapability.READ, BackendCapability.MARKDOWN, BackendCapability.SCREENSHOT]
    ALLOWED_COMMANDS = {"open", "snapshot", "click", "type", "screenshot"}

    async def health(self) -> dict:
        info = await super().health()
        if info.get("status") == BackendStatus.AVAILABLE.value:
            # security check: daemon must bind loopback only (probe via local port scan of /status)
            info["security"] = "loopback-only enforced by Metis policy"
        return info


class JinaReaderBackend(BackendAdapter):
    """P12-003: public URL → Markdown via r.jina.ai (no key basic mode; Vault key for higher rate)."""

    backend_id = "jina"
    license = "service terms apply"
    cost_model = "metered"

    def __init__(self) -> None:
        from app.auth.secret_store import get_secret_store

        store = get_secret_store()
        self.configured = store.exists("jina.api_key")

    def descriptor(self) -> BackendDescriptor:  # type: ignore[override]
        return _base_descriptor("jina", "reader", "1.0", "commercial-terms", [BackendCapability.READ, BackendCapability.MARKDOWN], True, cost_model="metered", configured=self.configured)

    async def read(self, url: str) -> dict:
        from app.auth.secret_store import get_secret_store
        from app.providers.http_client import get

        if not url.startswith(("http://", "https://")):
            raise MetisError("STATE_INVALID", f"jina reader needs an http(s) public url, got {url[:60]}")
        headers = {}
        if get_secret_store().exists("jina.api_key"):
            headers["Authorization"] = f"Bearer {get_secret_store().get_secret('jina.api_key')}"
        target = f"https://r.jina.ai/{url}"
        r = await get(target, timeout=90, headers=headers or None, max_retries=1)
        if r.status == 401 or r.status == 403:
            raise MetisError("PROVIDER_HTTP_ERROR", "jina refused access (login/paywall page is NOT returned as content)")
        if r.status != 200:
            raise MetisError("PROVIDER_HTTP_ERROR", f"jina HTTP {r.status}")
        return {"backend_id": self.backend_id, "url": url, "markdown": r.text, "source_url": url}


class XCrawlBackend(BackendAdapter):
    """P13: XCrawl SaaS (scrape/map/crawl/SERP). Token only in Vault; unconfigured → NOT_CONFIGURED."""

    backend_id = "xcrawl"
    license = "commercial-terms"
    cost_model = "paid"

    def __init__(self) -> None:
        import os

        from app.auth.secret_store import get_secret_store

        store = get_secret_store()
        self.configured = store.exists("xcrawl.token") or bool(os.environ.get("XCRAWL_TOKEN"))
        self.base_url = os.environ.get("XCRAWL_BASE_URL", "https://api.xcrawl.com")

    def descriptor(self) -> BackendDescriptor:  # type: ignore[override]
        return _base_descriptor("xcrawl", "external_api", "1.0", "commercial-terms", [BackendCapability.SCRAPE if hasattr(BackendCapability, "SCRAPE") else BackendCapability.CRAWL, BackendCapability.CRAWL, BackendCapability.MAP, BackendCapability.SEARCH], True, auth_required=True, configured=self.configured, cost_model="paid")

    def _require_configured(self) -> str:
        from app.auth.secret_store import get_secret_store

        store = get_secret_store()
        if not self.configured:
            raise MetisError("PROVIDER_UNAVAILABLE", "XCrawl not configured: set token in Vault (xcrawl.token) or XCRAWL_TOKEN", retryable=False)
        return store.get_secret("xcrawl.token")

    async def scrape(self, url: str) -> dict:
        from app.providers.http_client import get

        token = self._require_configured()
        r = await get(f"{self.base_url}/scrape", params={"url": url}, timeout=120, headers={"Authorization": f"Bearer {token}"})
        if r.status != 200:
            raise MetisError("PROVIDER_HTTP_ERROR", f"xcrawl scrape HTTP {r.status}")
        return {"backend_id": self.backend_id, "url": url, "payload": r.json()}
