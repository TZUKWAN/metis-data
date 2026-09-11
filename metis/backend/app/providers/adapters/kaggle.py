"""Kaggle adapter — anonymous list API verified 2026-09-11 (search P1).

Download requires Kaggle API credentials (basic auth) stored in Vault → P5 target.
No credential-bypass: without credentials the adapter reports capability missing.
"""
from __future__ import annotations

from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import mk_candidate
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get

API = "https://www.kaggle.com/api/v1"


def _kaggle_auth(access_context: dict | None) -> tuple[str, str] | None:
    ctx = access_context or {}
    user, key = ctx.get("kaggle_username"), ctx.get("kaggle_key")
    if user and key:
        return (user, key)
    from app.auth import vault as _vault  # late import

    try:
        user = _vault.get_secret("kaggle.username")
        key = _vault.get_secret("kaggle.key")
        if user and key:
            return (user, key)
    except Exception:
        pass
    return None


@register_adapter
class KaggleAdapter(ProviderAdapter):
    provider_id = "kaggle"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get(f"{API}/datasets/list", params={"search": query, "pageSize": min(limit, 20)}, timeout=45)
        if r.status == 401:
            raise PermissionError("kaggle search now requires credentials (HTTP 401)")
        if r.status != 200:
            raise RuntimeError(f"kaggle search HTTP {r.status}")
        items = r.json() or []
        out = []
        for it in items:
            ref = it.get("ref") or f"{it.get('owner','')}/{it.get('dataset_ref') or it.get('slug','')}"
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("title") or ref,
                    source_url=f"https://www.kaggle.com/datasets/{ref}",
                    description=(it.get("subtitle") or "")[:500],
                    publisher=it.get("ownerName") or it.get("owner") or "Kaggle community",
                    license=licenses_kaggle(it.get("licenses")),
                    access_mode="EXISTING_ACCOUNT",
                    requires_login=True,
                    unit_of_analysis="UNKNOWN",
                    source_ref=ref,
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"{API}/datasets/view/{dataset_ref}", timeout=45)
        if r.status != 200:
            raise RuntimeError(f"kaggle dataset HTTP {r.status}")
        it = r.json()
        return mk_candidate(
            provider_id=self.provider_id,
            title=it.get("title") or dataset_ref,
            source_url=f"https://www.kaggle.com/datasets/{dataset_ref}",
            description=(it.get("subtitle") or "")[:1000],
            publisher=it.get("ownerName") or "Kaggle community",
            license=licenses_kaggle(it.get("licenses")),
            access_mode="EXISTING_ACCOUNT",
            requires_login=True,
            source_ref=dataset_ref,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {
            "access_mode": "EXISTING_ACCOUNT",
            "requires_login": True,
            "restricted": False,
            "license": "VARIES",
            "notes": "download requires Kaggle account (API credentials in Vault); registration involves CAPTCHA on kaggle.com so auto-registration is not attempted",
        }

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        import zipfile
        from pathlib import Path

        auth = _kaggle_auth(access_context)
        if auth is None:
            raise PermissionError("Kaggle credentials not configured in Vault; bind an existing account first (download requires login)")
        import httpx

        url = f"{API}/datasets/download/{dataset_ref}"
        async with httpx.AsyncClient(timeout=600, follow_redirects=True, auth=auth) as client:
            r = await client.get(url)
        if r.status_code != 200:
            raise RuntimeError(f"kaggle download HTTP {r.status_code}")
        if r.content[:2] != b"PK":
            raise RuntimeError("kaggle download did not return a zip archive")
        p = Path(dest_dir) / f"kaggle_{dataset_ref.replace('/', '_')}.zip"
        p.write_bytes(r.content)
        with zipfile.ZipFile(p) as z:
            z.extractall(dest_dir)
        return [str(p)]


def licenses_kaggle(lics) -> str:
    if not lics:
        return "UNKNOWN"
    names = []
    for l in lics:
        n = (l.get("name") if isinstance(l, dict) else str(l)) or ""
        names.append(n)
    joined = ", ".join(names).upper()
    return joined or "UNKNOWN"
