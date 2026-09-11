"""World Bank Open Data adapter — real API v2 (search / metadata / anonymous download).

API: https://api.worldbank.org/v2  (JSON, no key required)
License: CC-BY-4.0 (open).
"""
from __future__ import annotations

import asyncio

from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import mk_candidate
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get

API = "https://api.worldbank.org/v2"

# indicator cache: keyword -> list of (id, name) — built once per process
_index_lock = asyncio.Lock()
_indicator_index: list[tuple[str, str]] | None = None


async def _load_indicator_index() -> list[tuple[str, str]]:
    global _indicator_index
    async with _index_lock:
        if _indicator_index is not None:
            return _indicator_index
        out: list[tuple[str, str]] = []
        # single bulk request: WB API supports per_page up to 32768 (29.5k indicators)
        r = await get(f"{API}/indicator", params={"format": "json", "per_page": 30000, "page": 1}, timeout=120, max_retries=1)
        if r.status == 200:
            data = r.json()
            items = data[1] if isinstance(data, list) and len(data) > 1 else []
            for it in items or []:
                out.append((it.get("id", ""), it.get("name", "")))
        _indicator_index = out
        return out


@register_adapter
class WorldBankAdapter(ProviderAdapter):
    provider_id = "world_bank"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        index = await _load_indicator_index()
        q = query.lower()
        scored = []
        for iid, name in index:
            nl = name.lower()
            score = 0.0
            for term in q.replace(";", " ").replace(",", " ").split():
                t = term.strip()
                if len(t) < 3:
                    continue
                if t in nl:
                    score += 2.0 if t in nl.split(",")[0] else 1.0
            if score > 0:
                scored.append((score, iid, name))
        scored.sort(reverse=True)
        out = []
        for _, iid, name in scored[:limit]:
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=name,
                    source_url=f"https://data.worldbank.org/indicator/{iid}",
                    description=name,
                    publisher="World Bank",
                    license="CC-BY-4.0",
                    access_mode="PUBLIC_ANONYMOUS_API",
                    source_ref=iid,
                    unit_of_analysis="country",
                    direct_file_url=f"{API}/country/all/indicator/{iid}?format=json&per_page=20000",
                    file_format="JSON",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"{API}/indicator/{dataset_ref}", params={"format": "json"}, timeout=30)
        if r.status != 200:
            raise RuntimeError(f"world_bank indicator {dataset_ref} HTTP {r.status}")
        data = r.json()
        it = (data[1] or [{}])[0] if isinstance(data, list) and len(data) > 1 else {}
        return mk_candidate(
            provider_id=self.provider_id,
            title=it.get("name", dataset_ref),
            source_url=f"https://data.worldbank.org/indicator/{dataset_ref}",
            description=it.get("name", ""),
            publisher="World Bank",
            doi=None,
            license="CC-BY-4.0",
            access_mode="PUBLIC_ANONYMOUS_API",
            source_ref=dataset_ref,
            unit_of_analysis="country",
            geography=["world"],
            direct_file_url=f"{API}/country/all/indicator/{dataset_ref}?format=json&per_page=20000",
            file_format="JSON",
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "CC-BY-4.0", "notes": "World Bank Open Data API; CC-BY-4.0"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        url = f"{API}/country/all/indicator/{dataset_ref}?format=json&per_page=20000&downloadformat=csv"
        r = await get(url, timeout=120)
        if r.status != 200:
            raise RuntimeError(f"world_bank download HTTP {r.status}")
        dest = Path(dest_dir) / f"world_bank_{dataset_ref}.json"
        dest.write_bytes(r.content)
        return [str(dest)]
