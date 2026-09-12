"""Phase E/F acceptance: unified AcquisitionService — descriptor (v2) path + legacy fallback.

Uses a local http.server serving tests/fixtures/data (same approach as conftest.fixture_server)
as the download source, a stub adapter registered by monkeypatching
app.acquisition.service.get_adapter, and a real MANAGER.create_job DownloadJob so the
existing raw commit path (_verify_and_commit) runs for real.
"""
from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

FIXTURE_DATA_DIR = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture(scope="module")
def data_server():
    """Local HTTP server rooted at tests/fixtures/data."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(FIXTURE_DATA_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base}/panel_data.csv", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


class StubAdapter:
    """Adapter v2: describes where the bytes live; never downloads itself."""

    provider_id = "stub"

    def __init__(self, csv_url: str) -> None:
        self.csv_url = csv_url

    async def build_acquisition_descriptor(self, dataset_ref, access_context=None):
        from app.providers.download_helper import AcquisitionDescriptor

        return AcquisitionDescriptor(url=self.csv_url, filename="panel.csv", expected_type="csv")


def _authorized_access_job(provider_id: str, download_job_id: str) -> dict:
    from app.access.machine import AccessState, create_access_job, transition
    from app.db.repository import REPO

    job = create_access_job(provider_id, candidate_id="panel", download_job_id=download_job_id)
    transition(job, AccessState.INSPECTING, "test: inspecting")
    transition(job, AccessState.PUBLIC, "test: public source")
    transition(job, AccessState.AUTHORIZED, "test: authorized")
    return REPO.get_access_job(job.access_job_id)


def _download_job_dict(provider_id: str, source_url: str) -> dict:
    from app.db.repository import REPO
    from app.downloads.service import MANAGER

    created = MANAGER.create_job(provider_id, "panel", source_url, license="CC0-1.0")
    return REPO.get_download_job(created.download_job_id)


def test_acquire_descriptor_path_commits_via_manager(temp_workspace, data_server, monkeypatch):
    """v2 descriptor → stream_to_file → _verify_and_commit: artifact registered, job COMPLETED."""
    import app.acquisition.service as acq_mod
    from app.acquisition.service import ACQUISITION
    from app.core import paths
    from app.db.repository import REPO

    adapter = StubAdapter(f"{data_server}/panel_data.csv")
    monkeypatch.setattr(acq_mod, "get_adapter", lambda provider_id: adapter)

    dl = _download_job_dict("stub", f"{data_server}/panel_data.csv")
    access_job = _authorized_access_job("stub", dl["download_job_id"])
    staging = paths.workspace_root() / "downloads" / dl["download_job_id"]

    files = asyncio.run(ACQUISITION.acquire(access_job, dl, staging))

    assert files, "acquire must return the committed file paths"
    committed = Path(files[0])
    assert committed.exists(), "committed file must exist in raw/"
    assert "country_name,iso3,year,gdp_per_capita" in committed.read_text(encoding="utf-8")

    saved = REPO.get_download_job(dl["download_job_id"])
    assert saved["status"] == "COMPLETED"
    assert saved["files"], "download job must list committed files"
    assert saved["files"][0]["sha256"]

    artifacts = [a for a in REPO.list_artifacts() if a["download_job_id"] == dl["download_job_id"]]
    assert artifacts, "artifact must be registered"
    assert artifacts[0]["checksum_sha256"] == saved["files"][0]["sha256"]
    # nothing half-downloaded left behind
    assert not list(staging.glob("*.partial"))


def test_acquire_legacy_fallback_when_descriptor_fails(temp_workspace, data_server, monkeypatch):
    """v2 build raises → adapter.acquire_dataset runs (legacy), commit still COMPLETED + UI event."""
    import app.acquisition.service as acq_mod
    from app.acquisition.service import ACQUISITION
    from app.core import paths
    from app.core.errors import MetisError
    from app.db.repository import REPO

    class LegacyOnlyAdapter(StubAdapter):
        async def build_acquisition_descriptor(self, dataset_ref, access_context=None):
            raise MetisError("PROVIDER_CAPABILITY_MISSING", "no v2 descriptor for stub")

        async def acquire_dataset(self, dataset_ref, dest_dir, access_context=None):
            dest = Path(dest_dir) / "legacy_panel.csv"
            shutil.copyfile(FIXTURE_DATA_DIR / "panel_data.csv", dest)
            return [str(dest)]

    adapter = LegacyOnlyAdapter(f"{data_server}/panel_data.csv")
    monkeypatch.setattr(acq_mod, "get_adapter", lambda provider_id: adapter)

    dl = _download_job_dict("stub", f"{data_server}/panel_data.csv")
    access_job = _authorized_access_job("stub", dl["download_job_id"])
    staging = paths.workspace_root() / "downloads" / dl["download_job_id"]

    files = asyncio.run(ACQUISITION.acquire(access_job, dl, staging))

    assert files and Path(files[0]).exists()
    saved = REPO.get_download_job(dl["download_job_id"])
    assert saved["status"] == "COMPLETED"
    assert saved["files"]
    events = [e for e in REPO.list_ui_events(limit=200) if e["kind"] == "acquisition.legacy_fallback"]
    assert events, "legacy fallback must be auditable via UI event"
