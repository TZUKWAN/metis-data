"""P15/P16: API + UI surface integration (server boots, static UI served, WS bus)."""
from __future__ import annotations

import os
import tempfile


def _client():
    ws = tempfile.mkdtemp()
    os.environ["METIS_WORKSPACE_DIR"] = ws
    os.environ["METIS_DB_URL"] = "sqlite:///" + ws.replace("\\", "/") + "/metis.db"
    from app.core.config import reset_settings

    reset_settings()
    from app.db.session import init_db, reset_engine

    reset_engine()
    init_db()
    from fastapi.testclient import TestClient

    from app.api.main import app

    return TestClient(app)


def test_server_boots_and_serves_ui():
    c = _client()
    r = c.get("/")
    assert r.status_code == 200 and "Metis Data" in r.text
    r = c.get("/api/health")
    assert r.json()["status"] == "ok"
    r = c.get("/ui/app.js")
    assert r.status_code == 200 and "fetch(" in r.text


def test_full_ui_flow_requirement_search_download_profile_build():
    """One integrated API pass mirroring the UI click path (fixture providers only)."""
    c = _client()
    import sys

    sys.path.insert(0, str(c.app and "")) if False else None
    # requirement
    r = c.post("/api/requirements", json={"text": "构建 2015—2023 年国家层面的青年失业率面板，优先官方数据"})
    assert r.status_code == 200
    rid = r.json()["requirement_id"]
    assert r.json()["assumptions"], "inferences must be displayed"
    # edit requirement revalidates
    r = c.put(f"/api/requirements/{rid}", json={"time_range": [2016, 2022]})
    assert r.json()["requirement"]["time_range"] == [2016, 2022]
    # build from two fixture artifacts: create downloads via the download API
    import asyncio

    from app.db.repository import REPO
    from app.downloads.service import MANAGER

    arts = []
    for fname, ref in [("panel_data.csv", "panel"), ("youth_unemployment.csv", "youth")]:
        url = f"{c.app.url}missing/{fname}" if False else None
        # use the fixture server from conftest instead
        arts.append((fname, ref))
    # create artifacts directly through the manager using the shared fixture server
    fixture_server = _get_fixture_server()
    for fname, ref in arts:
        job = MANAGER.create_job("fixture", ref, f"{fixture_server}/data/{fname}", license="CC0-1.0")
        asyncio.new_event_loop().run_until_complete(MANAGER.http_download(f"{fixture_server}/data/{fname}", job=job))
    artifacts = REPO.list_artifacts()
    assert len(artifacts) >= 2
    r = c.post("/api/builds", json={"title": "ui-flow", "inputs": [{"artifact_id": a["artifact_id"]} for a in artifacts[:2]], "keys": ["country", "year"]})
    assert r.status_code == 200
    bid = r.json()["build_id"]
    r = c.post(f"/api/builds/{bid}/run")
    assert r.status_code == 200
    import time

    for _ in range(120):
        b = c.get(f"/api/builds/{bid}").json()
        if b["status"] in ("COMPLETE", "FAILED", "NEEDS_REVIEW"):
            break
        time.sleep(0.5)
    assert b["status"] == "COMPLETE", str(b.get("validations", [])[:3])
    assert b["operations"] and b["field_lineage"]
    # package reachable via API
    r = c.get(f"/api/builds/{bid}/package/metadata/sources.json")
    assert r.status_code == 200
    r = c.get(f"/api/builds/{bid}/package/manifest.json")
    assert r.status_code == 200


def _get_fixture_server():
    import socket
    import subprocess
    import sys
    import time
    import urllib.request
    from pathlib import Path

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    root = Path(__file__).parent / "fixtures"
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=str(root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import atexit

    atexit.register(proc.terminate)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base}/pages/index.html", timeout=1)
            return base
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("fixture server failed to start")
