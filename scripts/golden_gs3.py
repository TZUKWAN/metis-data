"""GS-3 科研数据仓库：search ≥2 research repositories + acquire a real public dataset.

Zenodo / Harvard Dataverse / OSF / Figshare — pick whichever yields a small public
file; failures (rate limits, no public files) recorded as BLOCKED with evidence.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metis" / "backend"))

QUERY = "大学生 generative AI survey data"
REPOS = ["zenodo", "harvard_dataverse", "osf", "figshare"]


async def main() -> int:
    from app.core.config import get_settings

    get_settings().ensure_dirs()
    from app.db.session import init_db

    init_db()
    from app.db.repository import REPO
    from app.downloads.service import MANAGER
    from app.providers.base import get_adapter
    from app.search.dedup import deduplicate

    report: dict = {"scenario": "GS-3 research repositories", "query": QUERY, "started": time.time(), "repos": {}}

    # ---- search at least 2 repositories ----
    searched = []
    for pid in REPOS[:2]:
        try:
            adapter = get_adapter(pid)
            cands = await adapter.search_datasets("generative AI students survey", limit=5)
            searched.append({"provider_id": pid, "n": len(cands), "top": cands[0].model_dump(mode="json") if cands else None})
            report["repos"][pid] = {"search": "OK", "n": len(cands)}
        except Exception as e:  # noqa: BLE001
            report["repos"][pid] = {"search": "ERROR", "error": f"{type(e).__name__}: {e}"[:200]}
    assert len(searched) >= 2 and any(r.get("n", 0) > 0 for r in report["repos"].values()), "GS-3 needs 2 repos searched with results"

    # ---- dedupe across repos ----
    all_cands = []
    for pid in REPOS[:2]:
        try:
            adapter = get_adapter(pid)
            all_cands.extend(await adapter.search_datasets(QUERY, limit=5))
        except Exception:  # noqa: BLE001
            pass
    groups = deduplicate([c.model_dump(mode="json") for c in all_cands])
    report["dedup_groups"] = len(groups)

    # ---- acquire the first candidate with a direct public file (DOI recorded) ----
    acquired = None
    blocked = []
    for pid in REPOS[:2]:
        try:
            adapter = get_adapter(pid)
            cands = await adapter.search_datasets(QUERY if pid != "harvard_dataverse" else "generative AI", limit=5)
            if not cands:
                blocked.append(f"{pid}: no candidates")
                continue
            ref = cands[0].files[0].source_ref or cands[0].source_ref
            with tempfile.TemporaryDirectory() as td:
                files = await adapter.acquire_dataset(ref, td, {})
                if files and Path(files[0]).stat().st_size > 0:
                    job = MANAGER.create_job(pid, ref, cands[0].sources[0].source_url, license=cands[0].license)
                    job2 = REPO.get_download_job(job.download_job_id)
                    from pathlib import Path as _P

                    info = await MANAGER._verify_and_commit(_P(files[0]), job2, _P(files[0]).stat().st_size)
                    acquired = {"provider_id": pid, "ref": ref, "sha256": info["sha256"][:16], "size": info["size"], "doi": cands[0].doi, "license": cands[0].license}
                    break
        except Exception as e:  # noqa: BLE001
            blocked.append(f"{pid}: {type(e).__name__}: {str(e)[:160]}")

    report["acquired"] = acquired
    report["blocked"] = blocked
    report["result"] = "PASS" if acquired else "BLOCKED"
    report["duration_s"] = round(time.time() - report["started"], 1)
    out = ROOT / "metis" / "artifacts" / "golden_gs3_research.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GS-3: {report['result']} in {report['duration_s']}s -> {out}")
    if acquired:
        print(f"  acquired from {acquired['provider_id']} ref={acquired['ref']} doi={acquired['doi']}")
    for b in blocked:
        print(f"  blocked: {b}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
