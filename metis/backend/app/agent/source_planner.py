"""Source Planner (P01-008) + Search Query Planner (P01-009).

SourcePlan: 指标+地域 → Provider 优先级（中国省级财政问题绝不把 Kaggle 排前面）。
SearchQueryPlan: 中文/英文/Provider-specific query + 指标代码提示（不再局限于硬编码词典——
LLM 主路径生成，规则路径提供确定性基线）。
"""
from __future__ import annotations

from app.agent.client import LLMClient
from app.agent.policy import check_source_plan
from app.agent.schemas import DataRequirementPlan, SearchQueryPlan, SourcePlan, VariableMeasurementPlan
from app.core.logging import get_logger
from app.providers.registry import get_registry

log = get_logger("agent.source")

SOURCE_SYSTEM_PROMPT = """You are the source planner of Metis Data. Given a research data requirement and measurement plans,
choose which data providers to search, in what priority order, and craft per-provider queries.
Return strict JSON: {"provider_priorities":["provider_id",...],"provider_queries":{"provider_id":["query",...]},"search_languages":["zh","en"],"fallbacks":[...],"rationale":["..."]}
Rules: use ONLY provider_ids from the provided registry list; official/international sources outrank community platforms when the user prefers official data; Chinese geography needs Chinese sources; provide both Chinese and English queries per provider. Output JSON only."""

# Indicator code hints for query planning (deterministic baseline; LLM extends)
INDICATOR_HINTS: dict[str, list[str]] = {
    "youth_unemployment_rate": ["SL.UEM.1524.ZS"],
    "unemployment_rate": ["SL.UEM.TOTL.ZS"],
    "gdp_per_capita": ["NY.GDP.PCAP.CD", "NY.GDP.PCAP.KD"],
    "gdp": ["NY.GDP.MKTP.CD", "NY.GDP.MKTP.KD.ZG"],
    "education_level": ["SE.TER.ENRR", "SE.PRM.ENRR"],
    "aging": ["SP.POP.65UP.TO.ZS"],
    "population": ["SP.POP.TOTL"],
}


async def plan_sources(requirement: DataRequirementPlan, measurements: list[VariableMeasurementPlan]) -> tuple[SourcePlan, list[str]]:
    """Returns (SourcePlan, policy_problems). LLM primary; deterministic rules baseline + policy enforcement."""
    registry_ids = [p.provider_id for p in get_registry().all()]
    plan: SourcePlan | None = None
    if _llm_configured():
        try:
            client = LLMClient()
            user = (
                f"Requirement: {requirement.model_dump_json()}\n"
                f"Measurements: {[m.model_dump() for m in measurements]}\n"
                f"Available provider_ids: {registry_ids}"
            )
            plan = SourcePlan(**await client.complete_json(SOURCE_SYSTEM_PROMPT, user))
            valid_ids = set(registry_ids)
            plan.provider_priorities = [p for p in plan.provider_priorities if p in valid_ids]
            plan.provider_queries = {k: v for k, v in plan.provider_queries.items() if k in valid_ids and v}
        except Exception as exc:  # noqa: BLE001
            log.warning_ctx("llm source planning failed; using rules", error=str(exc)[:200])
            plan = None
    if plan is None:
        plan = _rule_plan(requirement, measurements)

    problems = check_source_plan(plan, requirement)
    return plan, problems


def _rule_plan(requirement: DataRequirementPlan, measurements: list[VariableMeasurementPlan]) -> SourcePlan:
    from app.domain.schemas import DataRequirement as DomainReq, VariableRequest

    # reuse the existing deterministic selector on a domain-shaped requirement
    variables = VariableRequest()
    role_field = {"outcome": "outcomes", "exposure": "exposures", "mediator": "mediators", "moderator": "moderators", "control": "controls", "identifier": "identifiers"}
    for v in requirement.variables:
        getattr(variables, role_field.get(v.role, "controls")).append(v.concept)
    tr = requirement.time_range
    domain_req = DomainReq(
        raw_request=requirement.research_goal,
        unit_of_analysis=requirement.unit_of_analysis,
        geography=requirement.geography,
        time_range=(tr["start"], tr["end"]) if tr.get("start") and tr.get("end") else None,
        frequency=requirement.frequency,
        variables=variables,
        preferred_sources=requirement.preferred_sources,
    )
    from app.search.selector import plan_queries as rule_plan_queries, select_providers

    providers = select_providers(domain_req, max_providers=8)
    queries = rule_plan_queries(domain_req, providers)
    priorities = [p.provider_id for p in providers]
    # measurement-driven boost: providers whose adapters own hinted indicator codes
    for m in measurements:
        for alt in ([m.preferred_measure] and []) + m.alternative_measures + m.proxy_variables:
            code = getattr(alt, "indicator_code_hint", "")
            if code and code.startswith(("SL.", "NY.", "SE.", "SP.")):
                if "world_bank" in priorities:
                    priorities.remove("world_bank")
                    priorities.insert(0, "world_bank")
    return SourcePlan(
        provider_priorities=priorities,
        provider_queries=queries,
        search_languages=["en"] + (["zh"] if any("中国" in g or g.upper() == "CN" for g in requirement.geography) else []),
        fallbacks=[],
        rationale=["deterministic rule baseline (LLM unavailable or failed)"],
    )


async def plan_queries(requirement: DataRequirementPlan, source_plan: SourcePlan, measurements: list[VariableMeasurementPlan]) -> list[SearchQueryPlan]:
    """Per-provider bilingual query plan with indicator-code hints (P01-009)."""
    hints: list[str] = []
    for m in measurements:
        hints += INDICATOR_HINTS.get(_canon(m.concept), [])
        for alt in m.alternative_measures + m.proxy_variables:
            if alt.indicator_code_hint:
                hints.append(alt.indicator_code_hint)

    plans: list[SearchQueryPlan] = []
    for provider_id, queries in source_plan.provider_queries.items():
        if not queries:
            continue
        plans.append(SearchQueryPlan(provider_id=provider_id, queries=queries[:4], indicator_code_hints=hints[:6]))
    # ensure at least a baseline plan for priority providers without queries
    for provider_id in source_plan.provider_priorities:
        if provider_id not in {p.provider_id for p in plans}:
            concepts = [m.concept.replace("_", " ") for m in measurements][:3]
            base = " ".join(concepts) or requirement.research_goal[:60]
            plans.append(SearchQueryPlan(provider_id=provider_id, queries=[base], indicator_code_hints=hints[:6]))
    return plans


def _llm_configured() -> bool:
    import os

    return bool(os.environ.get("METIS_LLM_BASE_URL", "").strip()) and bool(os.environ.get("METIS_LLM_MODEL", "").strip())


def _canon(concept: str) -> str:
    c = concept.lower().strip().replace(" ", "_")
    return c
