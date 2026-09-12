"""Candidate Analyzer (P01-004 schema) + Build Planner (Phase 17 groundwork).

candidate_analyzer: LLM-assisted relevance/coverage/limitations on normalized candidates;
deterministic fallback reuses the rule-based evaluator signals.
build_planner: requirement + selected assets + profiles → BuildPlan (strict schema).
"""
from __future__ import annotations

from app.agent.client import LLMClient
from app.agent.schemas import (
    AggregationPlan,
    BuildPlan,
    CandidateAnalysis,
    JoinPlan,
    ReviewPoint,
)
from app.core.logging import get_logger

log = get_logger("agent.candidate")

CANDIDATE_PROMPT = """You are the candidate analyzer of Metis Data. Given a data requirement and one normalized dataset candidate,
judge its relevance and coverage. Return strict JSON: {"candidate_id":"...","relevance":"high|medium|low|unknown","variable_coverage":["concept",...],"limitations":["..."],"license_concern":"...","reasons":["..."]}
Never claim a variable exists just because the title contains a keyword; only use the provided variable_hints/description evidence. Output JSON only."""

# stock vs flow semantics for aggregation recommendation (P19-004 groundwork)
SEMANTIC_AGG: dict[str, str] = {
    # rate/index-like concepts → mean
    "rate": "mean", "share": "mean", "ratio": "mean", "index": "mean", "price": "mean", "percent": "mean",
    # flow-like → sum
    "revenue": "sum", "expenditure": "sum", "export": "sum", "import": "sum", "investment": "sum", "emission": "sum", "patent": "sum",
    # stock-like → last
    "stock": "last", "population": "last", "balance": "last", "area": "last",
}


async def analyze_candidate(requirement_json: dict, candidate_json: dict) -> CandidateAnalysis:
    if _llm_configured():
        try:
            client = LLMClient()
            user = f"Requirement: {requirement_json}\nCandidate: {candidate_json}"
            return CandidateAnalysis(**await client.complete_json(CANDIDATE_PROMPT, user))
        except Exception as exc:  # noqa: BLE001
            log.warning_ctx("llm candidate analysis failed; deterministic signals only", error=str(exc)[:160])
    # deterministic fallback: derive from evaluator fields produced by search.recommend
    score = float(candidate_json.get("score") or 0)
    relevance = "high" if score >= 0.6 else "medium" if score >= 0.35 else "low"
    return CandidateAnalysis(
        candidate_id=candidate_json.get("candidate_id", ""),
        relevance=relevance,
        variable_coverage=[],
        limitations=list(candidate_json.get("limitations", []))[:5],
        license_concern="UNKNOWN license" if str(candidate_json.get("license", "")).upper() == "UNKNOWN" else "",
        reasons=list(candidate_json.get("reasons", []))[:5],
    )


async def plan_build(requirement_json: dict, assets: list[dict]) -> BuildPlan:
    """assets: [{artifact_id, profile:{columns, likely}, variables:[VariableSemantic]}...]"""
    if _llm_configured():
        try:
            client = LLMClient()
            system = (
                "You are the build planner of Metis Data. Given a requirement and dataset asset profiles, produce a strict JSON BuildPlan: "
                '{"target_schema":[],"inputs":["artifact_id"],"input_roles":{},"field_mappings":[{"source_artifact_id","source_field","target_field"}],'
                '"entity_strategy":"country|province|city|firm|person","time_strategy":"annual|quarterly|monthly","unit_conversions":[],'
                '"aggregations":[{"field","method","weight_field","rationale"}],"joins":[{"left_input","right_input","keys","expected_cardinality","join_type","coverage_requirement"}],'
                '"missing_policy":[],"derived_variables":[],"validations":[],"review_points":[]}. '
                "Pick keys from actual profile columns (canonical iso3/year after normalization); never assume country/year blindly — check the profiles. "
                "Recommend per-variable aggregation semantics (flow=sum, stock/rate=mean or last). Output JSON only."
            )
            user = f"Requirement: {requirement_json}\nAssets: {assets}"
            return BuildPlan(**await client.complete_json(system, user))
        except Exception as exc:  # noqa: BLE001
            log.warning_ctx("llm build planning failed; deterministic plan", error=str(exc)[:200])
    return _deterministic_plan(assets)


def _deterministic_plan(assets: list[dict]) -> BuildPlan:
    """Baseline plan from profiles: canonical keys (iso3/year) if profiles hint them,
    per-variable aggregation via SEMANTIC_AGG; review points for unknowns."""
    plan = BuildPlan(inputs=[a["artifact_id"] for a in assets])
    points: list[ReviewPoint] = []
    if not assets:
        points.append(ReviewPoint(severity="blocking", topic="build", message="没有输入资产"))
        plan.review_points = points
        return plan
    # keys: only if every asset profile suggests geo+time
    geo_ok = all(any("iso3" in c or "country" in str(c).lower() for c in (a.get("profile", {}).get("columns") or [])) for a in assets)
    year_ok = all(any(str(c).lower() in ("year", "time") or str(c).isdigit() for c in (a.get("profile", {}).get("columns") or [])) for a in assets)
    if geo_ok and year_ok:
        plan.entity_strategy = "country"
        plan.time_strategy = "annual"
        if len(assets) >= 2:
            plan.joins = [
                JoinPlan(left_input=assets[0]["artifact_id"], right_input=assets[1]["artifact_id"], keys=["iso3", "year"], expected_cardinality="1:1", join_type="inner", coverage_requirement=0.8)
            ]
    else:
        points.append(ReviewPoint(severity="blocking", topic="keys", message="输入资产缺少可识别的地理/时间键，无法自动确定 join key", remediation="人工确认 key 或补充数据"))
    # aggregations from variable semantics
    for a in assets:
        for vs in a.get("variables", []):
            concept = str(vs.get("canonical_name", "")).lower()
            method = next((m for marker, m in SEMANTIC_AGG.items() if marker in concept), None)
            if method is None:
                points.append(ReviewPoint(severity="warning", topic="aggregation", message=f"字段 {vs.get('canonical_name')} 聚合语义未知，不默认 mean", remediation="确认口径后选择聚合方法"))
                plan.aggregations.append(AggregationPlan(field=str(vs.get("canonical_name")), method="none", rationale="unknown semantics → needs review"))
            else:
                plan.aggregations.append(AggregationPlan(field=str(vs.get("canonical_name")), method=method, rationale=f"semantic marker '{next(k for k in SEMANTIC_AGG if SEMANTIC_AGG[k] == method)}' in concept"))
    plan.review_points = points
    return plan


def _llm_configured() -> bool:
    import os

    return bool(os.environ.get("METIS_LLM_BASE_URL", "").strip()) and bool(os.environ.get("METIS_LLM_MODEL", "").strip())


def plan_build_sync(requirement_json: dict, assets: list[dict]) -> BuildPlan:
    """Synchronous, deterministic planning wrapper (Phase H).

    Directly applies the rule-based planner (_deterministic_plan) without any LLM
    call, so planning is reproducible in environments without LLM credentials.
    requirement_json is accepted for signature symmetry with plan_build; the
    deterministic rules derive the plan from asset profiles alone.
    assets: [{artifact_id, profile: {columns, ...}, variables: [{canonical_name, ...}]}]
    """
    return _deterministic_plan(assets)
