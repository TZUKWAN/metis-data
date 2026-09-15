"""Phase 1 acceptance: LLM Agent Core (P01-001..011).

Tests use a STUB OpenAI-compatible HTTP server to exercise OUR client/planner
pipeline (schema enforcement, retry, fallback). Real-LLM runs require user
METIS_LLM_* env and are recorded separately — never faked here.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


# ---------- stub OpenAI-compatible server ----------
class _Handler(BaseHTTPRequestHandler):
    behavior: dict = {"fail_times": 0, "status": 200, "content": "{}"}

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


# ---------- P01-002: config ----------
def test_client_missing_config_clear_error(monkeypatch):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("METIS_LLM_MODEL", raising=False)
    from app.agent.client import LLMConfig
    from app.core.errors import MetisError

    with pytest.raises(MetisError) as e:
        LLMConfig.from_env()
    assert e.value.code == "CONFIG_MISSING"
    assert "METIS_LLM_BASE_URL" in e.value.message


def test_client_api_key_not_logged(monkeypatch, caplog):
    import logging

    from app.agent.client import LLMClient
    from app.core.logging import redact

    key = "sk-very-secret-METIS-TEST-SECRET-123"
    _with_llm_env(monkeypatch, "http://127.0.0.1:9", key=key)
    client = LLMClient()
    assert redact(f"Authorization Bearer {key}").count("sk-very-secret") == 0
    # log through the app's own adapter (production path) — must be masked
    from app.core.logging import get_logger

    logger = get_logger("agent.client")
    with caplog.at_level(logging.INFO):
        logger.info_ctx("auth header seen", auth=f"Bearer {key}")
        logger.info(f"auth {key}")
    assert key not in caplog.text


# ---------- P01-003: retry / error classification ----------
def test_retry_on_5xx_then_success(monkeypatch, stub_llm):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    behavior.update({"fail_times": 1, "status": 500, "content": {"ok": True}})
    from app.agent.client import LLMClient

    result = asyncio.new_event_loop().run_until_complete(LLMClient().complete_json("sys", "user"))
    assert result == {"ok": True}


def test_429_classified_rate_limited(monkeypatch, stub_llm):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    monkeypatch.setenv("METIS_LLM_MAX_RETRIES", "0")
    behavior.update({"fail_times": 1, "status": 429})
    from app.agent.client import AgentError, LLMClient

    with pytest.raises(AgentError) as e:
        asyncio.new_event_loop().run_until_complete(LLMClient().complete_json("s", "u"))
    assert e.value.code == "PROVIDER_RATE_LIMITED"


def test_401_classified_auth_error(monkeypatch, stub_llm):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    behavior.update({"fail_times": 1, "status": 401})
    from app.agent.client import AgentError, LLMClient

    with pytest.raises(AgentError) as e:
        asyncio.new_event_loop().run_until_complete(LLMClient().complete_json("s", "u"))
    assert e.value.code == "AUTH_ERROR"


def test_timeout_classified(monkeypatch):
    _with_llm_env(monkeypatch, "http://127.0.0.1:9")  # nothing listens
    monkeypatch.setenv("METIS_LLM_TIMEOUT", "1")
    from app.agent.client import AgentError, LLMClient

    with pytest.raises(AgentError) as e:
        asyncio.new_event_loop().run_until_complete(LLMClient().complete_json("s", "u"))
    assert e.value.code == "TIMEOUT"


# ---------- P01-004: schema enforcement ----------
def test_invalid_llm_output_rejected(monkeypatch, stub_llm):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    # missing required research_goal → pydantic rejects → planner falls back (no crash)
    behavior.update({"fail_times": 0, "content": {"unit_of_analysis": "country"}})
    from app.agent.requirement_planner import plan_requirement

    plan, source = asyncio.new_event_loop().run_until_complete(plan_requirement("构建面板"))
    assert source == "rule_fallback"


# ---------- P01-005: out-of-lexicon requirement via LLM ----------
def test_out_of_lexicon_requirement_llm(monkeypatch, stub_llm):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    llm_plan = {
        "research_goal": "中国城市科技创新、土地财政依赖、环境规制和产业升级关系研究",
        "unit_of_analysis": "city",
        "geography": ["CN"],
        "time_range": {"start": 2010, "end": 2023},
        "frequency": "annual",
        "variables": [
            {"concept": "科技创新", "role": "outcome", "description": "城市创新能力"},
            {"concept": "土地财政依赖", "role": "exposure", "description": "土地出让收入依赖"},
            {"concept": "环境规制", "role": "exposure", "description": "环境监管强度"},
            {"concept": "产业升级", "role": "outcome", "description": "产业结构高级化"},
        ],
        "constraints": {}, "preferred_sources": [], "deliverables": [], "assumptions": [], "questions": [],
    }
    behavior.update({"fail_times": 0, "content": llm_plan})
    from app.agent.requirement_planner import plan_requirement

    plan, source = asyncio.new_event_loop().run_until_complete(plan_requirement("中国城市科技创新、土地财政依赖、环境规制和产业升级"))
    assert source == "llm"
    concepts = {v.concept for v in plan.variables}
    assert len([c for c in concepts if c]) >= 4
    assert plan.unit_of_analysis == "city"


# ---------- P01-006: rule fallback keeps basic flow alive ----------
def test_rule_fallback_without_llm(monkeypatch):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    from app.agent.requirement_planner import plan_requirement

    plan, source = asyncio.new_event_loop().run_until_complete(plan_requirement("构建 2015—2023 年国家层面的青年失业率、人均 GDP 面板，优先官方数据"))
    assert source == "rule_fallback"
    assert plan.unit_of_analysis == "country"
    assert plan.time_range == {"start": 2015, "end": 2023}
    assert any("unemployment" in v.concept or "失业" in v.concept for v in plan.variables)


# ---------- P01-007: measurement planner ----------
def test_measurement_planner_fallback_dictionary(monkeypatch):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    from app.agent.measurement_planner import plan_measurements

    plans = asyncio.new_event_loop().run_until_complete(
        plan_measurements([
            {"concept": "digital_economy", "role": "exposure"},
            {"concept": "fiscal_pressure", "role": "exposure"},
            {"concept": "环境规制", "role": "moderator"},
        ])
    )
    assert len(plans) == 3
    digital = plans[0]
    assert digital.preferred_measure and digital.alternative_measures
    assert digital.aggregation_semantics in ("mean", "sum", "last", "first", "median", "weighted_mean", "min", "max", "none", "unknown")
    env = plans[2]
    assert env.preferred_measure  # Chinese concept maps into dictionary


# ---------- P01-008: source planner policy ----------
def test_source_planner_china_fiscal_not_kaggle(monkeypatch):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    from app.agent.schemas import DataRequirementPlan, VariableConcept
    from app.agent.source_planner import plan_sources

    req = DataRequirementPlan(
        research_goal="中国省级财政压力与土地财政面板",
        unit_of_analysis="province",
        geography=["CN"],
        time_range={"start": 2010, "end": 2022},
        frequency="annual",
        variables=[VariableConcept(concept="fiscal_pressure", role="outcome")],
        preferred_sources=["official"],
    )
    plan, problems = asyncio.new_event_loop().run_until_complete(plan_sources(req, []))
    head3 = [p.lower() for p in plan.provider_priorities[:3]]
    assert "kaggle" not in head3
    assert plan.provider_priorities and plan.provider_queries
    # policy note for missing CN sources when applicable
    assert isinstance(problems, list)


# ---------- P01-009: query plan with indicator hints ----------
def test_query_plan_indicator_hints(monkeypatch, stub_llm):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    from app.agent.schemas import DataRequirementPlan, SourcePlan, VariableConcept, VariableMeasurementPlan
    from app.agent.source_planner import plan_queries

    req = DataRequirementPlan(research_goal="youth unemployment panel", unit_of_analysis="country", geography=["global"], time_range={"start": 2015, "end": 2023}, frequency="annual", variables=[VariableConcept(concept="youth_unemployment_rate")])
    sp = SourcePlan(provider_priorities=["world_bank"], provider_queries={"world_bank": ["youth unemployment"]}, search_languages=["en"])
    measurements = [
        VariableMeasurementPlan(concept="youth_unemployment_rate", role="outcome", preferred_measure="ILO youth unemployment rate", unit="percent")
    ]
    # measurement planner alternative carries the WB hint
    from app.agent.schemas import MeasurementCandidate

    measurements[0].alternative_measures = [MeasurementCandidate(measure="WB youth unemployment", kind="alternative", indicator_code_hint="SL.UEM.1524.ZS")]
    plans = asyncio.new_event_loop().run_until_complete(plan_queries(req, sp, measurements))
    wb = next(p for p in plans if p.provider_id == "world_bank")
    assert "SL.UEM.1524.ZS" in wb.indicator_code_hints
    assert wb.queries


# ---------- P01-010: critic ----------
def test_critic_flags_conflicting_requirement(monkeypatch):
    monkeypatch.delenv("METIS_LLM_BASE_URL", raising=False)
    from app.agent.critic import review_requirement
    from app.agent.schemas import DataRequirementPlan

    bad = DataRequirementPlan(research_goal="x", unit_of_analysis="country", time_range={"start": 2020, "end": 2010}, frequency="unknown", variables=[])
    review = asyncio.new_event_loop().run_until_complete(review_requirement(bad))
    assert review.ok is False
    blocking = [p for p in review.review_points if p.severity == "blocking"]
    assert blocking  # inverted time + no variables flagged


# ---------- P01-011: agent API ----------
def test_agent_api_endpoints(monkeypatch, stub_llm):
    base, behavior = stub_llm
    _with_llm_env(monkeypatch, base)
    behavior.update({"fail_times": 0, "content": {
        "research_goal": "城市创新面板", "unit_of_analysis": "city", "geography": ["CN"],
        "time_range": {"start": 2012, "end": 2024}, "frequency": "annual",
        "variables": [{"concept": "科技创新", "role": "outcome"}, {"concept": "土地财政依赖", "role": "exposure"},
                       {"concept": "环境规制", "role": "moderator"}, {"concept": "产业升级", "role": "outcome"}],
        "constraints": {}, "preferred_sources": [], "deliverables": [], "assumptions": [], "questions": [],
    }})
    import os
    import tempfile

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

    with TestClient(app) as c:
        r = c.post("/api/agent/requirements/plan", json={"text": "中国城市科技创新、土地财政依赖、环境规制和产业升级"})
        assert r.status_code == 200 and r.json()["source"] == "llm"
        plan = r.json()["plan"]
        assert len(plan["variables"]) >= 4
        r = c.post("/api/agent/measurements/plan", json={"concepts": [{"concept": "innovation", "role": "outcome"}]})
        assert r.status_code == 200 and r.json()["plans"]
        r = c.post("/api/agent/sources/plan", json={"requirement": plan})
        assert r.status_code == 200 and r.json()["source_plan"]["provider_priorities"]
