"""Eurostat adapter — dissemination API (data) + SDMX dataflow list (search corpus).

Verified 2026-09-11: data endpoint HTTP 200; dataflow XML list HTTP 200.
"""
from __future__ import annotations

import asyncio
import re
from xml.etree import ElementTree

from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import mk_candidate, safe_get
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get

BASE = "https://ec.europa.eu/eurostat/api/dissemination"
SDMX = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"

_lock = asyncio.Lock()
_flows: list[tuple[str, str]] | None = None


async def _load_dataflows() -> list[tuple[str, str]]:
    """Parse SDMX dataflow XML (id + name) once; used as the searchable catalog."""
    global _flows
    async with _lock:
        if _flows is not None:
            return _flows
        r = await get(f"{SDMX}/dataflow/ESTAT/all/latest", timeout=90, max_retries=0)
        if r.status != 200:
            raise RuntimeError(f"eurostat dataflow list HTTP {r.status}")
        xml = r.content
        flows = []
        for m in re.finditer(rb"<str:Dataflow\s([^>]*?)id=\"([^\"]+)\"([^>]*?)agencyID=\"ESTAT\"", xml, re.S):
            chunk = m.group(0)
            m2 = re.search(rb'<com:Name[^>]*xml:lang="en"[^>]*>([^<]+)</com:Name>', chunk + xml[m.end(): m.end() + 500])
            name = m2.group(1).decode("utf-8", "ignore") if m2 else ""
            flows.append((m.group(2).decode(), name))
        if not flows:
            # fallback: generic Namespace-agnostic parse
            root = ElementTree.fromstring(xml)
            for df in root.iter():
                if df.tag.endswith("Dataflow") and "id" in df.attrib:
                    name = ""
                    for child in df.iter():
                        if child.tag.endswith("Name"):
                            name = (child.text or "").strip()
                            break
                    flows.append((df.attrib["id"], name))
        _flows = flows
        return _flows


@register_adapter
class EurostatAdapter(ProviderAdapter):
    provider_id = "eurostat"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        flows = await _load_dataflows()
        q_terms = [t for t in re.split(r"[\s,;]+", query.lower()) if len(t) >= 3]
        scored = []
        for fid, name in flows:
            nl = name.lower()
            s = sum(2.0 if t in nl.split("(")[0] else 1.0 for t in q_terms if t in nl)
            if s:
                scored.append((s, fid, name))
        scored.sort(reverse=True)
        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=name or fid,
                source_url=f"https://ec.europa.eu/eurostat/databrowser/view/{fid}/default/table",
                description=name or "Eurostat dataset",
                publisher="Eurostat (European Commission)",
                license="CC-BY-4.0",
                access_mode="PUBLIC_ANONYMOUS_API",
                source_ref=fid,
                unit_of_analysis="country",
                geography=["EU"],
                direct_file_url=f"{BASE}/statistics/1.0/data/{fid}?lang=EN&format=JSON",
                file_format="JSON",
            )
            for _, fid, name in scored[:limit]
        ]

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"{BASE}/statistics/1.0/data/{dataset_ref}?lang=EN&format=JSON", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"eurostat dataset {dataset_ref} HTTP {r.status}")
        data = r.json()
        label = data.get("label", dataset_ref)
        dims = list((data.get("dimension") or {}).keys())
        times = sorted(safe_get(data, "dimension", "time", "category", "index", default={}).keys())
        geos = list(safe_get(data, "dimension", "geo", "category", "index", default={}).keys())
        return mk_candidate(
            provider_id=self.provider_id,
            title=label,
            source_url=f"https://ec.europa.eu/eurostat/databrowser/view/{dataset_ref}/default/table",
            description=label,
            publisher="Eurostat (European Commission)",
            license="CC-BY-4.0",
            access_mode="PUBLIC_ANONYMOUS_API",
            source_ref=dataset_ref,
            unit_of_analysis="country",
            geography=geos[:50] or ["EU"],
            time_start=times[0] if times else None,
            time_end=times[-1] if times else None,
            variable_hints=[d for d in dims if d not in ("time", "geo")][:20],
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "CC-BY-4.0", "notes": "Eurostat dissemination API"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        r = await get(f"{BASE}/statistics/1.0/data/{dataset_ref}?lang=EN&format=JSON", timeout=120)
        if r.status != 200:
            raise RuntimeError(f"eurostat download HTTP {r.status}")
        dest = Path(dest_dir) / f"eurostat_{dataset_ref}.json"
        dest.write_bytes(r.content)
        return [str(dest)]
