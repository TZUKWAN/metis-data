"""P24-001 Project/Task multi-task model + P25 Agent Chat deterministic core."""
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


def test_project_crud_and_task_link():
    c = _client()
    r = c.post("/api/projects", json={"title": "Youth unemployment panel"})
    assert r.status_code == 200, r.text
    pid = r.json()["project"]["project_id"]
    # list shows the project with task_count
    lst = c.get("/api/projects").json()
    assert any(p["project_id"] == pid and p["task_count"] == 0 for p in lst)
    # detail: project + empty tasks
    d = c.get(f"/api/projects/{pid}").json()
    assert d["project"]["title"] == "Youth unemployment panel"
    assert d["tasks"] == []
    # link a REAL search run as a task
    from app.db.repository import REPO

    REPO.save_search_run("run_p24", "req_p24", "COMPLETED")
    t = c.post(f"/api/projects/{pid}/tasks", json={"kind": "search_run", "ref_id": "run_p24"})
    assert t.status_code == 200, t.text
    assert t.json()["kind"] == "search_run" and t.json()["status"] == "OPEN"
    tid = t.json()["task_id"]
    d = c.get(f"/api/projects/{pid}").json()
    assert len(d["tasks"]) == 1 and d["tasks"][0]["ref_id"] == "run_p24"
    assert any(p["project_id"] == pid and p["task_count"] == 1 for p in c.get("/api/projects").json())
    # status patch propagates
    p = c.patch(f"/api/tasks/{tid}", json={"status": "DONE"})
    assert p.status_code == 200 and p.json()["status"] == "DONE"
    assert c.get(f"/api/projects/{pid}").json()["tasks"][0]["status"] == "DONE"
    # 404 paths
    assert c.get("/api/projects/missing").status_code == 404
    assert c.post("/api/projects/missing/tasks", json={"kind": "search_run", "ref_id": "x"}).status_code == 404
    assert c.patch("/api/tasks/missing", json={"status": "DONE"}).status_code == 404


def test_agent_chat_progress_uses_real_ids():
    c = _client()
    from app.db.repository import REPO

    REPO.save_search_run("run_p24", "req_p24", "COMPLETED")
    REPO.upsert_provider_task("pt_p24_1", "run_p24", "world_bank", "done", result_count=12)
    REPO.upsert_provider_task("pt_p24_2", "run_p24", "who", "running")
    pid = c.post("/api/projects", json={"title": "P"}).json()["project"]["project_id"]
    c.post(f"/api/projects/{pid}/tasks", json={"kind": "search_run", "ref_id": "run_p24"})
    resp = c.post("/api/agent/chat", json={"question": "现在进行到哪了？", "project_id": pid})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_confirmation"] is False
    assert "run_p24" in data["evidence"]
    assert "run_p24" in data["answer"] and "COMPLETED" in data["answer"]
    # empty DB fallback also answers deterministically
    assert c.post("/api/agent/chat", json={"question": "进度如何"}).status_code == 200


def test_agent_chat_explains_recommendation():
    c = _client()
    from app.db.repository import REPO
    from app.domain.schemas import DatasetCandidate

    REPO.save_search_run("run_p24", "req_p24", "COMPLETED")
    REPO.save_candidate(
        "run_p24",
        DatasetCandidate(provider_id="world_bank", title="Youth unemployment panel", reasons=["has DOI"], recommendation={"topic": 0.9, "license": 0.8}),
    )
    resp = c.post("/api/agent/chat", json={"question": "为什么推荐 Youth unemployment？"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "has DOI" in data["answer"]
    assert "has DOI" in data["evidence"]
    assert "run_p24" in data["evidence"]
    # unknown title → lists the available candidate titles instead
    miss = c.post("/api/agent/chat", json={"question": "为什么推荐 Totally Unrelated Thing"}).json()
    assert "Youth unemployment panel" in miss["answer"]


def test_agent_chat_build_explain():
    c = _client()
    from app.db.repository import REPO
    from app.domain.schemas import BuildConfig

    REPO.save_build(BuildConfig(title="panel", keys=["country", "year"], missing_policy="none", aggregations=[{"field": "gdp", "method": "mean"}], status="COMPLETE"))
    bid = REPO.list_builds()[0]["build_id"]
    REPO.add_build_operation(operation_id="op_p24_1", build_id=bid, seq=1, operation_type="harmonize_keys", parameters={}, input_artifacts=[], output_artifacts=[], warnings=[])
    resp = c.post("/api/agent/chat", json={"question": "这些数据怎么合成的？缺失怎么处理？"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["needs_confirmation"] is False
    assert bid in data["evidence"]
    assert "missing_policy=none" in data["answer"]
    assert "harmonize_keys" in data["answer"]


def test_requires_confirmation_gate():
    from app.api.main import requires_confirmation

    assert requires_confirmation({"kind": "register_account"}) is True
    assert requires_confirmation({"kind": "delete_account"}) is True
    assert requires_confirmation({"kind": "allow_mm_join"}) is True
    assert requires_confirmation({"kind": "missing_policy_not_none"}) is True
    assert requires_confirmation({"kind": "search"}) is False
    assert requires_confirmation({}) is False
    # chat carrying a confirmable action: gated, nothing executed
    c = _client()
    r = c.post("/api/agent/chat", json={"question": "帮我注册 world_bank 账号", "action": {"kind": "register_account", "provider_id": "world_bank"}})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["needs_confirmation"] is True
    assert data["confirm_action"]["kind"] == "register_account"
    assert data["confirm_action"]["provider_id"] == "world_bank"
    # non-confirmable action goes through the normal deterministic path
    ok = c.post("/api/agent/chat", json={"question": "现在进行到哪了", "action": {"kind": "search"}}).json()
    assert ok["needs_confirmation"] is False
