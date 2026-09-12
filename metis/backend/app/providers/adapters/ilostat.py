"""ILOSTAT adapter via ILO SDMX REST (sdmx.ilo.org, NSI Web Service).

Verified 2026-09-11: dataflow list HTTP 200 (7.3MB XML); data query requires full
dimension keys — adapter resolves dimension order from the DSD.
"""
from __future__ import annotations

import asyncio
import re
from xml.etree import ElementTree

from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import mk_candidate
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get

BASE = "https://sdmx.ilo.org/rest"
NS = {"str": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message", "com": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common", "s": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure"}

_lock = asyncio.Lock()
_flows: list[tuple[str, str]] | None = None


async def _load_dataflows() -> list[tuple[str, str]]:
    global _flows
    async with _lock:
        if _flows is not None:
            return _flows
        r = await get(f"{BASE}/dataflow/ILO/all/latest", timeout=120, max_retries=0)
        if r.status != 200:
            raise RuntimeError(f"ilostat dataflow list HTTP {r.status}")
        root = ElementTree.fromstring(r.content)
        flows = []
        for df in root.iter("{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure}Dataflow"):
            fid = df.attrib.get("id", "")
            name = ""
            for child in df.iter():
                if child.tag.endswith("Name") and child.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") == "en":
                    name = (child.text or "").strip()
                    break
            flows.append((fid, name))
        _flows = flows
        return _flows


async def _dataflow_dims(flow_id: str) -> list[str]:
    """Dimension order for building SDMX keys."""
    dsd = flow_id.replace("DF_", "") if flow_id.startswith("DF_") else flow_id
    r = await get(f"{BASE}/datastructure/ILO/DSD_{dsd}/latest?references=none", timeout=60, max_retries=0)
    if r.status != 200:
        return []
    root = ElementTree.fromstring(r.content)
    dims = []
    for d in root.iter():
        if d.tag.endswith("Dimension"):
            ref = None
            for child in d.iter():
                if child.tag.endswith("Dimension") or child.tag.endswith("DimensionList"):
                    continue
                if child.tag.endswith("Ref") and "id" in child.attrib:
                    ref = child.attrib["id"]
                    break
            if ref:
                dims.append(ref)
        if d.tag.endswith("DimensionList"):
            pass
    return dims


@register_adapter
class IlostatAdapter(ProviderAdapter):
    provider_id = "ilostat"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        flows = await _load_dataflows()
        q_terms = [t for t in re.split(r"[\s,;]+", query.lower()) if len(t) >= 3]
        scored = []
        for fid, name in flows:
            nl = (name or "").lower()
            s = sum(2.0 if t in nl.split("-")[0] else 1.0 for t in q_terms if t in nl)
            if s:
                scored.append((s, fid, name))
        scored.sort(reverse=True)
        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=name or fid,
                source_url="https://ilostat.ilo.org/data/",
                description=name or fid,
                publisher="International Labour Organization (ILOSTAT)",
                license="CC-BY-4.0",
                access_mode="PUBLIC_ANONYMOUS_API",
                source_ref=fid,
                unit_of_analysis="country",
                geography=["world"],
                variable_hints=[fid],
            )
            for _, fid, name in scored[:limit]
        ]

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        flows = await _load_dataflows()
        name = dict(flows).get(dataset_ref, dataset_ref)
        return mk_candidate(
            provider_id=self.provider_id,
            title=name,
            source_url="https://ilostat.ilo.org/data/",
            description=name,
            publisher="International Labour Organization (ILOSTAT)",
            license="CC-BY-4.0",
            access_mode="PUBLIC_ANONYMOUS_API",
            source_ref=dataset_ref,
            unit_of_analysis="country",
            geography=["world"],
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "CC-BY-4.0", "notes": "ILOSTAT SDMX REST"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        """Stream SDMX CSV via the bounded download helper (payloads can exceed 32MB)."""
        import urllib.parse
        from pathlib import Path

        from app.providers.adapters.common import download_to_file

        country = (access_context or {}).get("ref_area", "CHN")
        params = urllib.parse.urlencode({"format": "csv", "startPeriod": (access_context or {}).get("start", "2000"), "c[REF_AREA]": country})
        url = f"{BASE}/data/ILO,{dataset_ref},1.0/all?{params}"
        dest = Path(dest_dir) / f"ilostat_{dataset_ref}.csv"
        try:
            await download_to_file(url, dest, timeout=300)
        except __import__("app.core.errors", fromlist=["MetisError"]).MetisError as e:
            if e.code != "PROVIDER_HTTP_ERROR":
                raise
            # fallback: all-dims wildcard key
            url2 = f"{BASE}/data/ILO,{dataset_ref},1.0/all?format=csv&startPeriod=2000"
            await download_to_file(url2, dest, timeout=600)
        return [str(dest)]

