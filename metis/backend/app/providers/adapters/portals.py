"""Generic CKAN adapter family + NBS China attempt + more international/US adapters.

Registered providers here: data_gov_uk, opendata_swiss, us_census, data_gouv_fr,
oecd, un_comtrade, nasa_earthdata, usgs, huggingface_datasets, dryad, osf,
figshare, wikidata, nbs_china.
"""
from __future__ import annotations

from app.domain.schemas import DatasetCandidate
from app.providers.adapters.common import licenses_from_ckan, mk_candidate, safe_get
from app.providers.base import ProviderAdapter, register_adapter
from app.providers.http_client import get


class CkanAdapter(ProviderAdapter):
    """CKAN package_search based adapter. Subclass sets api_base/provider_id."""
    api_base: str = ""
    display: str = ""

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get(f"{self.api_base}/api/3/action/package_search", params={"q": query, "rows": min(limit, 25)}, timeout=40)
        if r.status != 200:
            raise RuntimeError(f"{self.provider_id} ckan HTTP {r.status}")
        results = safe_get(r.json(), "result", "results", default=[]) or []
        return [self._to_candidate(p) for p in results]

    @staticmethod
    def _flat(v) -> str:
        """CKAN multilingual fields may be str or {lang: str}."""
        if isinstance(v, dict):
            for lang in ("en", "de", "fr", "it", "es", "nl"):
                if v.get(lang):
                    return str(v[lang])
            return str(next(iter(v.values()), "")) if v else ""
        return str(v or "")

    def _to_candidate(self, pkg: dict) -> DatasetCandidate:
        res = (pkg.get("resources") or [])
        r0 = res[0] if res else {}
        fmt = (r0.get("format") or "").upper() or None
        return mk_candidate(
            provider_id=self.provider_id,
            title=self._flat(pkg.get("title")) or pkg.get("name", ""),
            source_url=pkg.get("url") or f"{self.api_base}/dataset/{pkg.get('name','')}",
            description=self._flat(pkg.get("notes"))[:800],
            publisher=self._flat((pkg.get("organization") or {}).get("title", "")) if isinstance(pkg.get("organization"), dict) else "",
            license=licenses_from_ckan(pkg.get("license_id"), pkg.get("license_title")),
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=pkg.get("id", pkg.get("name", "")),
            direct_file_url=r0.get("url"),
            file_format=fmt if fmt in {"CSV", "TSV", "JSON", "XLS", "XLSX", "ZIP", "XML", "GEOJSON", "PARQUET", "SHP", "TXT", "HTML"} else None,
            time_start=(pkg.get("metadata_created") or "")[:10] or None,
        )

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"{self.api_base}/api/3/action/package_show", params={"id": dataset_ref}, timeout=40)
        if r.status != 200:
            raise RuntimeError(f"{self.provider_id} package_show HTTP {r.status}")
        return self._to_candidate(safe_get(r.json(), "result", default={}) or {})

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "CKAN open data portal"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        cand = await self.get_dataset_metadata(dataset_ref)
        urls = [s.direct_file_url for s in cand.files if s.direct_file_url]
        if not urls:
            pkg = None
            r = await get(f"{self.api_base}/api/3/action/package_show", params={"id": dataset_ref}, timeout=40)
            if r.status == 200:
                pkg = safe_get(r.json(), "result", default={}) or {}
            urls = [x.get("url") for x in (pkg or {}).get("resources", []) if x.get("url")]
        out = []
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            for u in urls[:5]:
                fr = await client.get(u)
                if fr.status_code != 200:
                    continue
                name = u.rsplit("/", 1)[-1].split("?")[0] or "resource.bin"
                p = Path(dest_dir) / name
                p.write_bytes(fr.content)
                out.append(str(p))
        if not out:
            raise RuntimeError(f"{self.provider_id}: no downloadable resource")
        return out


@register_adapter
class DataGovUkAdapter(CkanAdapter):
    provider_id = "data_gov_uk"
    api_base = "https://data.gov.uk"
    display = "data.gov.uk"


@register_adapter
class OpenDataSwissAdapter(CkanAdapter):
    provider_id = "opendata_swiss"
    api_base = "https://opendata.swiss"
    display = "opendata.swiss"


@register_adapter
class UsCensusAdapter(ProviderAdapter):
    """US Census: api.census.gov data.json catalog (verified 200, 5MB) + data endpoints."""
    provider_id = "us_census"

    _catalog: list[dict] | None = None

    async def _load_catalog(self) -> list[dict]:
        if self._catalog is not None:
            return self._catalog
        r = await get("https://api.census.gov/data.json", timeout=90, max_retries=0)
        if r.status != 200:
            raise RuntimeError(f"census catalog HTTP {r.status}")
        datasets = safe_get(r.json(), "dataset", default=[]) or []
        self._catalog = datasets
        return datasets

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        catalog = await self._load_catalog()
        terms = [t for t in query.lower().split() if len(t) >= 3]
        scored = []
        for ds in catalog:
            title = str(ds.get("title", "")).lower()
            s = sum(2.0 if t in title else 0.0 for t in terms)
            if s:
                scored.append((s, ds))
        scored.sort(key=lambda x: -x[0])
        out = []
        for s, ds in scored[:limit]:
            identifier = ds.get("identifier", "")
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=str(ds.get("title", "Census dataset")),
                    source_url=identifier,
                    description=str(ds.get("description", ""))[:800],
                    publisher="U.S. Census Bureau",
                    license="USGOV-PUBLIC",
                    access_mode="PUBLIC_ANONYMOUS_API",
                    source_ref=identifier.rsplit("/", 2)[-2] if identifier.count("/") >= 2 else identifier,
                    unit_of_analysis="UNKNOWN",
                    geography=["US"],
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        catalog = await self._load_catalog()
        for ds in catalog:
            if dataset_ref in str(ds.get("identifier", "")):
                return mk_candidate(
                    provider_id=self.provider_id,
                    title=str(ds.get("title", dataset_ref)),
                    source_url=str(ds.get("identifier", "")),
                    description=str(ds.get("description", ""))[:1500],
                    publisher="U.S. Census Bureau",
                    license="USGOV-PUBLIC",
                    access_mode="PUBLIC_ANONYMOUS_API",
                    source_ref=dataset_ref,
                    geography=["US"],
                )
        raise RuntimeError(f"census dataset {dataset_ref} not in catalog")

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "USGOV-PUBLIC", "notes": "public API, key optional"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        base = f"https://api.census.gov/data/{dataset_ref}" if "/" not in dataset_ref else dataset_ref
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            r = await client.get(base if base.endswith(".json") else base + "/geo.json")
        if r.status != 200:
            raise RuntimeError(f"census download HTTP {r.status}")
        p = Path(dest_dir) / f"us_census_{dataset_ref.replace('/', '_')}.json"
        p.write_bytes(r.content)
        return [str(p)]


@register_adapter
class DataGouvFrAdapter(ProviderAdapter):
    provider_id = "data_gouv_fr"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://www.data.gouv.fr/api/1/datasets/", params={"q": query, "page_size": min(limit, 25)}, timeout=40)
        if r.status != 200:
            raise RuntimeError(f"data.gouv.fr HTTP {r.status}")
        items = r.json().get("data", []) or []
        out = []
        for it in items:
            res = it.get("resources", []) or []
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("title", ""),
                    source_url=it.get("page", "") or f"https://www.data.gouv.fr/datasets/{it.get('id','')}",
                    description=(it.get("description") or "")[:800],
                    publisher=(it.get("organization") or {}).get("name", "") if isinstance(it.get("organization"), dict) else "",
                    license=(it.get("license") or "UNKNOWN"),
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    source_ref=it.get("id", ""),
                    direct_file_url=res[0].get("url") if res else None,
                    file_format=(res[0].get("format") or "").upper() if res else None,
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://www.data.gouv.fr/api/1/datasets/{dataset_ref}/", timeout=40)
        if r.status != 200:
            raise RuntimeError(f"data.gouv.fr dataset HTTP {r.status}")
        it = r.json()
        res = it.get("resources", []) or []
        return mk_candidate(
            provider_id=self.provider_id,
            title=it.get("title", ""),
            source_url=it.get("page", ""),
            description=(it.get("description") or "")[:1500],
            license=it.get("license") or "UNKNOWN",
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
            direct_file_url=res[0].get("url") if res else None,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "data.gouv.fr open license varies per dataset"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        cand = await self.get_dataset_metadata(dataset_ref)
        out = []
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            for s in cand.files:
                if not s.direct_file_url:
                    continue
                fr = await client.get(s.direct_file_url)
                if fr.status_code == 200:
                    p = Path(dest_dir) / (s.direct_file_url.rsplit("/", 1)[-1].split("?")[0] or "resource.bin")
                    p.write_bytes(fr.content)
                    out.append(str(p))
        if not out:
            raise RuntimeError("data.gouv.fr download failed")
        return out


@register_adapter
class OecdAdapter(ProviderAdapter):
    """OECD SDMX (sdmx.oecd.org): dataflow list as catalog (verified 200); CSV data."""
    provider_id = "oecd"

    _flows: list[tuple[str, str]] | None = None

    async def _load_flows(self) -> list[tuple[str, str]]:
        if self._flows is not None:
            return self._flows
        r = await get("https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.TPS/all/latest", timeout=90, max_retries=0)
        if r.status != 200:
            raise RuntimeError(f"oecd dataflow HTTP {r.status}")
        from xml.etree import ElementTree

        root = ElementTree.fromstring(r.content)
        flows = []
        for df in root.iter():
            if df.tag.split("}")[-1] == "Dataflow" and "id" in df.attrib:
                name = ""
                for child in df.iter():
                    if child.tag.split("}")[-1] == "Name":
                        name = (child.text or "").strip()
                        break
                flows.append((df.attrib["id"], name))
        self._flows = flows
        return flows

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        flows = await self._load_flows()
        terms = [t for t in query.lower().split() if len(t) >= 3]
        scored = []
        for fid, name in flows:
            nl = name.lower()
            s = sum(2.0 if t in nl else 1.0 for t in terms if t in nl)
            if s:
                scored.append((s, fid, name))
        scored.sort(reverse=True)
        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=name,
                source_url="https://data-explorer.oecd.org",
                description=name,
                publisher="OECD",
                license="OECD open (CC-BY-4.0 like)",
                access_mode="PUBLIC_ANONYMOUS_API",
                source_ref=fid,
                unit_of_analysis="country",
            )
            for _, fid, name in scored[:limit]
        ]

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        return mk_candidate(
            provider_id=self.provider_id,
            title=dataset_ref,
            source_url="https://data-explorer.oecd.org",
            publisher="OECD",
            license="OECD open",
            access_mode="PUBLIC_ANONYMOUS_API",
            source_ref=dataset_ref,
            unit_of_analysis="country",
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "OECD-OPEN", "notes": "SDMX CSV download"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        agency, fid = (dataset_ref.split(":") + [""])[:2] if ":" in dataset_ref else ("OECD.SDD.TPS", dataset_ref)
        url = f"https://sdmx.oecd.org/public/rest/data/{agency},{fid},latest/?startPeriod={(access_context or {}).get('start','2010')}&format=csvfilewithlabels"
        r = await get(url, timeout=240, max_retries=1)
        if r.status != 200:
            raise RuntimeError(f"oecd data HTTP {r.status}")
        p = Path(dest_dir) / f"oecd_{fid}.csv"
        p.write_bytes(r.content)
        return [str(p)]


@register_adapter
class UnComtradeAdapter(ProviderAdapter):
    """UN Comtrade public preview API (verified 200 without key for preview)."""
    provider_id = "un_comtrade"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        # Comtrade datasets are parameterized bilateral flows; build candidates from
        # query-mentioned year + a small set of major reporters (reference lists).
        import re as _re

        years = [y for y in _re.findall(r"(20\d\d)", query)] or ["2022"]
        out = []
        for y in years[:2]:
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=f"UN Comtrade international trade flows ({y})",
                    source_url="https://comtradeplus.un.org",
                    description="Bilateral goods trade flows by reporter/partner/commodity (HS), annual. Retrieved via public preview API.",
                    publisher="United Nations Statistics Division",
                    license="UN open data (attribution)",
                    access_mode="PUBLIC_ANONYMOUS_API",
                    time_start=y,
                    time_end=y,
                    unit_of_analysis="country",
                    geography=["world"],
                    variable_hints=["trade_value", "commodity", "flow"],
                    source_ref=f"annual_{y}",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        year = dataset_ref.rsplit("_", 1)[-1]
        return (await self.search_datasets(year))[0]

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "UN-OPEN", "notes": "public preview API; full API needs free subscription key"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        year = dataset_ref.rsplit("_", 1)[-1]
        reporter = (access_context or {}).get("reporterCode", "156")
        url = f"https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode={reporter}&period={year}&cmdCode=TOTAL&flowCode=X"
        r = await get(url, timeout=120, max_retries=1)
        if r.status != 200:
            raise RuntimeError(f"comtrade HTTP {r.status}")
        p = Path(dest_dir) / f"un_comtrade_{reporter}_{year}.json"
        p.write_bytes(r.content)
        return [str(p)]


@register_adapter
class NasaEarthdataAdapter(ProviderAdapter):
    """NASA CMR collection search (verified 200). Download needs Earthdata login (P5 target)."""
    provider_id = "nasa_earthdata"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://cmr.earthdata.nasa.gov/search/collections.json", params={"has_granules": "true", "page_size": min(limit, 25), "phrase": query}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"cmr HTTP {r.status}")
        entries = safe_get(r.json(), "feed", "entry", default=[]) or []
        out = []
        for e in entries:
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=e.get("title", ""),
                    source_url=e.get("links", [{}])[0].get("href", "https://www.earthdata.nasa.gov") if e.get("links") else "https://www.earthdata.nasa.gov",
                    description=e.get("summary", "")[:800],
                    publisher="NASA Earthdata",
                    license="VARIES (NASA open; EULA applies)",
                    access_mode="EXISTING_ACCOUNT",
                    requires_login=True,
                    source_ref=e.get("id", ""),
                    unit_of_analysis="UNKNOWN",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://cmr.earthdata.nasa.gov/search/concepts/{dataset_ref}.json", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"cmr concept HTTP {r.status}")
        e = safe_get(r.json(), "feed", "entry", default=[{}])[0] if "feed" in r.json() else r.json()
        return mk_candidate(provider_id=self.provider_id, title=e.get("title", dataset_ref), source_url="https://www.earthdata.nasa.gov", publisher="NASA Earthdata", access_mode="EXISTING_ACCOUNT", requires_login=True, source_ref=dataset_ref)

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "EXISTING_ACCOUNT", "requires_login": True, "restricted": False, "license": "NASA-OPEN", "notes": "granule download requires free Earthdata login (user intervention/link account)"}


@register_adapter
class UsgsAdapter(ProviderAdapter):
    """USGS ScienceBase catalog search + public file download (verified 200)."""
    provider_id = "usgs"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://www.sciencebase.gov/catalog/items", params={"q": query, "format": "json", "max": min(limit, 25), "fields": "title,summary,files"}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"sciencebase HTTP {r.status}")
        items = r.json().get("items", []) or []
        out = []
        for it in items:
            files = it.get("files", []) or []
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("title", ""),
                    source_url=f"https://www.sciencebase.gov/catalog/item/{it.get('id','')}",
                    description=(it.get("summary") or "")[:800],
                    publisher="U.S. Geological Survey",
                    license="USGOV-PUBLIC",
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    source_ref=str(it.get("id", "")),
                    direct_file_url=files[0].get("url") if files else None,
                    unit_of_analysis="UNKNOWN",
                    geography=["US"],
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://www.sciencebase.gov/catalog/item/{dataset_ref}", params={"format": "json", "fields": "title,summary,files"}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"sciencebase item HTTP {r.status}")
        it = r.json()
        files = it.get("files", []) or []
        return mk_candidate(
            provider_id=self.provider_id,
            title=it.get("title", dataset_ref),
            source_url=f"https://www.sciencebase.gov/catalog/item/{dataset_ref}",
            description=(it.get("summary") or "")[:1500],
            publisher="U.S. Geological Survey",
            license="USGOV-PUBLIC",
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
            direct_file_url=files[0].get("url") if files else None,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "USGOV-PUBLIC", "notes": "ScienceBase public files"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        r = await get(f"https://www.sciencebase.gov/catalog/item/{dataset_ref}", params={"format": "json", "fields": "files"}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"sciencebase HTTP {r.status}")
        files = r.json().get("files", []) or []
        out = []
        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
            for f in files[:5]:
                fr = await client.get(f["url"])
                if fr.status_code == 200:
                    p = Path(dest_dir) / (f.get("name") or f.get("fssid", "file"))
                    p.write_bytes(fr.content)
                    out.append(str(p))
        if not out:
            raise RuntimeError("sciencebase no public files")
        return out


@register_adapter
class HuggingFaceAdapter(ProviderAdapter):
    provider_id = "huggingface_datasets"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://huggingface.co/api/datasets", params={"search": query, "limit": min(limit, 25)}, timeout=45)
        if r.status != 200:
            raise RuntimeError(f"hf HTTP {r.status}")
        out = []
        for it in r.json() or []:
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("id", ""),
                    source_url=f"https://huggingface.co/datasets/{it.get('id','')}",
                    description=(it.get("description") or it.get("cardData", {}).get("dataset_info", {}) and "") or "UNKNOWN",
                    publisher=it.get("author", "Hugging Face community"),
                    license=str((it.get("cardData") or {}).get("license") or "UNKNOWN").upper(),
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    source_ref=it.get("id", ""),
                    unit_of_analysis="UNKNOWN",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://huggingface.co/api/datasets/{dataset_ref}", timeout=45)
        if r.status != 200:
            raise RuntimeError(f"hf dataset HTTP {r.status}")
        it = r.json()
        lic = str((it.get("cardData") or {}).get("license") or "UNKNOWN").upper()
        gated = bool(it.get("gated"))
        return mk_candidate(
            provider_id=self.provider_id,
            title=it.get("id", dataset_ref),
            source_url=f"https://huggingface.co/datasets/{dataset_ref}",
            description=(it.get("description") or "UNKNOWN")[:1500],
            publisher=it.get("author", "Hugging Face community"),
            license=lic,
            access_mode="EXISTING_ACCOUNT" if gated else "PUBLIC_ANONYMOUS_HTTP",
            requires_login=gated,
            source_ref=dataset_ref,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        r = await get(f"https://huggingface.co/api/datasets/{dataset_ref}", timeout=45)
        gated = r.status == 200 and bool(r.json().get("gated"))
        return {
            "access_mode": "EXISTING_ACCOUNT" if gated else "PUBLIC_ANONYMOUS_HTTP",
            "requires_login": gated,
            "restricted": gated,
            "license": "VARIES",
            "notes": "public parquet via datasets-server when not gated",
        }

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        r = await get(f"https://datasets-server.huggingface.co/parquet?dataset={dataset_ref}", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"hf parquet listing HTTP {r.status}")
        files = safe_get(r.json(), "parquet_files", default=[]) or []
        out = []
        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
            for f in files[:3]:
                url = f.get("urls", {}).get("parquet") if isinstance(f.get("urls"), dict) else f.get("url")
                if not url:
                    continue
                fr = await client.get(url)
                if fr.status_code == 200:
                    p = Path(dest_dir) / f"{f.get('config','data')}_{f.get('split','train')}_{f.get('filename','0.parquet')}"
                    p.write_bytes(fr.content)
                    out.append(str(p))
        if not out:
            raise RuntimeError("hf no public parquet files (gated dataset needs account)")
        return out


@register_adapter
class DryadAdapter(ProviderAdapter):
    provider_id = "dryad"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://datadryad.org/api/v2/datasets", params={"search": query, "per_page": min(limit, 25)}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"dryad HTTP {r.status}")
        out = []
        for it in (r.json().get("_embedded", {}) or {}).get("stash:datasets", []) or []:
            doi = it.get("identifier")
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("title", ""),
                    source_url=f"https://datadryad.org/datasets/doi:{doi}" if doi else "https://datadryad.org",
                    description=it.get("abstract", "")[:800],
                    publisher="Dryad",
                    doi=f"doi:{doi}" if doi else None,
                    license=str((it.get("storageSize") and "") or "UNKNOWN"),
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    source_ref=doi or "",
                    unit_of_analysis="UNKNOWN",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://datadryad.org/api/v2/datasets/doi:{dataset_ref}", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"dryad dataset HTTP {r.status}")
        it = r.json()
        return mk_candidate(provider_id=self.provider_id, title=it.get("title", dataset_ref), source_url=f"https://datadryad.org/datasets/doi:{dataset_ref}", publisher="Dryad", doi=f"doi:{dataset_ref}", access_mode="PUBLIC_ANONYMOUS_HTTP", source_ref=dataset_ref)

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES (CC0 common)", "notes": "Dryad public datasets"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        r = await get(f"https://datadryad.org/api/v2/datasets/doi:{dataset_ref}/versions", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"dryad versions HTTP {r.status}")
        vers = (r.json().get("_embedded", {}) or {}).get("stash:versions", []) or []
        if not vers:
            raise RuntimeError("dryad no versions")
        v = vers[-1]
        files = (v.get("_embedded", {}) or {}).get("stash:files", []) or []
        out = []
        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
            for f in files[:5]:
                path = f.get("path", {})
                url = f"https://datadryad.org/api/v2/files/download?path={path.get('value','')}"
                fr = await client.get(url)
                if fr.status_code == 200:
                    p = Path(dest_dir) / (path.get("value") or "file").replace("/", "_")
                    p.write_bytes(fr.content)
                    out.append(str(p))
        if not out:
            raise RuntimeError("dryad download failed")
        return out


@register_adapter
class OsfAdapter(ProviderAdapter):
    provider_id = "osf"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        r = await get("https://api.osf.io/v2/nodes/", params={"filter[title]": query, "page[size]": min(limit, 25)}, timeout=60)
        if r.status != 200:
            raise RuntimeError(f"osf HTTP {r.status}")
        out = []
        for it in r.json().get("data", []) or []:
            attrs = it.get("attributes", {})
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=attrs.get("title", ""),
                    source_url=f"https://osf.io/{it.get('id','')}",
                    description=(attrs.get("description") or "")[:800],
                    publisher="Open Science Framework",
                    license="UNKNOWN",
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    source_ref=it.get("id", ""),
                    time_start=(attrs.get("date_created") or "")[:4] or None,
                    unit_of_analysis="UNKNOWN",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        r = await get(f"https://api.osf.io/v2/nodes/{dataset_ref}/", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"osf node HTTP {r.status}")
        attrs = r.json().get("data", {}).get("attributes", {})
        return mk_candidate(provider_id=self.provider_id, title=attrs.get("title", dataset_ref), source_url=f"https://osf.io/{dataset_ref}", description=(attrs.get("description") or "")[:1500], publisher="Open Science Framework", access_mode="PUBLIC_ANONYMOUS_HTTP", source_ref=dataset_ref)

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "public OSF projects"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        r = await get(f"https://api.osf.io/v2/nodes/{dataset_ref}/files/osfstorage/", timeout=60)
        if r.status != 200:
            raise RuntimeError(f"osf files HTTP {r.status}")
        items = (r.json().get("data", []) or [])[:5]
        out = []
        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
            for it in items:
                attrs = it.get("attributes", {})
                if attrs.get("kind") != "file":
                    continue
                link = it.get("links", {}).get("download") or it.get("links", {}).get("move")
                if not link:
                    continue
                fr = await client.get(link)
                if fr.status_code == 200:
                    p = Path(dest_dir) / (attrs.get("name") or "osf_file")
                    p.write_bytes(fr.content)
                    out.append(str(p))
        if not out:
            raise RuntimeError("osf no public files")
        return out


@register_adapter
class FigshareAdapter(ProviderAdapter):
    provider_id = "figshare"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post("https://api.figshare.com/v2/articles/search", json={"search_for": query, "page_size": min(limit, 25)})
        if r.status_code != 200:
            raise RuntimeError(f"figshare HTTP {r.status_code}")
        out = []
        for it in r.json() or []:
            out.append(
                mk_candidate(
                    provider_id=self.provider_id,
                    title=it.get("title", ""),
                    source_url=it.get("url_public_html", "") or f"https://figshare.com/articles/{it.get('id','')}",
                    description="UNKNOWN",
                    publisher="Figshare",
                    doi=it.get("doi"),
                    license="UNKNOWN",
                    access_mode="PUBLIC_ANONYMOUS_HTTP",
                    source_ref=str(it.get("id", "")),
                    time_start=str(it.get("published_date", ""))[:4] or None,
                    unit_of_analysis="UNKNOWN",
                )
            )
        return out

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(f"https://api.figshare.com/v2/articles/{dataset_ref}")
        if r.status_code != 200:
            raise RuntimeError(f"figshare article HTTP {r.status_code}")
        it = r.json()
        files = it.get("files", []) or []
        return mk_candidate(
            provider_id=self.provider_id,
            title=it.get("title", dataset_ref),
            source_url=it.get("url_public_html", ""),
            description=(it.get("description") or "")[:1500],
            publisher="Figshare",
            doi=it.get("doi"),
            license=str(it.get("license", {}).get("name", "UNKNOWN")).upper(),
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
            direct_file_url=files[0].get("download_url") if files else None,
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "VARIES", "notes": "figshare public articles"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        from pathlib import Path

        import httpx

        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
            r = await client.get(f"https://api.figshare.com/v2/articles/{dataset_ref}")
            if r.status_code != 200:
                raise RuntimeError(f"figshare HTTP {r.status_code}")
            files = r.json().get("files", []) or []
            out = []
            for f in files[:5]:
                fr = await client.get(f["download_url"])
                if fr.status_code == 200:
                    p = Path(dest_dir) / f.get("name", "figshare_file")
                    p.write_bytes(fr.content)
                    out.append(str(p))
        if not out:
            raise RuntimeError("figshare download failed")
        return out


@register_adapter
class WikidataAdapter(ProviderAdapter):
    provider_id = "wikidata"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        # Wikidata is a knowledge graph, not a dataset repo: surface a SPARQL-accessible candidate.
        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=f"Wikidata SPARQL query: {query}",
                source_url="https://www.wikidata.org",
                description="Structured knowledge graph; query via WDQS SPARQL endpoint. Not a file-based dataset repository.",
                publisher="Wikimedia",
                license="CC0-1.0",
                access_mode="PUBLIC_ANONYMOUS_API",
                source_ref=query,
                unit_of_analysis="entity",
            )
        ]

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        return (await self.search_datasets(dataset_ref))[0]

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_API", "requires_login": False, "restricted": False, "license": "CC0-1.0", "notes": "SPARQL endpoint; UA policy applies"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        import urllib.parse
        from pathlib import Path

        sparql = (access_context or {}).get("sparql")
        if not sparql:
            raise RuntimeError("wikidata acquire requires a SPARQL query in access_context['sparql']")
        url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(sparql)
        r = await get(url, timeout=120, headers={"User-Agent": "MetisData/1.0 (research data agent)"}, max_retries=1)
        if r.status != 200:
            raise RuntimeError(f"wikidata HTTP {r.status}")
        p = Path(dest_dir) / "wikidata_result.json"
        p.write_bytes(r.content)
        return [str(p)]


@register_adapter
class NbsChinaAdapter(ProviderAdapter):
    """国家统计局“国家数据” (data.stats.gov.cn).

    EasyQuery needs session cookies from first visit. If anti-bot blocks anonymous
    HTTP, adapter raises and the provider is recorded as browser-required with audit
    evidence (no fake success).
    """
    provider_id = "nbs_china"

    async def search_datasets(self, query: str, filters: dict | None = None, limit: int = 20) -> list[DatasetCandidate]:
        # 国家数据 organizes yearly data by indicator tree (hgnd). The tree fetch is public.

        indicator_map = {
            "gdp": "A020101", "人均": "A020201", "总人口": "A030101", "失业": "A040101",
            "education": "A0C01", "教育": "A0C01", "cpi": "A090201", "工资": "A0E01",
        }
        matched = [code for k, code in indicator_map.items() if k in query.lower()]
        r = await get("https://data.stats.gov.cn/easyquery.htm", params={"id": "zb", "dbcode": "hgnd", "wdcode": "zb", "m": "getTree"}, timeout=30, max_retries=0)
        if r.status != 200:
            raise RuntimeError(f"nbs tree HTTP {r.status}")
        tree = r.json()
        if isinstance(tree, dict) and tree.get("returncode") == 200 or isinstance(tree, list):
            nodes = tree if isinstance(tree, list) else tree.get("data", [])
            names = {n.get("id"): n.get("name") or n.get("cname") for n in nodes if isinstance(n, dict)}
            out = []
            for nid, name in list(names.items())[:200]:
                nl = str(name or "")
                if matched or any(k in nl for k in ("国内生产总值", "失业", "教育", "人均")):
                    out.append(
                        mk_candidate(
                            provider_id=self.provider_id,
                            title=nl or str(nid),
                            source_url=f"https://data.stats.gov.cn/easyquery.htm?cn=C01&zb={nid}",
                            description=f"国家统计局年度数据指标 {nid}",
                            publisher="National Bureau of Statistics of China",
                            license="NBS open access (attribution)",
                            access_mode="PUBLIC_ANONYMOUS_HTTP",
                            source_ref=str(nid),
                            unit_of_analysis="country",
                            geography=["CN"],
                        )
                    )
                if len(out) >= limit:
                    break
            return out
        raise RuntimeError(f"nbs unexpected tree response: {str(tree)[:120]}")

    async def get_dataset_metadata(self, dataset_ref: str) -> DatasetCandidate:
        return mk_candidate(
            provider_id=self.provider_id,
            title=f"NBS indicator {dataset_ref}",
            source_url=f"https://data.stats.gov.cn/easyquery.htm?cn=C01&zb={dataset_ref}",
            description="国家统计局年度数据指标",
            publisher="National Bureau of Statistics of China",
            license="NBS open access (attribution)",
            access_mode="PUBLIC_ANONYMOUS_HTTP",
            source_ref=dataset_ref,
            unit_of_analysis="country",
            geography=["CN"],
        )

    async def get_access_requirements(self, dataset_ref: str) -> dict:
        return {"access_mode": "PUBLIC_ANONYMOUS_HTTP", "requires_login": False, "restricted": False, "license": "NBS-OPEN", "notes": "EasyQuery; anonymous HTTP may be rate-limited"}

    async def acquire_dataset(self, dataset_ref: str, dest_dir, access_context: dict | None = None) -> list[str]:
        import json as _json
        from pathlib import Path

        params = {
            "m": "QueryData", "dbcode": "hgnd", "rowcode": "zb", "colcode": "sj",
            "wds": "[]", "dfwds": _json.dumps([{"wdcode": "zb", "valuecode": dataset_ref}]),
            "k1": str(int(__import__("time").time() * 1000)),
        }
        r = await get("https://data.stats.gov.cn/easyquery.htm", params=params, timeout=60, max_retries=1)
        if r.status != 200:
            raise RuntimeError(f"nbs data HTTP {r.status}")
        body = r.json()
        if body.get("returncode") != 200:
            raise RuntimeError(f"nbs data error: {str(body)[:150]}")
        p = Path(dest_dir) / f"nbs_{dataset_ref}.json"
        p.write_bytes(r.content)
        return [str(p)]
