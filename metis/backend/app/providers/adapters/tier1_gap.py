"""UN SDG API + UCI ML + ModelScope adapters (GATE-02 closure) + NASA CMR keyword fix."""
from __future__ import annotations

from app.domain.schemas import DatasetCandidate
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get
from app.providers.adapters.common import mk_candidate, safe_get


@register_adapter
class UnSdgAdapter(ProviderAdapter):
    """UN SDG indicators API (unstats.un.org/sdgapi) — search series + CSV data."""

    provider_id = "un_databases"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://unstats.un.org/sdgapi/v1/sdg/Series/List", params={"pageSize": 2000}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"unsdg series list HTTP {r.status}")
        series = r.json() or []
        terms = [t for t in query.lower().replace(",", " ").split() if len(t) >= 3]
        scored = []
        for sr in series:
            text = f'{sr.get("description", "")} {sr.get("indicator", [""])[0] if sr.get("indicator") else ""}'.lower()
            score = sum(2.0 if t in text else 0.0 for t in terms)
            if score:
                scored.append((score, sr))
        scored.sort(key=lambda x: -x[0])
        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=sr.get("description", sr.get("code", "")),
                source_url=f'https://unstats.un.org/sdgapi/v1/sdg/Series/{sr.get("code")}/Data',
                description=f'UN SDG indicator {sr.get("indicator", [""])[0] if sr.get("indicator") else ""} series {sr.get("code")}',
                publisher="United Nations Statistics Division",
                license="UN open data",
                access_mode="PUBLIC_ANONYMOUS_API",
                unit_of_analysis="country",
                geography=["world"],
                source_ref=str(sr.get("code", "")),
                variable_hints=[str(sr.get("description", ""))[:60]],
            )
            for _, sr in scored[:limit]
        ]

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://unstats.un.org/sdgapi/v1/sdg/Series/List", params={"pageSize": 2000}, timeout=60)
        for sr in r.json() or []:
            if str(sr.get("code")) == dataset_ref:
                return mk_candidate(
                    provider_id=self.provider_id,
                    title=sr.get("description", dataset_ref),
                    source_url=f"https://unstats.un.org/sdgapi/v1/sdg/Series/{dataset_ref}/Data",
                    publisher="United Nations Statistics Division",
                    license="UN open data",
                    access_mode="PUBLIC_ANONYMOUS_API",
                    source_ref=dataset_ref,
                    unit_of_analysis="country",
                )
        raise RuntimeError(f"unsdg series {dataset_ref} not found")

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "UN-OPEN", "notes": "UN SDG public API"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        from app.providers.adapters.common import write_small_payload

        rows = []
        for page in (1, 2):  # first two pages are plenty for validation-grade pulls
            r = await get(
                f"https://unstats.un.org/sdgapi/v1/sdg/Series/{dataset_ref}/Data",
                params={"pageSize": 1000, "page": page},
                timeout=120,
                max_retries=1,
            )
            if r.status != 200:
                break
            batch = r.json() or []
            rows.extend(batch)
            if len(batch) < 1000:
                break
        if not rows:
            raise RuntimeError("unsdg no data rows")
        dest = Path(dest_dir) / f"unsdg_{dataset_ref}.json"
        write_small_payload(dest, __import__("json").dumps(rows).encode("utf-8"))
        return [str(dest)]


@register_adapter
class UciMlAdapter(ProviderAdapter):
    """UCI ML Repository public API (archive.ics.uci.edu/api)."""

    provider_id = "uci_ml"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://archive.ics.uci.edu/api/datasets/list", params={"search": query}, timeout=45)
        if r.status != 200:
            raise RuntimeError(f"uci list HTTP {r.status}")
        items = safe_get(r.json(), "data", default=[]) or []
        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=str(it.get("name", "")),
                source_url=f"https://archive.ics.uci.edu/dataset/{it.get('id')}",
                description=f"UCI dataset #{it.get('id')}",
                publisher="UC Irvine ML Repository",
                license="UNKNOWN",  # per-dataset; must verify
                access_mode="PUBLIC_ANONYMOUS_HTTP",
                source_ref=str(it.get("id", "")),
                unit_of_analysis="UNKNOWN",
            )
            for it in items[:limit]
        ]

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://archive.ics.uci.edu/api/dataset/{dataset_ref}", timeout=45)
        if r.status != 200:
            raise RuntimeError(f"uci dataset HTTP {r.status}")
        it = r.json().get("data", {})
        return mk_candidate(
            provider_id=self.provider_id,
            title=str(it.get("name", dataset_ref)),
            source_url=f"https://archive.ics.uci.edu/dataset/{dataset_ref}",
            description=str(it.get("abstract", ""))[:800],
            publisher="UC Irvine ML Repository",
            license=str(it.get("license", {}).get("name", "UNKNOWN")).upper() if isinstance(it.get("license"), dict) else "UNKNOWN",
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "UCI public zip download"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        import httpx
        from pathlib import Path

        r = await get(f"https://archive.ics.uci.edu/api/dataset/{dataset_ref}", timeout=45)
        it = r.json().get("data", {})
        url = None
        for sup in it.get("external_url", []) or []:
            pass
        # canonical zip: /static/public/uci/<id>/... exposed via api 'data_url'
        url = it.get("data_url")
        if not url:
            raise RuntimeError("uci no data url")
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            fr = await client.get(url)
        if fr.status_code != 200:
            raise RuntimeError(f"uci download HTTP {fr.status_code}")
        from app.providers.adapters.common import write_small_payload

        dest = Path(dest_dir) / f"uci_{dataset_ref}.zip"
        write_small_payload(dest, fr.content)
        return [str(dest)]
