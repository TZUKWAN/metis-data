"""Provider Registry (P02-001/002): the single source of truth for provider capabilities.

- Loads providers.catalog.yaml (every PRD §6 platform).
- Exposes lookups and generates the UI Integration Matrix.
- Provider entries are only mutated via audits/adapters with evidence.
"""
from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.errors import MetisError
from app.domain.schemas import ProviderRecord

CATALOG_FILE = Path(__file__).resolve().parent / "providers.catalog.yaml"


class ProviderRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._providers: dict[str, ProviderRecord] = {}
        self.load()

    def load(self) -> None:
        with self._lock, CATALOG_FILE.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        providers = {}
        for entry in doc["providers"]:
            rec = ProviderRecord(**entry)
            providers[rec.provider_id] = rec
        self._providers = providers

    def save(self) -> None:
        """Persist registry mutations (audits) back to the YAML source of truth."""
        with self._lock:
            doc = {
                "version": "1.0",
                "updated": __import__("datetime").date.today().isoformat(),
                "providers": [json_safe(p.model_dump()) for p in self._providers.values()],
            }
            CATALOG_FILE.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # -- queries --
    def all(self) -> list[ProviderRecord]:
        return list(self._providers.values())

    def get(self, provider_id: str) -> ProviderRecord:
        rec = self._providers.get(provider_id)
        if rec is None:
            raise MetisError("NOT_FOUND", f"provider {provider_id} not in registry", details={"provider_id": provider_id})
        return rec

    def exists(self, provider_id: str) -> bool:
        return provider_id in self._providers

    def by_category(self, category: str) -> list[ProviderRecord]:
        return [p for p in self._providers.values() if p.category == category]

    def update(self, rec: ProviderRecord) -> None:
        with self._lock:
            self._providers[rec.provider_id] = rec

    # -- Integration Matrix (UI 由此自动生成, A2) --
    def integration_matrix(self) -> list[dict]:
        rows = []
        for p in self._providers.values():
            rows.append(
                {
                    "provider_id": p.provider_id,
                    "name": p.name,
                    "category": p.category,
                    "trust_class": p.trust_class,
                    "integration_level": p.integration_level,
                    "capabilities": p.capabilities.model_dump(),
                    "auth_modes": p.auth_modes,
                    "status": p.status,
                    "last_verified_at": p.last_verified_at,
                    "blocking_reason": p.blocking_reason,
                    "adapter_version": p.adapter_version,
                }
            )
        return rows


def json_safe(d: dict) -> dict:
    return {k: (v if v is not None else None) for k, v in d.items()}


@lru_cache(maxsize=1)
def get_registry() -> ProviderRegistry:
    reg = ProviderRegistry()
    return reg
