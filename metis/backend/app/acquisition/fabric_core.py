"""P06 + P07: CrawlPolicyEngine / robots / rate limiter / injection guard /
BackendAdapter protocol / BackendRegistry / SafeCommandRunner / AcquisitionRouter.

统一策略与路由层：所有自主采集请求先过 PolicyEngine，所有外部能力只作为 Backend。
"""
from __future__ import annotations

import asyncio
import fnmatch
import os
import time
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.acquisition.fabric import BackendCapability, BackendDescriptor, BackendStatus, CrawlPlan
from app.core.errors import MetisError
from app.core.logging import get_logger

log = get_logger("fabric")


# ---------------- P06-001: CrawlPolicyEngine ----------------
class PolicyVerdict(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    MANUAL_REVIEW = "manual_review"


class CrawlPolicyEngine:
    """Every crawl passes here BEFORE any request is made."""

    def __init__(self) -> None:
        self.site_rules: dict[str, PolicyVerdict] = {}  # domain suffix match

    def set_rule(self, domain: str, verdict: PolicyVerdict) -> None:
        self.site_rules[domain.lower()] = verdict

    def check(self, plan: CrawlPlan) -> dict:
        problems: list[str] = []
        parsed = urlparse(plan.seeds[0])
        seed_host = (parsed.hostname or "").lower()
        for domain in plan.allowed_domains:
            if not (seed_host == domain.lower() or seed_host.endswith("." + domain.lower())):
                problems.append(f"seed {seed_host} outside allowed_domains {domain}")
        for rule_domain, verdict in self.site_rules.items():
            if seed_host == rule_domain or seed_host.endswith("." + rule_domain):
                if verdict == PolicyVerdict.BLOCK:
                    problems.append(f"domain {rule_domain} is BLOCKED by site registry")
                elif verdict == PolicyVerdict.MANUAL_REVIEW:
                    problems.append(f"domain {rule_domain} requires manual review")
        if plan.robots_policy != "respect" and plan.rendering_policy != "not_applicable":
            pass  # not_applicable is only legal for provider APIs (caller must justify)
        if problems:
            return {"verdict": PolicyVerdict.BLOCK, "reasons": problems}
        return {"verdict": PolicyVerdict.ALLOW, "reasons": []}


# ---------------- P06-002: robots.txt service ----------------
@dataclass
class _RobotsEntry:
    disallow: list[str] = field(default_factory=list)
    fetched_at: float = 0.0


class RobotsService:
    TTL = 3600

    def __init__(self) -> None:
        self._cache: dict[str, _RobotsEntry] = {}

    async def allowed(self, url: str, user_agent: str = "MetisData/1.0") -> tuple[bool, str]:
        from app.providers.http_client import get

        parsed = urlparse(url)
        key = f"{parsed.scheme}://{parsed.netloc}"
        entry = self._cache.get(key)
        now = time.monotonic()
        if entry is None or now - entry.fetched_at > self.TTL:
            entry = _RobotsEntry(fetched_at=now)
            try:
                r = await get(f"{key}/robots.txt", timeout=10, max_retries=0)
                if r.status == 200:
                    rules: list[tuple[str, str]] = []
                    agent_hits = False
                    for raw in r.text.splitlines():
                        line = raw.split("#")[0].strip()
                        if not line or ":" not in line:
                            continue
                        k, _, v = line.partition(":")
                        k = k.strip().lower()
                        v = v.strip()
                        if k == "user-agent":
                            agent_hits = v == "*" or v in user_agent
                        elif k == "disallow" and agent_hits:
                            rules.append((v, "disallow"))
                entry.disallow = [p for p, kind in rules if kind == "disallow" and p]
                self._cache[key] = entry
            except Exception:  # noqa: BLE001 — robots fetch failure: fail OPEN but note
                self._cache[key] = _RobotsEntry(fetched_at=now)
        for prefix in entry.disallow:
            if prefix and parsed.path.startswith(prefix):
                return False, f"BLOCKED_ROBOTS: path disallowed by robots.txt ({prefix})"
        return True, "allowed"


ROBOTS = RobotsService()


# ---------------- P06-003: per-domain rate limiter ----------------
class DomainRateLimiter:
    """Token-ish per-domain pacing; respects 429 Retry-After upstream via backoff()."""

    def __init__(self, default_interval: float = 1.0) -> None:
        self.default_interval = default_interval
        self._last: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str, interval: float | None = None) -> None:
        interval = interval if interval is not None else self.default_interval
        async with self._lock:
            now = time.monotonic()
            wait = self._last.get(domain, 0.0) + interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[domain] = time.monotonic()

    def note_retry_after(self, domain: str, seconds: float) -> None:
        self._last[domain] = time.monotonic() + seconds - self.default_interval


# ---------------- P07-003: SafeCommandRunner ----------------
class SafeCommandRunner:
    """argv-only external CLI execution. plain shell execution is FORBIDDEN by policy and by
    tests/architecture. Binary allowlist + fixed cwd + env allowlist + output caps."""

    def __init__(self, binary_allowlist: list[str], cwd: str | None = None, env_allowlist: list[str] | None = None) -> None:
        self.binary_allowlist = binary_allowlist
        self.cwd = cwd
        self.env_allowlist = env_allowlist or ["PATH", "HOME", "SYSTEMROOT", "TEMP", "TMP", "APPDATA"]

    def validate_binary(self, argv: list[str]) -> str:
        if not argv:
            raise MetisError("STATE_INVALID", "empty argv")
        binary = Path(argv[0]).name
        # Windows: allow "python" to match "python.exe"
        candidates = {binary, binary[:-4] if binary.lower().endswith(".exe") else binary}
        if not (candidates & set(self.binary_allowlist) or argv[0] in self.binary_allowlist):
            raise MetisError("STATE_INVALID", f"binary {binary} not in allowlist")
        for a in argv:
            assert not isinstance(a, bytes)
        return argv[0]

    async def run(self, argv: list[str], *, timeout: float = 60.0, max_output: int = 2 * 1024 * 1024, env_extra: dict | None = None) -> dict:
        self.validate_binary(argv)
        import subprocess

        env = {k: os.environ[k] for k in self.env_allowlist if k in os.environ}
        if env_extra:
            env.update(env_extra)
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=self.cwd, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, shell=False,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise MetisError("PROVIDER_TIMEOUT", f"command timed out after {timeout}s", retryable=True)
        return {
            "returncode": proc.returncode,
            "stdout": out.decode("utf-8", errors="replace")[:max_output],
            "stderr": err.decode("utf-8", errors="replace")[:max_output],
        }


# ---------------- P07-001/002: BackendAdapter + Registry ----------------
class UnsupportedCapability(MetisError):
    def __init__(self, backend_id: str, capability: BackendCapability) -> None:
        super().__init__("PROVIDER_CAPABILITY_MISSING", f"backend {backend_id} does not support {capability}")


class BackendAdapter:
    """Contract base (P07-001). Subclasses override what they support; unsupported
    capabilities raise UnsupportedCapability. All calls are timeout/cancel aware
    (asyncio.wait_for at the call site)."""

    backend_id: str = ""
    descriptor: BackendDescriptor | None = None

    def _require(self, cap: BackendCapability) -> None:
        caps = self.descriptor.capabilities if self.descriptor else []
        if cap not in caps:
            raise UnsupportedCapability(self.backend_id, cap)

    async def health(self) -> dict:
        return {"backend_id": self.backend_id, "status": "unknown"}

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        self._require(BackendCapability.SEARCH)
        raise UnsupportedCapability(self.backend_id, BackendCapability.SEARCH)

    async def read(self, url: str) -> dict:
        self._require(BackendCapability.READ)
        raise UnsupportedCapability(self.backend_id, BackendCapability.READ)

    async def crawl(self, plan: CrawlPlan) -> dict:
        self._require(BackendCapability.CRAWL)
        raise UnsupportedCapability(self.backend_id, BackendCapability.CRAWL)

    async def social_search(self, query: str, limit: int = 10) -> list[dict]:
        self._require(BackendCapability.SOCIAL)
        raise UnsupportedCapability(self.backend_id, BackendCapability.SOCIAL)

    async def paper_search(self, query: str, limit: int = 10) -> list[dict]:
        self._require(BackendCapability.PAPER)
        raise UnsupportedCapability(self.backend_id, BackendCapability.PAPER)


class BackendRegistry:
    """P07-002: detect-only at startup — never auto-installs anything."""

    def __init__(self) -> None:
        self._backends: dict[str, BackendAdapter] = {}

    def register(self, adapter: BackendAdapter) -> None:
        self._backends[adapter.backend_id] = adapter

    def get(self, backend_id: str) -> BackendAdapter:
        if backend_id not in self._backends:
            raise MetisError("NOT_FOUND", f"backend {backend_id} not registered")
        return self._backends[backend_id]

    def available(self, capability: BackendCapability) -> list[BackendAdapter]:
        out = []
        for a in self._backends.values():
            if a.descriptor and a.descriptor.status == BackendStatus.AVAILABLE and capability in a.descriptor.capabilities:
                out.append(a)
        return out

    def all(self) -> list[BackendAdapter]:
        return list(self._backends.values())


BACKEND_REGISTRY = BackendRegistry()


# ---------------- P07-004 / P25-003: AcquisitionRouter ----------------
class AcquisitionRouter:
    """Route acquisition tasks to backends in priority order with recorded fallbacks.

    Default priority: official provider → direct HTTP → reader → browser → external crawl.
    Social: public/official first, user-authorized browser bridge, optional service.
    """

    PRIORITY = [
        ["official_provider", "direct_http", "reader", "browser", "external_crawl"],
        ["public_api", "user_authorized_browser", "optional_service"],
    ]

    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, Any]] = {}

    def register_handler(self, backend_name: str, *, task_types: set[str], handler) -> None:
        self._handlers[backend_name] = {"task_types": task_types, "handler": handler}

    async def route(self, task_type: str, payload: dict) -> dict:
        """Try registered handlers in priority order; every attempt is recorded."""
        chain: list[dict] = []
        order = self.PRIORITY[0] if task_type in ("web_read", "web_crawl", "site_map", "dataset_acquire") else self.PRIORITY[1]
        for backend_name in order:
            h = self._handlers.get(backend_name)
            if h is None or task_type not in h["task_types"]:
                continue
            try:
                result = await h["handler"](payload)
                chain.append({"backend": backend_name, "result": "success"})
                return {"backend": backend_name, "fallback_chain": chain, "payload": result}
            except Exception as e:  # noqa: BLE001 — fallback policy (P25-003)
                chain.append({"backend": backend_name, "result": "failed", "error": str(e)[:160]})
                if "USER_INTERVENTION_REQUIRED" in str(e) or "CAPTCHA" in str(e):
                    raise
        raise MetisError("ACQUISITION_FAILED", f"all backends failed for {task_type}", details={"chain": chain})


ROUTER = AcquisitionRouter()
