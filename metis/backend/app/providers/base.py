"""ProviderAdapter contract (P02-003) + Capability Guard (P02-004).

Unified interface (PRD §8). UI NEVER calls provider-specific methods — only these.
Capability Guard refuses calls a provider does not declare (未实现能力不得标 true).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.core.errors import MetisError
from app.core.logging import get_logger
from app.domain.enums import AccessMode
from app.domain.schemas import DatasetCandidate, ProviderRecord
from app.providers.registry import get_registry

log = get_logger("provider")


class AccessRequirements(BaseModel):
    access_mode: str = AccessMode.UNKNOWN
    requires_login: bool = False
    restricted: bool = False
    license: str = "UNKNOWN"
    notes: str = ""
    intervention_kinds: list[str] = []


class ProviderAdapter(ABC):
    """Base class for all adapters. `provider_id` must match the registry entry."""

    provider_id: str = ""
    adapter_version: str = "1.0.0"

    def __init__(self) -> None:
        self.record: ProviderRecord = get_registry().get(self.provider_id)
        self._verified_level = False

    # ---- capability guard ----
    def _require(self, capability: str) -> None:
        caps = self.record.capabilities
        if not getattr(caps, capability, False):
            raise MetisError(
                "PROVIDER_CAPABILITY_MISSING",
                f"provider {self.provider_id} does not declare capability '{capability}'",
                provider_id=self.provider_id,
                details={"capability": capability, "integration_level": self.record.integration_level},
            )

    # ---- unified interface ----
    @abstractmethod
    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        """Real discovery against the provider. Returns normalized candidates."""

    @abstractmethod
    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        """Full metadata for one dataset."""

    async def preview_dataset(self, dataset_ref: str) -> dict:
        self._require("preview")
        raise MetisError("PROVIDER_CAPABILITY_MISSING", f"preview not implemented for {self.provider_id}", provider_id=self.provider_id)

    async def get_access_requirements(self, dataset_ref: str) -> AccessRequirements:
        self._require("metadata_api")
        return AccessRequirements()

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        """Download raw file(s) into dest_dir; returns local file paths. Requires DownloadJob upstream (P11 gate)."""
        raise MetisError("PROVIDER_CAPABILITY_MISSING", f"acquire not implemented for {self.provider_id}", provider_id=self.provider_id)

    async def refresh_auth(self) -> dict:
        return {"provider_id": self.provider_id, "status": "no_auth_required"}


_ADAPTERS: dict[str, ProviderAdapter] = {}


def register_adapter(cls: type[ProviderAdapter]) -> type[ProviderAdapter]:
    inst = cls()
    _ADAPTERS[inst.provider_id] = inst
    return cls


def get_adapter(provider_id: str) -> ProviderAdapter:
    if provider_id not in _ADAPTERS:
        # import all adapter modules to trigger registration
        _import_all()
    if provider_id not in _ADAPTERS:
        raise MetisError("PROVIDER_CAPABILITY_MISSING", f"no adapter implemented for {provider_id}", provider_id=provider_id)
    return _ADAPTERS[provider_id]


def available_adapters() -> list[str]:
    _import_all()
    return sorted(_ADAPTERS)


def _import_all() -> None:
    import importlib
    import pkgutil

    from app.providers import adapters as adapters_pkg

    for mod in pkgutil.iter_modules(adapters_pkg.__path__):
        importlib.import_module(f"app.providers.adapters.{mod.name}")
