"""Planning-chain orchestrator (Phase B): LLM planning becomes the search main chain.

One call — build_planning_bundle(text) — runs the full chain
requirement → measurements → sources → queries and assembles a PlanningBundle.
Rules stay exactly where they belong: fallback when a stage's LLM call fails and
deterministic validators/policy (the rules never disappear, they stop being the
default path). Bundles are persisted so a search run can be driven purely by
planning_id.
"""
from __future__ import annotations

from typing import Any

from app.agent.measurement_planner import plan_measurements
from app.agent.requirement_planner import plan_requirement
from app.agent.schemas import PlanningBundle, ProviderQueryPlan, ReviewPoint
from app.agent.source_planner import plan_queries, plan_sources
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.schemas import new_id

log = get_logger("agent.orchestrator")

# markers the deterministic fallbacks leave behind (used for planning_source provenance)
_RULE_SOURCE_MARKER = "deterministic rule baseline"
_FALLBACK_MEASURE_MARKER = "deterministic fallback dictionary"
_UNRESOLVED_MEASURE_MARKER = "[unresolved]"


def _measurement_stage_is_llm(measurements: list, requirement_llm: bool) -> bool:
    """The measurement planner returns plans only; detect its path via notes."""
    if not measurements:
        return requirement_llm  # no concepts → stage followed the requirement stage
    return not any(
        _FALLBACK_MEASURE_MARKER in (m.notes or "") or (m.notes or "").startswith(_UNRESOLVED_MEASURE_MARKER)
        for m in measurements
    )


async def build_planning_bundle(text: str, planning_id: str | None = None) -> PlanningBundle:
    """Run the full planning chain over a natural-language request.

    planning_source provenance: every stage LLM → "llm"; every stage fallback →
    "fallback"; any mix → "mixed". Policy problems become warning review points.
    """
    requirement, requirement_source = await plan_requirement(text)
    requirement_llm = requirement_source == "llm"

    measurements = await plan_measurements([{"concept": v.concept, "role": v.role} for v in requirement.variables])
    source_plan, policy_problems = await plan_sources(requirement, measurements)
    query_plans = await plan_queries(requirement, source_plan, measurements)

    stage_llm = [
        requirement_llm,
        _measurement_stage_is_llm(measurements, requirement_llm),
        not any(_RULE_SOURCE_MARKER in r for r in source_plan.rationale),
    ]
    planning_source = "llm" if all(stage_llm) else ("fallback" if not any(stage_llm) else "mixed")

    review_points = [
        ReviewPoint(severity="warning", topic="source_plan_policy", message=str(p), remediation="check provider priorities for policy compliance")
        for p in policy_problems
    ]

    bundle = PlanningBundle(
        planning_id=planning_id or new_id("plan"),
        requirement=requirement,
        measurements=measurements,
        source_plan=source_plan,
        query_plans=[ProviderQueryPlan(**q.model_dump()) for q in query_plans],
        assumptions=list(requirement.assumptions),
        review_points=review_points,
        planning_source=planning_source,
    )
    log.info_ctx(
        "planning bundle built",
        planning_id=bundle.planning_id,
        source=planning_source,
        providers=len(bundle.source_plan.provider_priorities),
        queries=len(bundle.query_plans),
    )
    return bundle


def save_bundle(bundle: PlanningBundle | dict, requirement_text: str | None = None) -> str:
    """Persist a PlanningBundle (pydantic model or dict). Returns the planning_id."""
    payload: dict[str, Any] = bundle if isinstance(bundle, dict) else bundle.model_dump(mode="json")
    planning_id = payload.get("planning_id") or new_id("plan")
    payload["planning_id"] = planning_id
    text = requirement_text if requirement_text is not None else str((payload.get("requirement") or {}).get("research_goal", ""))
    REPO.save_planning_run(planning_id, str(payload.get("planning_source", "fallback")), text, payload)
    return planning_id


def load_bundle(planning_id: str) -> dict | None:
    """Load a persisted bundle by id; None when unknown.

    The returned dict carries the original user text under "requirement_text"
    (stored beside the bundle) so downstream can rebuild a DataRequirement with
    a verbatim raw_request.
    """
    run = REPO.get_planning_run(planning_id)
    if not run:
        return None
    data = dict(run.get("data") or {})
    data.setdefault("planning_id", planning_id)
    data.setdefault("requirement_text", run.get("requirement_text", ""))
    return data
