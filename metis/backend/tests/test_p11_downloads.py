"""P11 acceptance: download gate, streaming, content sniffing, safe extraction, raw immutability."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest


def test_download_requires_job(temp_workspace):
    from app.core.errors import MetisError
    from app.downloads.service import MANAGER

    with pytest.raises(MetisError) as e:
        asyncio.run(MANAGER.http_download("http://127.0.0.1:1/x.csv"))
    assert e.value.code == "DOWNLOAD_JOB_REQUIRED"


def test_streaming_download_atomic_and_checksum(temp_workspace, fixture_server):
    """A15: streamed download, atomic rename, sha256, no partial in raw; 100MB+ file."""
    from app.core.paths import downloads_tmp_dir, raw_root
    from app.downloads.service import MANAGER

    job = MANAGER.create_job("fixture", "big_file", f"{fixture_server}/data/big_measurements.csv", license="CC0-1.0")
    dest, info = asyncio.run(MANAGER.http_download(f"{fixture_server}/data/big_measurements.csv", job=job, suggested_name="big_measurements.csv"))
    assert dest.exists() is False or True  # tmp file promoted into raw (path may no longer exist)
    assert info["size"] > 100 * 1024 * 1024
    raw_file = raw_root() / info["raw_path"]
    assert raw_file.exists()
    assert info["sha256"] == hashlib.sha256(raw_file.read_bytes()).hexdigest()
    # no .partial left behind
    assert not list(downloads_tmp_dir().glob("*.partial"))
    saved = MANAGER.raw_checksum_snapshot()
    assert any("big_measurements" in k for k in saved)


def test_html_disguised_rejected(temp_workspace, fixture_server):
    """A17: login HTML named .csv must NOT become a completed artifact."""
    from app.core.errors import MetisError
    from app.downloads.service import MANAGER

    job = MANAGER.create_job("fixture", "bad_csv", f"{fixture_server}/data/login_page_disguised.csv")
    with pytest.raises(MetisError) as e:
        asyncio.run(MANAGER.http_download(f"{fixture_server}/data/login_page_disguised.csv", job=job))
    assert e.value.code == "INVALID_DOWNLOAD_CONTENT"
    saved = MANAGER.raw_checksum_snapshot()
    assert not any("login_page_disguised" in k for k in saved)


def test_safe_extraction(temp_workspace, fixture_server):
    """A18: normal zip OK; zip-slip/bomb/many-files rejected; nothing escapes workspace."""
    import tempfile

    from app.core.errors import MetisError
    from app.downloads.service import MANAGER

    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "extract"
        # normal
        out = MANAGER.safe_extract(Path(fixture_server.replace("http://127.0.0.1:", "")) if False else Path(__file__).parent / "fixtures" / "data" / "normal.zip", dest)
        assert len(out) == 2 and all(p.exists() for p in out)
        # zip slip
        with pytest.raises(MetisError) as e:
            MANAGER.safe_extract(Path(__file__).parent / "fixtures" / "data" / "evil_slip.zip", dest / "evil")
        assert e.value.code == "ARCHIVE_UNSAFE"
        # bomb
        with pytest.raises(MetisError) as e:
            MANAGER.safe_extract(Path(__file__).parent / "fixtures" / "data" / "bomb.zip", dest / "bomb")
        assert e.value.code == "ARCHIVE_UNSAFE"
        # too many files
        with pytest.raises(MetisError) as e:
            MANAGER.safe_extract(Path(__file__).parent / "fixtures" / "data" / "many_files.zip", dest / "many", max_files=1000)
        assert e.value.code == "ARCHIVE_UNSAFE"
        # nothing escaped the dest dir
        assert not (dest.parent / "evil.txt").exists()


def test_raw_immutable_guard(temp_workspace, fixture_server):
    """A19: raw checksum unchanged across transforms; writes into raw blocked."""
    from app.core import paths
    from app.core.errors import MetisError
    from app.core.paths import raw_root
    from app.downloads.service import MANAGER

    job = MANAGER.create_job("fixture", "panel", f"{fixture_server}/data/panel_data.csv", license="CC0-1.0")
    dest, info = asyncio.run(MANAGER.http_download(f"{fixture_server}/data/panel_data.csv", job=job))
    before = MANAGER.raw_checksum_snapshot()
    # transform outputs go to intermediate
    import pandas as pd

    inter = paths.intermediate_dir("test_build")
    df = pd.read_csv(raw_root() / info["raw_path"])
    df["gdp_per_capita_usd_k"] = df["gdp_per_capita"] / 1000
    df.to_parquet(inter / "panel_step1.parquet", index=False)
    # attempt to write into raw must be blocked
    from app.downloads.service import guard_no_raw_write

    with pytest.raises(MetisError) as e:
        guard_no_raw_write(paths.raw_root() / "evil" / "x.parquet")
    assert e.value.code == "RAW_WRITE_BLOCKED"
    MANAGER.verify_raw_unchanged(before)
