"""Requirement Planner (P01-005/006): LLM primary, rule fallback, rule validator.

模型负责理解（含词典外语义），规则负责兜底与校验。模型不可用时基础需求仍可处理。
"""
from __future__ import annotations

from app.agent.client import AgentError, LLMClient
from app.agent.policy import plan_str, reject_unsafe, validate_requirement_plan
from app.agent.schemas import DataRequirementPlan, VariableConcept
from app.core.logging import get_logger

log = get_logger("agent.requirement")

SYSTEM_PROMPT = """You are the requirement planner of Metis Data, a research-data agent.
Convert the user's natural-language data request into a strict JSON object with EXACTLY these keys:
research_goal (string), unit_of_analysis (one of country|province|prefecture|city|individual|firm|household|entity|year|unknown),
geography (array of strings, use ISO codes or clear names), time_range (object {start:int|null, end:int|null}),
frequency (annual|quarterly|monthly|daily|unknown),
variables (array of {concept, role, description} where role is outcome|exposure|mediator|moderator|control|identifier),
constraints (object), preferred_sources (array), deliverables (array), assumptions (array), questions (array of open questions for the user).
Rules: never invent indicator codes here; every important inference must appear in assumptions; put anything ambiguous in questions; output JSON only."""


async def plan_requirement(text: str) -> tuple[DataRequirementPlan, str]:
    """Returns (plan, source) where source is 'llm' | 'rule_fallback'.

    Acceptance (P01-005): a request OUTSIDE the handwritten lexicon — e.g.
    '中国城市科技创新、土地财政依赖、环境规制和产业升级' — must yield >=4 concepts
    when the LLM is configured; without an LLM the rule fallback still produces a
    usable basic plan (P01-006).
    """
    unsafe = reject_unsafe(text)
    if unsafe:
        raise AgentError("STATE_INVALID", unsafe, retryable=False)

    if _llm_configured():
        try:
            client = LLMClient()
            raw = await client.complete_json(SYSTEM_PROMPT, text)
            plan = DataRequirementPlan(**raw)
            problems = validate_requirement_plan(plan)
            blocking = [p for p in problems if "no variables" in p or "inverted" in p or "invalid" in p]
            if blocking:
                raise AgentError("BAD_RESPONSE", f"LLM plan rejected by validator: {blocking}", retryable=True)
            return plan, "llm"
        except AgentError as exc:
            if exc.code == "STATE_INVALID":
                raise
            log.warning_ctx("llm requirement planning failed; using rule fallback", error=exc.message, code=exc.code)
        except Exception as exc:  # noqa: BLE001
            log.warning_ctx("llm requirement planning crashed; using rule fallback", error=str(exc)[:200])
    return rule_fallback_plan(text), "rule_fallback"


def _llm_configured() -> bool:
    import os

    return bool(os.environ.get("METIS_LLM_BASE_URL", "").strip()) and bool(os.environ.get("METIS_LLM_MODEL", "").strip())


def plan_from_rule_to_schema(text: str) -> DataRequirementPlan:
    """Wrapper converting the deterministic parser output into the agent schema."""
    from app.search.parser import parse_requirement

    req = parse_requirement(text)
    variables = []
    role_map = {
        "outcomes": "outcome", "exposures": "exposure", "mediators": "mediator",
        "moderators": "moderator", "controls": "control", "identifiers": "identifier", "optional": "control",
    }
    for role_field, role in role_map.items():
        for name in getattr(req.variables, role_field):
            variables.append(VariableConcept(concept=name, role=role, description="from rule lexicon"))
    tr = req.time_range
    return DataRequirementPlan(
        research_goal=req.research_question or req.raw_request,
        unit_of_analysis=req.unit_of_analysis,
        geography=list(req.geography),
        time_range={"start": tr[0] if tr else None, "end": tr[1] if tr else None},
        frequency=req.frequency,
        variables=variables,
        constraints={"max_missing_rate": req.max_missing_rate} if req.max_missing_rate else {},
        preferred_sources=list(req.preferred_sources),
        deliverables=[],
        assumptions=list(req.assumptions),
        questions=[],
    )


# alias used by API fallback path
def rule_fallback_plan(text: str) -> DataRequirementPlan:
    return plan_from_rule_to_schema(text)
