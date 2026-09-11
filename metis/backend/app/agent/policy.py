"""Deterministic policy guards (P01-004/P26). Rules own safety, license, access, sanity.

The model proposes; these guards dispose. No LLM output enters downstream without:
  schema validation (pydantic, extra=forbid) + policy checks here.
"""
from __future__ import annotations

import re

from app.agent.client import AgentError
from app.agent.schemas import DataRequirementPlan, SourcePlan

# community/commercial platforms must never outrank official sources for official-data asks
_COMMERCIAL = {"kaggle", "heywhale", "tianchi", "baidu_aistudio", "datafountain", "opendatalab", "data_world", "modelscope_datasets"}
_TIME_RE = re.compile(r"^(19|20)\d{2}$")


def validate_requirement_plan(plan: DataRequirementPlan) -> list[str]:
    """Returns blocking problems (empty = OK). Also coerces obviously bad time ranges."""
    problems: list[str] = []
    start, end = plan.time_range.get("start"), plan.time_range.get("end")
    if start is not None and end is not None:
        if not (_TIME_RE.match(str(start)) and _TIME_RE.match(str(end))):
            problems.append(f"time_range values look invalid: {start}-{end}")
        elif int(start) > int(end):
            problems.append(f"time_range inverted: {start} > {end}")
    if plan.time_range and not start and not end:
        problems.append("time_range present but both start/end missing")
    if not plan.variables:
        problems.append("no variables identified — downstream search would be meaningless")
    if plan.unit_of_analysis == "unknown" and not plan.questions:
        plan.questions.append("研究单位未能确定，请确认（country/province/city/individual…）")
    return problems


def check_source_plan(plan: SourcePlan, requirement: DataRequirementPlan) -> list[str]:
    """Hard policy: official-data asks must not be led by community/commercial platforms."""
    problems: list[str] = []
    text = (plan_str(requirement)).lower()
    wants_official = any(k in text for k in ("官方", "official", "国际组织", "international", "政府", "统计"))
    china_context = any(k in text for k in ("中国", "china", "省级", "地级", "china's")) or any(
        g.lower() in ("cn", "china", "中国") for g in requirement.geography
    )
    head = [p.lower() for p in plan.provider_priorities[:3]]
    if wants_official and head and any(h in _COMMERCIAL for h in head):
        problems.append(f"official-data request led by community platform(s) {head}: priorities reordered by policy")
        official_first = [p for p in plan.provider_priorities if p.lower() not in _COMMERCIAL]
        commercial = [p for p in plan.provider_priorities if p.lower() in _COMMERCIAL]
        plan.provider_priorities = official_first + commercial
    if china_context and plan.provider_queries:
        # Chinese sources must appear for Chinese geography asks
        cn_sources = [p for p in plan.provider_priorities if p.startswith(("nbs_", "cn_", "beijing_", "shanghai_", "shenzhen_", "wuhan_"))]
        if not cn_sources and not any("nbs" in p or "china" in p for p in plan.provider_priorities):
            plan.rationale.append("policy: 中国地理需求应至少尝试一个中国官方来源（nbs_china 等）")
    return problems


def plan_str(requirement: DataRequirementPlan) -> str:
    parts = [requirement.research_goal] + [v.concept for v in requirement.variables] + requirement.geography + requirement.preferred_sources
    return " ".join(parts)


def reject_unsafe(prompt: str) -> str | None:
    """Simple content policy: refuse planning for clearly unsafe requests."""
    lowered = prompt.lower()
    for marker in ("绕过验证码", "bypass captcha", "破解密码", "crack password", "爬取付费", "bypass paywall"):
        if marker in lowered:
            return f"request refused by policy: contains '{marker}'"
    return None


def ensure_planner_available() -> None:
    """Raises CONFIG_MISSING with the actionable message when LLM env is unset."""
    from app.agent.client import LLMConfig

    LLMConfig.from_env()


__all__ = ["validate_requirement_plan", "check_source_plan", "reject_unsafe", "ensure_planner_available", "AgentError"]
