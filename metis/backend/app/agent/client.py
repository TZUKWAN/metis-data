"""OpenAI-compatible model client (P01-002/003).

- Config from env: METIS_LLM_BASE_URL / METIS_LLM_API_KEY / METIS_LLM_MODEL /
  METIS_LLM_REASONING_EFFORT / METIS_LLM_TIMEOUT / METIS_LLM_MAX_RETRIES.
- Unset config → AgentError CONFIG_MISSING (clear, actionable).
- Bounded retries with exponential backoff; 429 respects Retry-After.
- Error classification: AUTH_ERROR / RATE_LIMITED / TIMEOUT / SERVER_ERROR / BAD_RESPONSE.
- The API key is registered with the log-redaction registry and never logged.
"""
from __future__ import annotations

import asyncio
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.errors import MetisError
from app.core.logging import get_logger

log = get_logger("agent.client")


class AgentError(MetisError):
    def __init__(self, code: str, message: str, **kw: Any) -> None:
        super().__init__(code, message, **kw)


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    reasoning_effort: str | None
    timeout: float
    max_retries: int

    @classmethod
    def from_env(cls) -> LLMConfig:
        base = os.environ.get("METIS_LLM_BASE_URL", "").strip()
        key = os.environ.get("METIS_LLM_API_KEY", "").strip()
        model = os.environ.get("METIS_LLM_MODEL", "").strip()
        if not base or not model:
            missing = [n for n, v in (("METIS_LLM_BASE_URL", base), ("METIS_LLM_MODEL", model)) if not v]
            raise AgentError(
                "CONFIG_MISSING",
                f"LLM not configured: set {', '.join(missing)} (+ METIS_LLM_API_KEY if the endpoint requires auth). Rule-based fallback is still available for requirement parsing.",
            )
        return cls(
            base_url=base.rstrip("/"),
            api_key=key,
            model=model,
            reasoning_effort=os.environ.get("METIS_LLM_REASONING_EFFORT", "").strip() or None,
            timeout=float(os.environ.get("METIS_LLM_TIMEOUT", "120")),
            max_retries=int(os.environ.get("METIS_LLM_MAX_RETRIES", "2")),
        )


class LLMClient:
    """Minimal, vendor-neutral OpenAI-compatible chat client."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.cfg = config or LLMConfig.from_env()
        if self.cfg.api_key:
            from app.core.logging import register_secret

            register_secret(self.cfg.api_key)  # masked in every log/error

    async def complete_json(self, system: str, user: str, *, temperature: float = 0.1) -> dict[str, Any]:
        """Chat completion constrained to a JSON object; returns parsed dict."""
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if self.cfg.reasoning_effort:
            payload["reasoning_effort"] = self.cfg.reasoning_effort

        attempt = 0
        started = time.monotonic()
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self.cfg.timeout) as client:
                    headers = {"Authorization": f"Bearer {self.cfg.api_key}"} if self.cfg.api_key else {}
                    resp = await client.post(f"{self.cfg.base_url}/chat/completions", json=payload, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt <= self.cfg.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise AgentError("TIMEOUT", f"LLM request failed after {attempt} attempts: {type(exc).__name__}", retryable=True) from exc
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", "2"))
                if attempt <= self.cfg.max_retries:
                    log.warning_ctx("llm rate limited", retry_after=wait)
                    await asyncio.sleep(min(wait, 60))
                    continue
                raise AgentError("PROVIDER_RATE_LIMITED", "LLM rate limited; retries exhausted", retryable=True)
            if resp.status_code in (401, 403):
                raise AgentError("AUTH_ERROR", f"LLM endpoint rejected credentials (HTTP {resp.status_code}); check METIS_LLM_API_KEY", retryable=False)
            if resp.status_code >= 500:
                if attempt <= self.cfg.max_retries:
                    await asyncio.sleep(self._backoff(attempt))
                    continue
                raise AgentError("PROVIDER_HTTP_ERROR", f"LLM endpoint HTTP {resp.status_code}; retries exhausted", retryable=True)
            if resp.status_code != 200:
                raise AgentError("PROVIDER_HTTP_ERROR", f"LLM endpoint HTTP {resp.status_code}: {resp.text[:200]}", retryable=False)

            try:
                content = resp.json()["choices"][0]["message"]["content"]
            except Exception as exc:  # noqa: BLE001
                raise AgentError("BAD_RESPONSE", "LLM response missing choices[0].message.content", retryable=True) from exc
            try:
                result = json_loads(content)
            except Exception as exc:  # noqa: BLE001
                raise AgentError("BAD_RESPONSE", "LLM content is not valid JSON", retryable=True) from exc
            log.info_ctx("llm complete", model=self.cfg.model, attempt=attempt, duration_s=round(time.monotonic() - started, 1))
            return result

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(2 ** attempt + random.random(), 30)


def json_loads(text: str | dict) -> dict:
    import json

    if isinstance(text, dict):
        return text
    # tolerate markdown fences some models add despite response_format
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.startswith("json"):
            t = t[4:]
    return json.loads(t)
