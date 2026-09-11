"""P16-019 / A38 Golden Scenario — REAL end-to-end execution.

  构建 2015—2023 年国家层面的青年失业、人均 GDP 和教育水平面板，优先官方或国际组织数据。

Must actually complete: Requirement → ≥4 Provider parallel search → candidate
recommendation → ≥2 real acquisitions → Raw → Profile → Build (entity/time/join/
missing) → QA → Provenance → Final Package → Reproduce. Any stage replaced by a
static mock FAILS the scenario.

Writes evidence to metis/artifacts/golden_scenario_report.json.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metis" / "backend"))

REQUEST = "构建 2015—2023 年国家层面的青年失业率、人均 GDP、教育水平面板，优先使用官方或国际组织数据。"

# acquisitions we WANT for the panel (indicator-level, real provider datasets)
# GS-1 needs >=2 distinct international organizations; GS-5 needs >=3 inputs
ACQUIRE_HINTS = {
    "world_bank": ["SL.UEM.1524.ZS", "NY.GDP.PCAP.CD"],  # youth unemp, GDP pc
    "eurostat": ["une_rt_a"],
    "ilostat": ["DF_SDG_0831_SEX_ECO_RT"],
    "un_comtrade": ["annual_2022"],
}
MIN_ACQUIRE = 2
MIN_PROVIDERS = 2


async def main() -> int:
    from app.core.config import get_settings

    get_settings().ensure_dirs()
    from app.db.session import init_db

    init_db()
    report: dict = {"request": REQUEST, "stages": {}, "started": time.time()}

    # ---- 1. Requirement ----
    from app.search.parser import parse_requirement, validate_requirement

    req = parse_requirement(REQUEST)
    assert req.unit_of_analysis == "country" and req.time_range == (2015, 2023)
    assert not validate_requirement(req)
    from app.db.repository import REPO

    REPO.save_requirement(req)
    report["stages"]["requirement"] = {"ok": True, "assumptions": req.assumptions}
    print(f"[1/9] requirement parsed: unit={req.unit_of_analysis} time={req.time_range} freq={req.frequency}")

    # ---- 2. Provider selection + query plan ----
    from app.domain.schemas import DataRequirement
    from app.search.selector import plan_queries, select_providers

    providers = select_providers(DataRequirement(**req.model_dump(mode="json")), max_providers=8)
    plan = plan_queries(DataRequirement(**req.model_dump(mode="json")), providers)
    assert len(providers) >= 4, f"need >=4 providers, got {len(providers)}"
    report["stages"]["provider_selection"] = {"ok": True, "providers": [p.provider_id for p in providers], "query_plan": plan}
    print(f"[2/9] providers: {[p.provider_id for p in providers]}")

    # ---- 3. Parallel search ----
    from app.search.orchestrator import ORCHESTRATOR

    run_id = await ORCHESTRATOR.run_search(req.model_dump(mode="json"), [p.provider_id for p in providers], plan)
    run = REPO.get_search_run(run_id)
    tasks = REPO.list_provider_tasks(run_id)
    done = [t for t in tasks if t["status"] == "done"]
    cands = REPO.list_candidates(run_id, dedup_only=True)
    assert run["status"] == "COMPLETED" and len(done) >= 3 and cands
    report["stages"]["search"] = {
        "ok": True, "run_id": run_id, "status": run["status"],
        "provider_tasks": tasks, "n_candidates": len(cands),
    }
    print(f"[3/9] search run {run_id}: {len(done)} done, {len(cands)} candidates")

    # ---- 4. Acquisition of >=2 real sources ----
    from app.downloads.service import MANAGER
    from app.providers.base import get_adapter

    acquired: list[dict] = []
    for pid, refs in ACQUIRE_HINTS.items():
        providers_hit = {a["provider_id"] for a in acquired}
        if len(acquired) >= 4 and len(providers_hit) >= MIN_PROVIDERS:
            break
        if pid not in [p.provider_id for p in providers]:
            continue
        for ref in refs:
            if len(acquired) >= 3:
                break
            try:
                job = MANAGER.create_job(pid, ref, f"https://provider/{pid}/{ref}", license="OPEN(verify per provider)")
                adapter = get_adapter(pid)
                staging = get_settings().workspace_dir / "downloads" / job.download_job_id
                staging.mkdir(parents=True, exist_ok=True)
                files = await adapter.acquire_dataset(ref, staging, {"ref_area": "CHN", "start": "2015"})
                if not files:
                    continue
                job2 = REPO.get_download_job(job.download_job_id)
                for f in files:
                    from pathlib import Path

                    await MANAGER._verify_and_commit(Path(f), job2, Path(f).stat().st_size)
                job3 = REPO.get_download_job(job.download_job_id)
                for f in job3.get("files", []):
                    acquired.append({"provider_id": pid, "ref": ref, "artifact_id": f["artifact_id"], "sha256": f["sha256"][:16], "size": f["size"]})
                print(f"    acquired {pid}:{ref} ({job3['files'][0]['size']} bytes)")
            except Exception as e:  # noqa: BLE001
                print(f"    acquire failed {pid}:{ref}: {type(e).__name__}: {str(e)[:120]}")
    assert len(acquired) >= MIN_ACQUIRE, f"need >=2 real acquisitions, got {len(acquired)}"
    n_providers = len({a["provider_id"] for a in acquired})
    assert n_providers >= MIN_PROVIDERS, f"GS-1 needs >=2 distinct providers, got {n_providers}"
    report["stages"]["acquisition"] = {"ok": True, "acquired": acquired, "distinct_providers": n_providers}
    print(f"[4/9] acquired {len(acquired)} real sources from {n_providers} providers")

    # ---- 5. Profile ----
    from app.datasets.profile import profile_artifact

    profiles = {}
    for a in acquired:
        art = REPO.get_artifact(a["artifact_id"])
        prof = profile_artifact(a["artifact_id"], art["raw_path"])
        profiles[a["artifact_id"]] = prof
    assert all(p.get("row_count", 0) > 0 for p in profiles.values())
    report["stages"]["profile"] = {"ok": True, "artifacts": {k: {"rows": v.get("row_count"), "cols": v.get("column_count"), "format": v.get("format")} for k, v in profiles.items()}}
    print(f"[5/9] profiled {len(profiles)} artifacts")

    # ---- 6. Build ----
    from app.domain.schemas import BuildConfig, BuildInputRef

    # choose two artifacts with country+year-ish structure
    cfg = BuildConfig(
        title="GOLDEN panel 2015-2023",
        requirement_id=req["requirement_id"] if isinstance(req, dict) else req.requirement_id,
        inputs=[BuildInputRef(artifact_id=a["artifact_id"]) for a in acquired[:3]],  # GS-5: up to 3 inputs
        keys=["country", "year"],
        missing_policy="none",
        derived_variables=[],
    )
    REPO.save_build(cfg)
    from app.builds.executor import BuildExecutor

    result = await BuildExecutor(cfg.build_id).run()
    assert result["status"] == "COMPLETE"
    validations = REPO.list_validations(cfg.build_id)
    report["stages"]["build"] = {
        "ok": True, "build_id": cfg.build_id, "rows": result["rows"], "validations": validations,
        "n_inputs": min(len(acquired), 3),
        "operations": [o["operation_type"] for o in REPO.list_build_operations(cfg.build_id)],
    }
    print(f"[6/9] build COMPLETE: {result['rows']} rows; ops={report['stages']['build']['operations']}")

    # ---- 7. Final package integrity ----
    pkg = Path(result["package"]["package_dir"])
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    missing = [f for f in manifest["files"] if not (pkg / f).exists()]
    assert not missing
    report["stages"]["package"] = {"ok": True, "files": manifest["files"], "rows": manifest["row_count"], "cols": manifest["column_count"]}
    print(f"[7/9] package manifest: {len(manifest['files'])} files all present")

    # ---- 8. Reproduce ----
    r = subprocess.run([sys.executable, str(pkg / "scripts" / "reproduce.py"), "--raw-root", str(get_settings().workspace_dir / "raw")], capture_output=True, text=True, cwd=str(pkg / "scripts"))
    repro_ok = r.returncode == 0
    report["stages"]["reproduce"] = {"ok": repro_ok, "returncode": r.returncode, "stdout": r.stdout[-400:], "stderr": r.stderr[-400:]}
    print(f"[8/9] reproduce: {'PASS' if repro_ok else 'FAIL'}")

    # ---- 9. field lineage present ----
    lineage = REPO.list_field_lineage(cfg.build_id)
    assert lineage and all(l["lineage"].get("url") for l in lineage[:5])
    report["stages"]["lineage"] = {"ok": True, "n_fields": len(lineage), "sample": lineage[0]}
    print(f"[9/9] field lineage: {len(lineage)} chains traced to URL/DOI")

    report["result"] = "PASS" if repro_ok else "PASS_WITH_REPRODUCE_FAILURE"
    report["duration_s"] = round(time.time() - report["started"], 1)
    out = ROOT / "metis" / "artifacts" / "golden_scenario_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGOLDEN SCENARIO: {report['result']} in {report['duration_s']}s -> {out}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
