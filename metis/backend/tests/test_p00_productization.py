"""Phase 0 productization: P00-004 browser session create schema regression."""
from __future__ import annotations

import os
import tempfile


def _client():
    ws = tempfile.mkdtemp()
    os.environ["METIS_WORKSPACE_DIR"] = ws
    os.environ["METIS_DB_URL"] = "sqlite:///" + ws.replace("\\", "/") + "/metis.db"
    from app.core.config import reset_settings

    reset_settings()
    from app.db.session import reset_engine, init_db

    reset_engine()
    init_db()
    from fastapi.testclient import TestClient
    from app.api.main import app

    return TestClient(app)


def test_create_browser_session_without_session_id():
    """P00-004: the real frontend call {task_label} must return 200 and create a session."""
    c = _client()
    r = c.post("/api/browser/sessions", json={"task_label": "ui"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"] and data["state"]
    # listed with binding info
    sessions = c.get("/api/browser/sessions").json()
    assert any(s["session_id"] == data["session_id"] for s in sessions)
    assert "task_binding" in sessions[0]


def test_create_browser_session_with_task_binding():
    c = _client()
    r = c.post("/api/browser/sessions", json={"task_label": "acquire", "provider_id": "world_bank", "download_job_id": "dl_test"})
    assert r.status_code == 200
    sessions = c.get("/api/browser/sessions").json()
    s = next(s for s in sessions if s["session_id"] == r.json()["session_id"])
    assert s["task_binding"]["provider_id"] == "world_bank"
    assert s["task_binding"]["download_job_id"] == "dl_test"
