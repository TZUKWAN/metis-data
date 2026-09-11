"""Zenodo + Harvard Dataverse + generic Dataverse adapters — real public APIs."""
from __future__ import annotations

from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import mk_candidate, safe_get, write_small_payload
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get


def _flatten_authors(value) -> list[str]:
    """Dataverse author fields can be str / list[str] / list[dict] / nested lists."""
    out: list[str] = []

    def rec(v):
        if v is None:
            return
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            name = v.get("authorName", {}) if isinstance(v.get("authorName"), dict) else {}
            out.append(str(v.get("authorName") or name.get("value") or "") or str(list(v.values())[0] if v else ""))
        elif isinstance(v, (list, tuple)):
            for x in v:
                rec(x)

    rec(value)
    return [a for a in (s.strip() for s in out) if a]


@register_adapter
class ZenodoAdapter(ProviderAdapter):
    provider_id = "zenodo"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://zenodo.org/api/records", params={"q": query, "size": min(limit, 25)}, timeout=45)
        if r.status != 200:
            raise RuntimeError(f"zenodo search HTTP {r.status}")
        hits = safe_get(r.json(), "hits", "hits", default=[]) or []
        out = []
        for h in hits:
            meta = h.get("metadata", {})
            files = h.get("files", []) or []
            license_id = safe_get(meta, "license", "id", default="UNKNOWN")
            f0 = files[0] if files else None
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=meta.get("title", "Untitled"),
                    source_url=h.get("links", {}).get("self_html") or f"https://zenodo.org/records/{h.get('id','')}",
                    description=(meta.get("description") or "")[:800],
                    publisher="Zenodo",
                    authors=[c.get("name", "") for c in meta.get("creators", []) if isinstance(c, dict)],
                    doi=h.get("doi"),
                    version=meta.get("version"),
                    license=license_id.upper() if license_id else "UNKNOWN",
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    time_start=(meta.get("publication_date") or "")[:4] or None,
                    unit_of_analysis="UNKNOWN",
                    source_ref=str(h.get("id", "")),
                    direct_file_url=f0.get("links", {}).get("self") if f0 else None,
                    file_format=(f0.get("key", "").rsplit(".", 1)[-1].upper() if f0 and "." in f0.get("key", "") else None),
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://zenodo.org/api/records/{dataset_ref}", timeout=45)
        if r.status != 200:
            raise RuntimeError(f"zenodo record {dataset_ref} HTTP {r.status}")
        h = r.json()
        meta = h.get("metadata", {})
        files = h.get("files", []) or []
        from app.providers.adapters.common import normalize_doi

        return mk_candidate(
            provider_id=self.provider_id,
            title=meta.get("title", "Untitled"),
            source_url=h.get("links", {}).get("self_html") or f"https://zenodo.org/records/{dataset_ref}",
            description=(meta.get("description") or "")[:2000],
            publisher="Zenodo",
            authors=[c.get("name", "") for c in meta.get("creators", []) if isinstance(c, dict)],
            doi=normalize_doi(h.get("doi")),
            version=meta.get("version"),
            license=(safe_get(meta, "license", "id", default="UNKNOWN") or "UNKNOWN").upper(),
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
            direct_file_url=files[0].get("links", {}).get("self") if files else None,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "Zenodo record files; some records restricted"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        r = await get(f"https://zenodo.org/api/records/{dataset_ref}", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"zenodo record HTTP {r.status}")
        files = r.json().get("files", []) or []
        if not files:
            raise RuntimeError("zenodo record has no public files")
        out = []
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            for f in files[:5]:
                fr = await client.get(f["links"]["self"])
                if fr.status_code != 200:
                    continue
                p = Path(dest_dir) / f["key"].replace("/", "_")
                write_small_payload(p, fr.content)
                out.append(str(p))
        if not out:
            raise RuntimeError("zenodo file download failed")
        return out


class _DataverseBase(ProviderAdapter):
    base: str = "https://dataverse.harvard.edu"
    display_name: str = "Harvard Dataverse"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get(f"{self.base}/api/search", params={"q": query, "type": "dataset", "per_page": min(limit, 25)}, timeout=45)
        if r.status != 200:
            raise RuntimeError(f"dataverse search HTTP {r.status}")
        items = safe_get(r.json(), "data", "items", default=[]) or []
        out = []
        for it in items:
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("name", ""),
                    source_url=it.get("url", self.base),
                    description=it.get("description", "") or "UNKNOWN",
                    publisher=self.display_name,
                    authors=_flatten_authors(it.get("authors")),
                    doi=it.get("global_id"),
                    version=str(it.get("version", "")) or None,
                    license="UNKNOWN",
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    time_start=str(it.get("published_at", ""))[:4] or None,
                    unit_of_analysis="UNKNOWN",
                    source_ref=it.get("global_id", ""),
                    file_format=None,
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        # dataset_ref is a DOI-like global id (doi:10.7910/DVN/XXXX)
        pid = dataset_ref.replace("doi:", "")
        r = await get(f"{self.base}/api/datasets/:persistentId/?persistentId=doi:{pid}", timeout=45)
        if r.status != 200:
            raise RuntimeError(f"dataverse dataset HTTP {r.status}")
        dv = safe_get(r.json(), "data", "latestVersion", default={}) or {}
        md = (dv.get("metadataBlocks", {}) or {}).get("citation", {})
        fields = {f.get("typeName"): f.get("value") for f in md.get("fields", [])}
        title = fields.get("title", dataset_ref)
        if isinstance(title, list):
            title = title[0] if title else dataset_ref
        return mk_candidate(
            provider_id=self.provider_id,
            title=str(title),
            source_url=f"{self.base}/dataset.xhtml?persistentId=doi:{pid}",
            description=str(fields.get("dsDescription", ""))[:2000],
            publisher=self.display_name,
            authors=[a.get("authorName", {}).get("value", "") for a in (fields.get("author") or [])] if isinstance(fields.get("author"), list) else [],
            doi=f"doi:{pid}",
            license="UNKNOWN",
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "public files via /api/access/datafile; restricted files need login"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        pid = dataset_ref.replace("doi:", "")
        r = await get(f"{self.base}/api/datasets/:persistentId/?persistentId=doi:{pid}", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"dataverse dataset HTTP {r.status}")
        files = safe_get(r.json(), "data", "latestVersion", "files", default=[]) or []
        out = []
        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
            for f in files[:5]:
                fid = safe_get(f, "dataFile", "id")
                if not fid:
                    continue
                fr = await client.get(f"{self.base}/api/access/datafile/{fid}")
                if fr.status_code != 200:
                    continue
                name = safe_get(f, "dataFile", "filename") or f"dataverse_{fid}"
                p = Path(dest_dir) / name.replace("/", "_")
                write_small_payload(p, fr.content)
                out.append(str(p))
        if not out:
            raise RuntimeError("dataverse no downloadable public files")
        return out


@register_adapter
class HarvardDataverseAdapter(_DataverseBase):
    provider_id = "harvard_dataverse"
    base = "https://dataverse.harvard.edu"
    display_name = "Harvard Dataverse"
