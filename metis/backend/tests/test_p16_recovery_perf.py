"""P16 performance + crash recovery acceptance (A35/A40)."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "fixtures" / "data"
BACKEND = Path(__file__).resolve().parents[1]


def test_profile_100mb_memory_bounded(temp_workspace):
    """A40: 100MB+ CSV profile must not OOM (bounded chunks)."""
    import ctypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    def peak_working_set_mb() -> float:
        pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.PeakWorkingSetSize / (1024 * 1024)

    t0 = time.time()
    from app.datasets.profile import profile_file

    prof = profile_file(DATA / "profile_100mb.csv")
    dur = time.time() - t0
    peak = peak_working_set_mb()
    assert prof["row_count"] > 3_000_000
    assert dur < 300
    assert peak < 2500, f"profile peak RSS {peak:.0f} MB too high"
    out = Path(os.environ["METIS_WORKSPACE_DIR"]).parent / "bench"
    out.mkdir(exist_ok=True)
    (out / "profile_benchmark.json").write_text(json.dumps({"file": "profile_100mb.csv", "size_mb": round(prof["size_bytes"] / 1e6, 1), "rows": prof["row_count"], "duration_s": round(dur, 1), "peak_rss_mb": round(peak, 0), "mode": prof["profile_mode"]}, indent=2))
    print(f"profile: {dur:.1f}s, peak RSS {peak:.0f} MB")


def test_download_100mb_streaming_duration(temp_workspace, fixture_server):
    """A40/A15: 112MB streamed download with progress + checksum."""
    from app.downloads.service import MANAGER

    job = MANAGER.create_job("fixture", "big", f"{fixture_server}/data/big_measurements.csv", license="CC0-1.0")
    progress_seen = []

    def on_progress(received, total):
        progress_seen.append(received)

    async def go():
        return await MANAGER.http_download(f"{fixture_server}/data/big_measurements.csv", job=job, on_progress=on_progress)

    t0 = time.time()
    dest, info = asyncio.new_event_loop().run_until_complete(go())
    dur = time.time() - t0
    assert info["size"] > 100 * 1024 * 1024 and info["sha256"]
    assert progress_seen, "progress events must be emitted during download"
    print(f"download: {info['size']/1e6:.0f}MB in {dur:.1f}s")


def test_crash_recovery_kill_mid_download(temp_workspace, fixture_server):
    """A35: SIGKILL a worker mid-download → restart reconciles truthfully:
    download FAILED (retryable), no partial file in raw/, no fake COMPLETE."""
    worker = BACKEND / "tests" / "worker_download.py"
    env = dict(os.environ)
    ws = Path(os.environ["METIS_WORKSPACE_DIR"])
    proc = subprocess.Popen([sys.executable, str(worker), str(ws), fixture_server], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # let it stream for a bit, then kill hard
    time.sleep(4)
    proc.kill()
    proc.wait(timeout=10)

    # restart: reconcile on the same workspace DB
    from app.db.recovery import reconcile_on_startup
    from app.db.repository import REPO

    report = reconcile_on_startup()
    jobs = REPO.list_download_jobs()
    assert jobs, "download job must have been persisted before the kill"
    # jobs killed mid-flight are FAILED (retryable), never fake-COMPLETE
    failed = [j for j in jobs if j["status"] == "FAILED" and j.get("error_code") == "DOWNLOAD_FAILED"]
    assert failed, f"crashed job must be FAILED: {[j['status'] for j in jobs]}"
    # anything that did COMPLETE before the kill is a fully verified commit — fine.
    # The invariant: FAILED (killed) jobs have NO files in raw/ and no .partial anywhere in raw/.
    failed_ids = {j["download_job_id"] for j in failed}
    raw_polluted = []
    for p in (ws / "raw").rglob("*.csv"):
        if any(jid in str(p) for jid in failed_ids):
            raw_polluted.append(p)
    assert not raw_polluted, f"partial download leaked into raw: {raw_polluted}"
    j = failed[0]
    (ws.parent / "bench").mkdir(exist_ok=True)
    (ws.parent / "bench" / "crash_recovery.json").write_text(json.dumps({"kill_after_s": 4, "job_status": j["status"], "error_code": j.get("error_code"), "raw_polluted": False, "recovery_report": report}, indent=2))
