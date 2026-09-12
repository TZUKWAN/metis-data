"""Phase B acceptance: LLM Planning as the search main chain.

Uses the same STUB OpenAI-compatible HTTP server pattern as test_p01_agent.py:
one stub serves all planning stages (a router function discriminates the stage
from the prompt's user message). Provider network is stubbed by monkeypatching
app.search.orchestrator.get_adapter (same approach as test_p10_search).
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

TEXT = "构建2012—2024年中国地级市科技创新、土地财政依赖、环境规制和产业升级面板数据"

REQUIREMENT_PLAN = {
    "research_goal": "构建2012—2024年中国地级市科技创新、土地财政依赖、环境规制和产业升级面板数据",
    "unit_of_analysis": "city",
    "geography": ["CN"],
    "time_range": {"start": 2012, "end": 2024},
    "frequency": "annual",
    "variables": [
        {"concept": "科技创新", "role": "outcome", "description": "城市创新能力"},
        {"concept": "土地财政依赖", "role": "exposure", "description": "土地出让收入依赖"},
        {"concept": "环境规制", "role": "moderator", "description": "环境监管强度"},
        {"concept": "产业升级", "role": "outcome", "description": "产业结构高级化"},
    ],
    "constraints": {},
    "preferred_sources": [],
    "deliverables": [],
    "assumptions": ["地级市层面数据以城市统计年鉴为主要来源"],
    "questions": [],
}

MEASUREMENT_PLANS = {
    "plans": [
        {"concept": "科技创新", "role": "outcome", "preferred_measure": "专利授权量（每万人）", "unit": "count per 10k", "frequency": "annual", "aggregation_semantics": "sum", "confidence": 0.7},
        {"concept": "土地财政依赖", "role": "exposure", "preferred_measure": "土地出让收入/一般公共预算收入", "unit": "ratio", "frequency": "annual", "aggregation_semantics": "last", "confidence": 0.7},
        {"concept": "环境规制", "role": "moderator", "preferred_measure": "节能环保支出占一般公共预算支出比重", "unit": "percent", "frequency": "annual", "aggregation_semantics": "mean", "confidence": 0.7},
        {"concept": "产业升级", "role": "outcome", "preferred_measure": "第三产业增加值/GDP", "unit": "ratio", "frequency": "annual", "aggregation_semantics": "last", "confidence": 0.7},
    ]
}

SOURCE_PLAN = {
    "provider_priorities": ["opendata_swiss", "data_gov_uk"],
    "provider_queries": {
        "opendata_swiss": ["china city innovation panel", "科技创新 城市 面板"],
        "data_gov_uk": ["local enterprise indicators panel"],
    },
    "search_languages": ["zh", "en"],
    "fallbacks": [],
    "rationale": ["official statistics portals first for panel data"],
}


def _stub_router(user_msg: str):
    """Discriminate the planning stage from the prompt's user message."""
    if user_msg.startswith("Requirement:"):
        return SOURCE_PLAN
    if user_msg.lstrip().startswith("- "):
        return MEASUREMENT_PLANS
    return REQUIREMENT_PLAN


# ---------- stub OpenAI-compatible server (copied from test_p01_agent.py) ----------
class _Handler(BaseHTTPRequestHandler):
    behavior: dict = {"fail_times": 0, "status": 200, "content": _stub_router}

    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.behavior["fail_times"] > 0:
            self.behavior["fail_times"] -= 1
            self.send_response(self.behavior["status"] if self.behavior["status"] != 200 else 500)
            self.end_headers()
            self.wfile.write(b'{"error":"stub"}')
            return
        content = self.behavior["content"]
        if callable(content):
            user_msg = body["messages"][-1]["content"]
            content = content(user_msg)
        resp = json.dumps({"choices": [{"message": {"role": "assistant", "content": json.dumps(content if not isinstance(content, dict) else content)}}]})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(resp.encode())


@pytest.fixture(scope="module")
def stub_llm():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}", _Handler.behavior
    srv.shutdown()


def _with_llm_env(monkeypatch, base_url, model="stub-model", key="stub-key-METIS-TEST-SECRET"):
    monkeypatch.setenv("METIS_LLM_BASE_URL", base_url)
    monkeypatch.setenv("METIS_LLM_API_KEY", key)
    monkeypatch.setenv("METIS_LLM_MODEL", model)
    monkeypatch.setenv("METIS_LLM_TIMEOUT", "10")
    monkeypatch.setenv("METIS_LLM_MAX_RETRIES", "1")


def _without_llm_env(monkeypatch):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("METIS_LLM_MODEL", raising=False)


class _FakeAdapter:
    """Stand-in provider adapter so tests never hit the real network (L5)."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id

    async def search_datasets(self, q, filters=None, limit=10):
        from app.providers.adapters.common import mk_candidate

        return [
            mk_candidate(
                provider_id=self.provider_id,
                title=f"Stub dataset {self.provider_id} — {q[:16]}",
                source_url=f"https://example.org/{self.provider_id}/{abs(hash(q)) % 9999}",
                source_ref=q[:24],
            )
        ]


def _patch_search_adapters(monkeypatch):
    import app.search.orchestrator as orch_mod

    fakes = {"opendata_swiss": _FakeAdapter("opendata_swiss"), "data_gov_uk": _FakeAdapter("data_gov_uk")}
    monkeypatch.setattr(orch_mod, "get_adapter", lambda pid: fakes[pid])


# ---------- Phase B: LLM planning chain drives the search main path ----------
def test_planning_chain_llm_drives_search_run(temp_workspace, stub_llm, monkeypatch):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    behavior.update({"fail_times": 0, "status": 200, "content": _stub_router})
    from fastapi.testclient import TestClient

    from app.api.main import app

    with TestClient(app) as c:
        # 1) planning chain over an out-of-lexicon requirement
        r = c.post("/api/agent/planning", json={"text": TEXT})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["planning_source"] == "llm"
        assert data["bundle"]["requirement"]["unit_of_analysis"] == "city"
        assert len(data["bundle"]["requirement"]["variables"]) >= 4
        assert data["bundle"]["measurements"], "measurement plans missing"
        assert data["bundle"]["source_plan"]["provider_priorities"]
        assert data["bundle"]["query_plans"]
        planning_id = data["planning_id"]
        assert planning_id

        # 2) bundle is retrievable by id
        r2 = c.get(f"/api/agent/planning/{planning_id}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["planning_id"] == planning_id
        assert r2.json()["requirement_text"] == TEXT  # original text preserved

        _patch_search_adapters(monkeypatch)

        # 3) search run driven purely by planning_id (no requirement_id, no provider_ids)
        r3 = c.post("/api/search/runs", json={"planning_id": planning_id})
        assert r3.status_code == 200, r3.text
        assert r3.json()["planning_source"] == "llm"
        assert r3.json()["providers"] == ["opendata_swiss", "data_gov_uk"]  # bundle priorities
        run_id = r3.json()["run_id"]

        from app.db.repository import REPO
        from app.domain.enums import SearchRunStatus

        run = REPO.get_search_run(run_id)
        assert run["status"] == SearchRunStatus.COMPLETED
        planning_bundle = run["query_plan"]["planning_bundle"]
        assert planning_bundle["planning_source"] == "llm"
        assert planning_bundle["query_plans"], "bundle queries missing from persisted run"

        # 4) a DataRequirement was derived from the bundle and persisted (raw text verbatim)
        reqs = REPO.list_requirements()
        assert any(rq["raw_request"] == TEXT for rq in reqs)
        derived = next(rq for rq in reqs if rq["raw_request"] == TEXT)
        assert derived["unit_of_analysis"] == "city"
        assert derived["time_range"] == [2012, 2024]
        assert derived["assumptions"]  # bundle assumptions carried over


def test_planning_chain_fallback_without_llm(temp_workspace, monkeypatch):
    _without_llm_env(monkeypatch)
    from fastapi.testclient import TestClient

    from app.api.main import app

    with TestClient(app) as c:
        r = c.post("/api/agent/planning", json={"text": TEXT})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["planning_source"] == "fallback"
        assert data["bundle"]["requirement"]["time_range"] == {"start": 2012, "end": 2024}
        planning_id = data["planning_id"]

        # the chain still drives a search run end to end (explicit providers avoid real network)
        _patch_search_adapters(monkeypatch)
        r2 = c.post("/api/search/runs", json={"planning_id": planning_id, "provider_ids": ["opendata_swiss", "data_gov_uk"]})
        assert r2.status_code == 200, r2.text
        assert r2.json()["planning_source"] == "fallback"

        from app.db.repository import REPO
        from app.domain.enums import SearchRunStatus

        run = REPO.get_search_run(r2.json()["run_id"])
        assert run["status"] == SearchRunStatus.COMPLETED
        assert run["query_plan"]["planning_bundle"]["planning_source"] == "fallback"


def test_planning_run_repository_roundtrip(temp_workspace):
    from app.db.repository import REPO

    pid = REPO.save_planning_run("plan_rt1", "llm", "原始需求文本", {"planning_id": "plan_rt1", "planning_source": "llm"})
    assert pid == "plan_rt1"
    got = REPO.get_planning_run("plan_rt1")
    assert got and got["planning_source"] == "llm"
    assert got["requirement_text"] == "原始需求文本"
    assert got["data"]["planning_id"] == "plan_rt1"
    assert any(r["planning_id"] == "plan_rt1" for r in REPO.list_planning_runs())
    assert REPO.get_planning_run("plan_missing") is None


def test_run_search_bundle_priorities_when_providers_omitted(temp_workspace, monkeypatch):
    """Direct orchestrator call: bundle + provider_ids=None → bundle priorities drive the run."""
    from app.db.repository import REPO
    from app.domain.enums import SearchRunStatus
    from app.search.orchestrator import ORCHESTRATOR

    _patch_search_adapters(monkeypatch)
    bundle = {
        "planning_id": "plan_direct",
        "planning_source": "llm",
        "source_plan": {"provider_priorities": ["opendata_swiss"], "provider_queries": {}, "search_languages": ["en"], "fallbacks": [], "rationale": []},
        "query_plans": [{"provider_id": "opendata_swiss", "queries": ["innovation panel"], "indicator_code_hints": []}],
    }
    run_id = asyncio.run(ORCHESTRATOR.run_search({"requirement_id": "req_bundle_direct"}, None, None, run_id="run_bundle_direct", bundle=bundle))
    run = REPO.get_search_run(run_id)
    assert run["provider_ids"] == ["opendata_swiss"]  # from bundle priorities
    assert run["query_plan"]["planning_bundle"]["planning_source"] == "llm"
    assert run["query_plan"]["opendata_swiss"] == ["innovation panel"]  # from bundle query_plans
    assert run["status"] == SearchRunStatus.COMPLETED


def test_search_run_backward_compatible_without_bundle(temp_workspace, monkeypatch):
    """No planning_id → exactly the legacy behaviour (no planning_bundle key, no planning_source)."""
    _without_llm_env(monkeypatch)
    from fastapi.testclient import TestClient

    from app.api.main import app

    with TestClient(app) as c:
        r = c.post("/api/requirements", json={"text": "构建 2015—2023 年国家层面的青年失业率面板，优先官方数据"})
        assert r.status_code == 200, r.text
        rid = r.json()["requirement_id"]

        _patch_search_adapters(monkeypatch)
        r2 = c.post("/api/search/runs", json={"requirement_id": rid, "provider_ids": ["opendata_swiss"]})
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert "planning_source" not in body

        from app.db.repository import REPO
        from app.domain.enums import SearchRunStatus

        run = REPO.get_search_run(body["run_id"])
        assert run["status"] == SearchRunStatus.COMPLETED
        assert "planning_bundle" not in run["query_plan"]
