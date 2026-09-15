"""Shared pytest fixtures: temp workspace, DB, event bus, fixture HTTP server."""
from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture()
def temp_workspace(tmp_path, monkeypatch):
    """Isolated workspace + settings + fresh DB per test."""
    ws = tmp_path / "workspace"
    monkeypatch.setenv("METIS_WORKSPACE_DIR", str(ws))
    monkeypatch.setenv("METIS_DB_URL", f"sqlite:///{(ws / 'metis.db').as_posix()}")
    monkeypatch.setenv("METIS_LOG_DIR", str(ws / "logs"))
    monkeypatch.setenv("METIS_BROWSER_DOWNLOAD_DIR", str(ws / "downloads" / "browser"))
    monkeypatch.setenv("METIS_BROWSER_USER_DATA_DIR", str(ws / "browser-profile"))
    # Tests MUST never open visible windows on the user's desktop.
    monkeypatch.setenv("METIS_BROWSER_HEADLESS", "true")
    from app.core.config import reset_settings

    reset_settings()
    from app.core import logging as mlog

    mlog.clear_registered_secrets()
    from app.db.session import init_db, reset_engine

    reset_engine()
    init_db()
    yield ws
    reset_settings()
    reset_engine()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def fixture_server():
    """Local HTTP server serving tests/fixtures/pages and tests/fixtures/data."""
    port = _free_port()
    root = BACKEND_DIR / "tests" / "fixtures"
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base}/pages/index.html", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield base
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------- shared Playwright loop/fixtures (loop-bound connections) ----------------
_LOOP = None


def browser_run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module")
def loop():
    loop = asyncio.new_event_loop()
    global _LOOP
    _LOOP = loop
    yield loop
    loop.run_until_complete(_shutdown_sessions())
    loop.close()


async def _shutdown_sessions():
    from app.browser.runtime import MANAGER

    for s in list(MANAGER.sessions()):
        try:
            await MANAGER.get(s["session_id"]).close()
        except Exception:
            pass


@pytest.fixture()
def browser_session(temp_workspace, loop):
    import logging

    logging.getLogger("app.browser.runtime").setLevel(logging.WARNING)

    async def _new():
        from app.browser.runtime import MANAGER

        return await MANAGER.new_session("e2e-test")

    return loop.run_until_complete(_new())
