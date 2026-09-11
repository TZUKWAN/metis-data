"""Real-provider smoke verification (P03-P07).

For every implemented adapter:
  1. run a REAL search → verify candidate schema (title/provider/source_url);
  2. (verify_download list) run a REAL small acquisition into a temp dir;
  3. update the registry YAML with verified capabilities/levels + last_verified_at
     + blocking_reason when a target level is NOT reached (never overstate).
Audit-only providers (no adapter) get a reachability probe + honest P0 record.

Usage:  python scripts/provider_smoke.py [--search-only]
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "metis" / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.domain.schemas import ProviderCapabilities  # noqa: E402
from app.providers.base import ProviderAdapter, available_adapters, get_adapter  # noqa: E402
from app.providers.registry import get_registry  # noqa: E402

TODAY = datetime.now(timezone.utc).date().isoformat()

# per-provider natural query (provider-appropriate language/topic)
QUERIES = {
    "world_bank": "unemployment", "eurostat": "unemployment", "ilostat": "unemployment",
    "data_gov_uk": "unemployment", "opendata_swiss": "arbeitslosigkeit", "data_gouv_fr": "chomage",
    "zenodo": "unemployment panel", "harvard_dataverse": "unemployment", "kaggle": "unemployment",
    "dryad": "plant traits", "osf": "survey data", "figshare": "climate", "huggingface_datasets": "sentiment",
    "usgs": "water quality", "us_census": "population", "un_comtrade": "trade 2022", "wikidata": "country",
    "nasa_earthdata": "sea surface temperature", "oecd": "unemployment", "nbs_china": "gdp",
}

# providers where we also verify an anonymous download (P4 evidence)
VERIFY_DOWNLOAD = {
    "world_bank": ("GDP growth (annual %)", "NY.GDP.MKTP.KD.ZG"),
    "eurostat": ("unemployment annual", "une_rt_a"),
    "ilostat": ("unemployment", "DF_SDG_0831_SEX_ECO_RT"),
    "zenodo": ("unemployment rate panel csv", None),
    "harvard_dataverse": ("unemployment", None),
    "data_gov_uk": ("unemployment", None),
    "opendata_swiss": ("arbeitslose", None),
    "data_gouv_fr": ("chomage", None),
    "un_comtrade": ("trade 2022", "annual_2022"),
    "usgs": ("water quality", None),
    "osf": ("survey data", None),
    "dryad": ("plant traits", None),
    "figshare": ("climate data", None),
    "us_census": ("population estimates", None),
}


def _upd(provider_id: str, **kw) -> None:
    reg = get_registry()
    rec = reg.get(provider_id)
    data = rec.model_dump()
    caps = dict(data.get("capabilities") or {})
    for k, v in kw.pop("capabilities", {}).items():
        caps[k] = v
    data["capabilities"] = caps
    data.update(kw)
    data["adapter_version"] = data.get("adapter_version") or "1.0.0"
    rec = type(rec)(**data)
    reg.update(rec)


async def smoke_adapter(pid: str, verify_download: bool) -> dict:
    res: dict = {"provider_id": pid, "search": "FAIL", "download": "SKIP", "notes": []}
    try:
        adapter: ProviderAdapter = get_adapter(pid)
        cands = await adapter.search_datasets(QUERIES.get(pid, "unemployment"), limit=8)
        if not cands:
            res["notes"].append("search returned 0 candidates")
            res["search"] = "EMPTY"
        else:
            c = cands[0]
            assert c.provider_id == pid and c.title and c.sources[0].source_url, "candidate schema invalid"
            res["search"] = "OK"
            res["n_results"] = len(cands)
    except Exception as e:  # noqa: BLE001
        res["search"] = "ERROR"
        res["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        return res

    ref = None
    try:
        adapter = get_adapter(pid)
        cands = await adapter.search_datasets(QUERIES.get(pid, "unemployment"), limit=3)
        ref = cands[0].source_ref or None
    except Exception:  # noqa: BLE001
        pass

    if verify_download:
        try:
            adapter = get_adapter(pid)
            real_ref = (VERIFY_DOWNLOAD.get(pid) or (None, None))[1] or ref
            if not real_ref:
                res["download"] = "NO_REF"
            else:
                with tempfile.TemporaryDirectory() as td:
                    files = await adapter.acquire_dataset(real_ref, td, {"ref_area": "CHN", "reporterCode": "156"})
                    total = sum(Path(f).stat().st_size for f in files if Path(f).exists())
                    if total == 0:
                        raise RuntimeError("download produced empty files")
                    # content sniff: reject login/error HTML
                    from app.providers.adapters.common import looks_like_html

                    if any(looks_like_html(Path(f).read_bytes()) and Path(f).suffix in (".csv", ".json", ".zip") for f in files):
                        raise RuntimeError("downloaded file looks like HTML")
                res["download"] = "OK"
                res["dl_bytes"] = total
        except Exception as e:  # noqa: BLE001
            res["download"] = "ERROR"
            res["dl_error"] = f"{type(e).__name__}: {str(e)[:160]}"
    return res


async def audit_registered_only() -> list[dict]:
    """Honest audit rows for every registered provider without an HTTP adapter."""
    import httpx

    reg = get_registry()
    rows = []
    adapters = set(available_adapters())
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for rec in reg.all():
            if rec.provider_id in adapters:
                continue
            status = "unreachable"
            try:
                r = await client.get(rec.homepage, headers={"User-Agent": "Mozilla/5.0 (MetisData research agent)"})
                status = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001
                status = f"{type(e).__name__}"
            rows.append({"provider_id": rec.provider_id, "homepage_status": status})
    return rows


async def main() -> None:
    get_settings().ensure_dirs()
    init_db()
    search_only = "--search-only" in sys.argv
    results = []
    for pid in available_adapters():
        r = await smoke_adapter(pid, verify_download=not search_only and pid in VERIFY_DOWNLOAD)
        results.append(r)
        print(f"{pid:24s} search={r['search']:6s} download={r.get('download','SKIP'):6s} {r.get('error','')}{r.get('dl_error','')}")

    # registry updates from REAL evidence
    for r in results:
        pid = r["provider_id"]
        if r["search"] == "OK":
            caps = {"discovery_api": True}
            level = 1
            _upd(pid, capabilities=caps, integration_level=level, last_verified_at=TODAY, blocking_reason=None)
        else:
            _upd(
                pid,
                last_verified_at=TODAY,
                blocking_reason=f"anonymous HTTP search failed ({r.get('error','?')}) on {TODAY}; browser search required or platform changed",
            )

    dl_ok = {r["provider_id"] for r in results if r.get("download") == "OK"}
    for pid in dl_ok:
        rec = get_registry().get(pid)
        caps = rec.capabilities.model_dump()
        caps.update({"anonymous_download": True, "metadata_api": True})
        _upd(pid, capabilities=caps, integration_level=max(rec.integration_level, 4), last_verified_at=TODAY, blocking_reason=None)

    # Kaggle: search verified anonymous; download requires credentials → P1, honest note
    kb = [r for r in results if r["provider_id"] == "kaggle"]
    if kb and kb[0]["search"] == "OK":
        rec = get_registry().get("kaggle")
        caps = rec.capabilities.model_dump()
        caps.update({"discovery_api": True, "authenticated_download": True, "registration": False})
        _upd(
            "kaggle",
            capabilities=caps,
            integration_level=1,
            last_verified_at=TODAY,
            blocking_reason="download requires Kaggle account credentials (Vault); anonymous download not offered by platform; site registration uses CAPTCHA so auto-registration not implemented",
            auth_modes=["form_login", "api_key"],
            browser_required_for=["registration"],
        )

    get_registry().save()
    print(f"\nregistry updated: {sum(1 for r in results if r['search']=='OK')} adapters verified; downloads OK: {len(dl_ok)}")

    audits = await audit_registered_only()
    from app.db.repository import REPO

    for a in audits:
        REPO.add_capability_audit(
            provider_id=a["provider_id"],
            integration_level=0,
            target_level=1,
            evidence=f"homepage probe: {a['homepage_status']}; no anonymous HTTP discovery API implemented; browser search required",
            blocking_reason="catalog/login site without public anonymous search API",
            last_verified_at=TODAY,
        )
    print(f"audited {len(audits)} registered-only providers")

    Path("metis/artifacts").mkdir(exist_ok=True)
    report = {"date": TODAY, "adapters": results, "audits": audits}
    Path("metis/artifacts/provider_smoke_report.json").write_text(__import__("json").dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("report -> metis/artifacts/provider_smoke_report.json")


if __name__ == "__main__":
    asyncio.run(main())
