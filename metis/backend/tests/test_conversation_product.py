"""Deterministic conversational product E2E (§24/§28): the full user chain in CI.

Fixture LLM (rules fallback — no external calls), fixture search (saves real
candidates), fixture access (AUTHORIZED or LOGIN_REQUIRED), real download manager,
real acquisition over a local HTTP server, real BuildPlanner/BuildExecutor.
Covers: async accept, failure convergence, intermediate states, result links,
preview (FOUND/READY), public download, auth intervention + probe + auto-resume,
build existing results, one-shot discover→acquire→build, refine context,
scoped explain, conversation isolation, refresh restore, cancel.
"""
from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

FIXTURE_DATA_DIR = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """Deterministic product E2E never calls the real LLM.

    Empty-string sentinel instead of delenv: metis/.env is loaded via setdefault at
    import time, so deleted vars would be re-added — an empty value sticks and both
    LLMClient.from_env and _llm_configured treat it as "not configured".
    """
    for var in ("METIS_LLM_BASE_URL", "METIS_LLM_API_KEY", "METIS_LLM_MODEL"):
        monkeypatch.setenv(var, "")


@pytest.fixture(scope="module")
def data_server():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    yield from _start_server(port)


def _start_server(port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(FIXTURE_DATA_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
    provider_id = "stub_provider"

    def __init__(self, csv_url: str) -> None:
        self.csv_url = csv_url

    async def build_acquisition_descriptor(self, dataset_ref, access_context=None):
        from app.providers.download_helper import AcquisitionDescriptor

        return AcquisitionDescriptor(url=self.csv_url, filename="panel.csv", expected_type="csv")


def _candidate(cid: str, title: str, provider: str, url: str, score: float) -> dict:
    return {
        "candidate_id": cid, "title": title, "provider_id": provider,
        "publisher": provider, "description": f"{title} 测试数据集",
        "geography": ["全球"], "time_coverage": {"start": 2015, "end": 2024},
        "license": "CC-BY", "score": score, "reasons": ["主题匹配", "官方来源"],
        "recommendation": {"authority": 0.8}, "limitations": [], "unknowns": [],
        "is_primary": True,
        "sources": [{"source_ref": f"ref_{cid}", "source_url": url, "file_format": "CSV"}],
    }


@pytest.fixture()
def fake_search(temp_workspace, monkeypatch, data_server):
    """Search stub: persists real candidate rows into REPO for the given run_id."""
    from app.search.orchestrator import ORCHESTRATOR as SEARCH_ORCH

    def _install(cands=None, delay: float = 0.0):
        cands = cands if cands is not None else [
            _candidate("cand_a", "青年失业率数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9),
            _candidate("cand_b", "人均GDP数据集", "oecd", f"{data_server}/youth_unemployment.csv", 0.7),
        ]

        async def fake_run_search(requirement, provider_ids=None, query_plan=None, run_id=None, bundle=None):
            from app.db.repository import REPO

            await asyncio.sleep(delay)
            for c in cands:
                REPO.save_candidate(run_id, c)
            return run_id

        monkeypatch.setattr(SEARCH_ORCH, "run_search", fake_run_search)
        return cands

    return _install



@pytest.fixture()
def fast_planning(temp_workspace, monkeypatch, request):
    """Fixture planning (§28): instant deterministic PlanningBundle — no network probes.

    The real deterministic planning chain health-probes provider endpoints (~70s);
    product E2E must not depend on external network latency.
    """
    import app.agent.orchestrator as orch_mod
    from app.agent.schemas import DataRequirementPlan, PlanningBundle, ProviderQueryPlan, SourcePlan

    def _install(providers=None):
        providers = providers or ["stub_provider", "oecd"]

        async def fast_bundle(text, planning_id=None):
            return PlanningBundle(
                requirement=DataRequirementPlan(research_goal=text, unit_of_analysis="country",
                                                time_range={"start": 2015, "end": 2024}),
                source_plan=SourcePlan(provider_priorities=list(providers)),
                query_plans=[ProviderQueryPlan(provider_id=p, queries=[text[:40]]) for p in providers],
                planning_source="fallback",
            )

        monkeypatch.setattr(orch_mod, "build_planning_bundle", fast_bundle)
    return _install


@pytest.fixture()
def public_access(temp_workspace, monkeypatch):
    """resolve_access → AUTHORIZED (public source)."""
    def _install():
        from app.access.machine import AccessState, create_access_job, transition

        async def fake_resolve(provider_id, dataset_ref, *, candidate_id="", download_job_id=""):
            job = create_access_job(provider_id, candidate_id=candidate_id, download_job_id=download_job_id)
            transition(job, AccessState.INSPECTING, "fixture: inspecting")
            transition(job, AccessState.PUBLIC, "fixture: public")
            transition(job, AccessState.AUTHORIZED, "fixture: authorized")
            return job

        import app.access.executor as exec_mod
        monkeypatch.setattr(exec_mod, "resolve_access", fake_resolve)
    return _install


@pytest.fixture()
def login_required_access(temp_workspace, monkeypatch, data_server):
    """resolve_access → WAITING_USER until the test flips the flag (simulates login)."""
    def _install():
        from app.access.machine import AccessState, create_access_job, transition

        state = {"authorized": False}

        async def fake_resolve(provider_id, dataset_ref, *, candidate_id="", download_job_id=""):
            job = create_access_job(provider_id, candidate_id=candidate_id, download_job_id=download_job_id)
            transition(job, AccessState.INSPECTING, "fixture: inspecting")
            if state["authorized"]:
                transition(job, AccessState.PUBLIC, "fixture: public")
                transition(job, AccessState.AUTHORIZED, "fixture: user logged in")
            else:
                transition(job, AccessState.WAITING_USER, "fixture: login required")
                job.browser_session_id = "sess_fixture"
            return job

        import app.access.executor as exec_mod
        monkeypatch.setattr(exec_mod, "resolve_access", fake_resolve)
        return state
    return _install


@pytest.fixture()
def real_acquisition(temp_workspace, monkeypatch):
    """Real AcquisitionService with a stub adapter (v2 descriptor → real stream → raw commit)."""
    def _install(csv_url: str):
        import app.acquisition.service as acq_mod

        monkeypatch.setattr(acq_mod, "get_adapter", lambda pid: StubAdapter(csv_url))
    return _install


@pytest.fixture()
def client(temp_workspace):
    from fastapi.testclient import TestClient

    from app.api.main import app

    with TestClient(app) as c:
        yield c


def _wait_task(client, cid, task_id, timeout=25.0, state_in=None):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = client.get(f"/api/conversations/{cid}/task/{task_id}")
        last = r.json()
        if last["state"] in (state_in or {"COMPLETE", "FAILED", "CANCELLED"}):
            return last
        time.sleep(0.2)
    return last


def _send(client, cid, text):
    r = client.post(f"/api/conversations/{cid}/messages", json={"text": text})
    assert r.status_code == 202, r.text
    return r.json()


# ---------------- §24 tests ----------------

def test_conversation_async_accept(client, fake_search, fast_planning, public_access, real_acquisition):
    fast_planning()
    """POST /messages returns 202 immediately (P95 < 500ms) with a task id (§12)."""
    fake_search(delay=1.5)
    public_access()
    real_acquisition(f"{_data_server_base(client)}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    t0 = time.time()
    r = client.post(f"/api/conversations/{cid}/messages", json={"text": "找青年失业率数据"})
    ms = (time.time() - t0) * 1000
    assert r.status_code == 202
    assert ms < 500, f"POST took {ms:.0f}ms — async contract broken"
    body = r.json()
    assert body["task_id"] and body["state"] == "UNDERSTANDING"


def _data_server_base(client):  # helper keeps fixtures readable
    return client  # unused; data_server URL injected by fixtures


def test_conversation_failure_persists_failed(client, monkeypatch):
    """P0-11: pipeline exception → task FAILED + user-friendly assistant message, never stuck."""
    import app.agent.orchestrator as orch_mod

    async def boom(text, planning_id=None):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(orch_mod, "build_planning_bundle", boom)
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找数据")
    t = _wait_task(client, cid, body["task_id"])
    assert t["state"] == "FAILED"
    assert t["error_code"]
    msgs = client.get(f"/api/conversations/{cid}/messages").json()
    last = [m for m in msgs if m["role"] == "assistant"][-1]
    assert "LLM" not in last["content"] or "暂时" in last["content"] or "问题" in last["content"]
    assert "Traceback" not in last["content"] and "RuntimeError" not in last["content"]


def test_task_intermediate_states(client, fake_search, fast_planning, public_access):
    fast_planning()
    """P0-12: SEARCHING is persisted mid-flight (not just UNDERSTANDING→COMPLETE)."""
    fake_search(delay=1.2)
    public_access()
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找GDP数据")
    seen = set()
    deadline = time.time() + 20
    while time.time() < deadline:
        t = client.get(f"/api/conversations/{cid}/task/{body['task_id']}").json()
        seen.add(t["state"])
        if t["state"] in ("COMPLETE", "FAILED"):
            break
        time.sleep(0.1)
    assert t["state"] == "COMPLETE"
    assert "SEARCHING" in seen, f"intermediate states not persisted: {seen}"


def test_conversation_result_link(client, fake_search, fast_planning, public_access):
    fast_planning()
    """P0-10: candidates become result links with stable result_ids."""
    fake_search()
    public_access()
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找青年失业率数据")
    _wait_task(client, cid, body["task_id"])
    results = client.get(f"/api/conversations/{cid}/results").json()
    assert len(results) == 2
    for v in results:
        assert v["result_id"].startswith("res_")
        assert v["state"] in ("已找到", "可用")
        assert v["title"]


def test_result_preview_found(client, fake_search, fast_planning, public_access):
    fast_planning()
    """P0-03: FOUND result preview returns honest metadata (no fabricated numbers)."""
    fake_search()
    public_access()
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找数据")
    _wait_task(client, cid, body["task_id"])
    results = client.get(f"/api/conversations/{cid}/results").json()
    p = client.get(f"/api/results/{results[0]['result_id']}/preview").json()
    assert p["preview_kind"] == "metadata"
    assert p["title"]
    assert p["source_url"].startswith("http")


def test_result_preview_ready(client, fake_search, fast_planning, public_access, real_acquisition, data_server):
    fast_planning()
    """P0-03: READY result preview returns REAL parsed data rows."""
    fake_search(cands=[_candidate("cand_a", "青年失业率数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9)])
    public_access()
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "下载青年失业率数据")
    _wait_task(client, cid, body["task_id"])
    results = client.get(f"/api/conversations/{cid}/results").json()
    ready = [v for v in results if v["state"] == "可用"]
    assert ready, f"no READY result: {[v['state'] for v in results]}"
    p = client.get(f"/api/results/{ready[0]['result_id']}/preview").json()
    assert p["preview_kind"] == "data"
    assert p["columns"] and p["total_rows"] > 0
    assert p["rows"]


def test_result_download_public(client, fake_search, fast_planning, public_access, real_acquisition, data_server, temp_workspace):
    fast_planning()
    """UAT-06: FOUND → ACQUIRING → READY, artifact committed, same result_id (P0-04/05)."""
    fake_search(cands=[_candidate("cand_a", "青年失业率数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9)])
    public_access()
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找数据")
    _wait_task(client, cid, body["task_id"])
    results = client.get(f"/api/conversations/{cid}/results").json()
    found = results[0]
    assert found["state"] == "已找到"

    # user clicks 下载 on a FOUND result → full chain runs
    client.post(f"/api/results/{found['result_id']}/download")
    deadline = time.time() + 20
    final = None
    while time.time() < deadline:
        final = client.get(f"/api/results/{found['result_id']}").json()
        if final["state"] in ("可用", "获取失败"):
            break
        time.sleep(0.2)
    assert final["state"] == "可用"
    assert final["result_id"] == found["result_id"], "result_id changed across acquisition"
    assert final["preview_available"]
    raw_root = temp_workspace / "raw"
    assert any(raw_root.rglob("*.csv")), "artifact not committed to raw/"


def test_auth_intervention(client, fake_search, fast_planning, login_required_access, real_acquisition, data_server):
    """P0-13: login-needed access creates an intervention + result WAITING_USER."""
    fast_planning()
    login_required_access()
    fake_search(cands=[_candidate("cand_auth", "受限数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9)])
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "下载这个数据")
    _wait_task(client, cid, body["task_id"])
    itvs = client.get(f"/api/conversations/{cid}/interventions?state=WAITING_USER").json()
    assert len(itvs) == 1
    itv = itvs[0]
    assert itv["kind"] == "LOGIN_REQUIRED"
    assert itv["result_id"].startswith("res_")
    assert itv["browser_session_id"] == "sess_fixture"
    link = client.get(f"/api/results/{itv['result_id']}").json()
    assert link["state"] == "需要登录"


def test_auth_probe_failure_keeps_waiting(client, fake_search, fast_planning, login_required_access, real_acquisition, data_server):
    fast_planning()
    """P0-14/UAT-08: 我已完成 without a real login → probe fails, intervention stays WAITING_USER."""
    login_required_access()
    fake_search(cands=[_candidate("cand_auth", "受限数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9)])
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "下载数据")
    _wait_task(client, cid, body["task_id"])
    itv = client.get(f"/api/conversations/{cid}/interventions?state=WAITING_USER").json()[0]
    r = client.post(f"/api/interventions/{itv['intervention_id']}/resume").json()
    assert r["probed"] is True and r["authorized"] is False
    assert "未检测到登录成功" in r["message"]
    still = client.get(f"/api/interventions/{itv['intervention_id']}").json()
    assert still["state"] == "WAITING_USER"


def test_auth_resume_result_ready(client, fake_search, fast_planning, login_required_access, real_acquisition, data_server):
    fast_planning()
    """P0-15/UAT-09: after real login the ORIGINAL download resumes automatically → READY, no second click."""
    state = login_required_access()
    fake_search(cands=[_candidate("cand_auth", "受限数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9)])
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "下载数据")
    _wait_task(client, cid, body["task_id"])
    itv = client.get(f"/api/conversations/{cid}/interventions?state=WAITING_USER").json()[0]

    state["authorized"] = True  # user logs in via the browser window
    r = client.post(f"/api/interventions/{itv['intervention_id']}/resume").json()
    assert r["state"] == "RESOLVED" and r["authorized"] is True

    # auto-resume: the pipeline acquires without any further user action
    deadline = time.time() + 20
    link = None
    while time.time() < deadline:
        link = client.get(f"/api/results/{itv['result_id']}").json()
        if link["state"] in ("可用", "获取失败"):
            break
        time.sleep(0.2)
    assert link["state"] == "可用"
    assert link["result_id"] == itv["result_id"]


def test_build_existing_results(client, fake_search, fast_planning, public_access, real_acquisition, data_server):
    fast_planning()
    """UAT-11: two READY results + '把这两个合并' → BUILDING → FINAL (P0-06)."""
    fake_search(cands=[
        _candidate("cand_a", "青年失业率数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9),
        _candidate("cand_b", "人均GDP数据集", "stub_provider", f"{data_server}/youth_unemployment.csv", 0.85),
    ])
    public_access()
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "下载这两份数据")
    t = _wait_task(client, cid, body["task_id"])
    assert t["state"] == "COMPLETE"
    ready = [v for v in client.get(f"/api/conversations/{cid}/results").json() if v["state"] == "可用"]
    assert len(ready) == 2, f"need 2 READY, got {[v['state'] for v in client.get(f'/api/conversations/{cid}/results').json()]}"

    body2 = _send(client, cid, "把这两个合并")
    t2 = _wait_task(client, cid, body2["task_id"])
    assert t2["state"] == "COMPLETE"
    results = client.get(f"/api/conversations/{cid}/results").json()
    finals = [v for v in results if v["state"] == "最终数据集"]
    assert finals, f"no FINAL result after merge: {[v['state'] for v in results]}"
    pv = client.get(f"/api/results/{finals[0]['result_id']}/preview").json()
    assert pv["preview_kind"] == "final" and pv["total_rows"] > 0


def test_one_shot_discover_acquire_build(client, fake_search, fast_planning, public_access, real_acquisition, data_server):
    fast_planning()
    """UAT-12/§19: one sentence '帮我构建面板' with no data → full Discover→Acquire→Build→FINAL."""
    fake_search(cands=[
        _candidate("cand_a", "青年失业率数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9),
        _candidate("cand_b", "人均GDP数据集", "stub_provider", f"{data_server}/youth_unemployment.csv", 0.85),
    ])
    public_access()
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "帮我构建2015-2024年国家层面的青年失业率和人均GDP面板数据")
    t = _wait_task(client, cid, body["task_id"], timeout=40)
    assert t["state"] == "COMPLETE", t
    task = client.get(f"/api/conversations/{cid}/task/{body['task_id']}").json()
    assert task["goal"] in ("discover_acquire_build", "operate_on_existing_results")
    results = client.get(f"/api/conversations/{cid}/results").json()
    assert any(v["state"] == "最终数据集" for v in results), [v["state"] for v in results]


def test_refine_context(client, fake_search, fast_planning, public_access):
    fast_planning()
    """P0-08/UAT-10: refine inherits the previous requirement, merges source constraints."""
    fake_search()
    public_access()
    cid = client.post("/api/conversations").json()["conversation_id"]
    b1 = _send(client, cid, "找全球青年失业率和人均GDP数据")
    _wait_task(client, cid, b1["task_id"])
    b2 = _send(client, cid, "不要世界银行，只用OECD和ILO")
    t2 = _wait_task(client, cid, b2["task_id"])
    assert t2["state"] == "COMPLETE"
    assert t2["goal"] == "refine_existing_task"
    # merged requirement text carries the original topic forward (context preserved)
    from app.ui.conversation_store import STORE
    tj = STORE.get_task(b2["task_id"])
    assert "失业率" in tj["data"]["requirement_text"], "refine dropped prior context"
    assert "只用OECD" in tj["data"]["requirement_text"] or "OECD" in tj["data"]["requirement_text"]


def test_explain_scoped(client, fake_search, fast_planning, public_access):
    fast_planning()
    """P0-09/UAT: explain reads THIS conversation's results, not the global latest run."""
    fake_search()
    public_access()
    cid_a = client.post("/api/conversations").json()["conversation_id"]
    cid_b = client.post("/api/conversations").json()["conversation_id"]
    ba = _send(client, cid_a, "找青年失业率数据")
    _wait_task(client, cid_a, ba["task_id"])

    be = _send(client, cid_b, "为什么推荐这个结果")
    te = _wait_task(client, cid_b, be["task_id"])
    assert te["state"] == "COMPLETE"
    msgs = client.get(f"/api/conversations/{cid_b}/messages").json()
    reply = [m for m in msgs if m["role"] == "assistant"][-1]["content"]
    assert "还没有结果" in reply or "先告诉我" in reply, "explain leaked another conversation's results"


def test_conversation_isolation(client, fake_search, fast_planning, public_access):
    fast_planning()
    """UAT-15: two conversations never share results/tasks/interventions."""
    fake_search()
    public_access()
    cid_a = client.post("/api/conversations").json()["conversation_id"]
    cid_b = client.post("/api/conversations").json()["conversation_id"]
    ba = _send(client, cid_a, "找数据A")
    _wait_task(client, cid_a, ba["task_id"])
    res_a = client.get(f"/api/conversations/{cid_a}/results").json()
    assert res_a
    res_b = client.get(f"/api/conversations/{cid_b}/results").json()
    assert res_b == [], "conversation B saw conversation A's results"
    tasks_b = client.get(f"/api/conversations/{cid_b}/tasks").json()
    assert all(t["task_id"] != ba["task_id"] for t in tasks_b)


def test_refresh_restore(client, fake_search, fast_planning, public_access):
    fast_planning()
    """§20/UAT-14: after completion, messages + task + results all survive (restore reads the same APIs)."""
    fake_search()
    public_access()
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找数据")
    _wait_task(client, cid, body["task_id"])
    # a "refreshed" client re-reads everything from persistence
    msgs = client.get(f"/api/conversations/{cid}/messages").json()
    assert len([m for m in msgs if m["role"] == "user"]) == 1
    assert len([m for m in msgs if m["role"] == "assistant"]) == 1
    tasks = client.get(f"/api/conversations/{cid}/tasks").json()
    assert tasks and tasks[0]["state"] == "COMPLETE"
    results = client.get(f"/api/conversations/{cid}/results").json()
    assert len(results) == 2


def test_cancel_task(client, fake_search, fast_planning, public_access):
    fast_planning()
    """UAT-17: cancel during search → task CANCELLED, pipeline stops."""
    fake_search(delay=6.0)
    public_access()
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "找数据")
    time.sleep(1.0)
    r = client.post(f"/api/conversations/{cid}/task/{body['task_id']}/cancel")
    assert r.status_code == 200
    t = _wait_task(client, cid, body["task_id"], timeout=15)
    assert t["state"] == "CANCELLED"


def test_export_formats(client, fake_search, fast_planning, public_access, real_acquisition, data_server):
    fast_planning()
    """UAT-13: real CSV export of a READY result — file exists, non-empty, readable."""
    fake_search(cands=[_candidate("cand_a", "青年失业率数据集", "stub_provider", f"{data_server}/panel_data.csv", 0.9)])
    public_access()
    real_acquisition(f"{data_server}/panel_data.csv")
    cid = client.post("/api/conversations").json()["conversation_id"]
    body = _send(client, cid, "下载数据")
    _wait_task(client, cid, body["task_id"])
    ready = [v for v in client.get(f"/api/conversations/{cid}/results").json() if v["state"] == "可用"]
    assert ready
    r = client.get(f"/api/results/{ready[0]['result_id']}/export/csv")
    assert r.status_code == 200
    assert len(r.content) > 100
    assert b"," in r.content
