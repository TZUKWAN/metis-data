"""Planner Critic (P01-010): second-pass review of plans.

Deterministic checks always run; LLM critic adds conceptual review when configured.
明显矛盾需求能指出冲突。
"""
from __future__ import annotations

from app.agent.client import LLMClient
from app.agent.policy import validate_requirement_plan
from app.agent.schemas import BuildPlan, CriticReview, DataRequirementPlan, ReviewPoint, SourcePlan
from app.core.logging import get_logger

log = get_logger("agent.critic")

CRITIC_PROMPT = """You are the critic of Metis Data's planning layer. Review the requirement and source plan for:
missing concepts, measurement logic problems, geography inconsistencies, unit issues, time issues, source problems.
Return strict JSON: {"ok": bool, "review_points": [{"severity":"info|warning|blocking","topic":"...","message":"...","remediation":"..."}]}
Only include real issues. Output JSON only."""


async def review_requirement(requirement: DataRequirementPlan, source_plan: SourcePlan | None = None) -> CriticReview:
    points: list[ReviewPoint] = []

    # deterministic checks (always)
    for problem in validate_requirement_plan(requirement):
        severity = "blocking" if ("no variables" in problem or "inverted" in problem or "invalid" in problem) else "warning"
        points.append(ReviewPoint(severity=severity, topic="requirement", message=problem, remediation="请修改需求后重试"))

    # conflict: frequency vs time granularity
    if requirement.frequency == "daily" and requirement.unit_of_analysis in ("country", "province") and requirement.time_range.get("start") and requirement.time_range.get("end"):
        span = int(requirement.time_range["end"]) - int(requirement.time_range["start"])
        if span >= 3:
            points.append(ReviewPoint(severity="warning", topic="time", message=f"日度频率跨 {span} 年的国家级面板数据量异常庞大，确认是否真需要 daily", remediation="考虑使用 monthly/annual"))

    # source plan sanity
    if source_plan is not None and not source_plan.provider_priorities:
        points.append(ReviewPoint(severity="blocking", topic="source", message="没有任何可用 Provider 被选择", remediation="放宽来源限制或降低 trust requirement"))
    if source_plan is not None and len(source_plan.provider_priorities) < 2:
        points.append(ReviewPoint(severity="warning", topic="source", message="仅选择了 1 个 Provider，多源交叉验证建议至少 2-4 个", remediation="加入更多来源"))

    # LLM conceptual review (additive)
    if _llm_configured():
        try:
            client = LLMClient()
            user = f"Requirement: {requirement.model_dump_json()}\nSourcePlan: {source_plan.model_dump_json() if source_plan else 'none'}"
            review = CriticReview(**await client.complete_json(CRITIC_PROMPT, user))
            points.extend(review.review_points)
        except Exception as exc:  # noqa: BLE001
            log.warning_ctx("llm critic unavailable; deterministic review only", error=str(exc)[:160])

    return CriticReview(ok=not any(p.severity == "blocking" for p in points), review_points=points)


async def review_build_plan(plan: BuildPlan) -> CriticReview:
    points: list[ReviewPoint] = []
    if not plan.inputs:
        points.append(ReviewPoint(severity="blocking", topic="build", message="Build 没有输入数据集", remediation="先下载数据"))
    if plan.joins:
        for j in plan.joins:
            if j.expected_cardinality == "m:m":
                points.append(ReviewPoint(severity="blocking", topic="join", message=f"join {j.left_input}×{j.right_input} 预期 m:m", remediation="先聚合或去重一方"))
            if not j.keys:
                points.append(ReviewPoint(severity="blocking", topic="join", message="join 未定义 key", remediation="显式声明 join keys"))
    unknown_agg = [a.field for a in plan.aggregations if a.method == "none"]
    if unknown_agg:
        points.append(ReviewPoint(severity="warning", topic="aggregation", message=f"字段 {unknown_agg[:5]} 未指定聚合方法", remediation="为每个变量选择聚合语义"))
    return CriticReview(ok=not any(p.severity == "blocking" for p in points), review_points=points)


def _llm_configured() -> bool:
    import os

    return bool(os.environ.get("METIS_LLM_BASE_URL", "").strip()) and bool(os.environ.get("METIS_LLM_MODEL", "").strip())
