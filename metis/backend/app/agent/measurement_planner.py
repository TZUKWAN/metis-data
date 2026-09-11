"""Measurement Planner (P01-007): abstract concepts → concrete measurement plans.

LLM produces the plan when configured; a deterministic dictionary of common
social-science concepts provides the fallback so the pipeline never dies.
"""
from __future__ import annotations

from app.agent.client import LLMClient
from app.agent.schemas import MeasurementCandidate, VariableMeasurementPlan
from app.core.logging import get_logger

log = get_logger("agent.measurement")

SYSTEM_PROMPT = """You are the measurement planner of Metis Data.
For each input concept, propose how to measure it with public statistical data.
Return strict JSON: {"plans": [{"concept","role","preferred_measure","alternative_measures":[{"measure","kind","source_hint","indicator_code_hint"}],"proxy_variables":[same],"unit","frequency","aggregation_semantics","notes","confidence"}]}
aggregation_semantics is one of mean|sum|last|first|median|weighted_mean|min|max|none|unknown.
Prefer official statistics; include real indicator codes (e.g. World Bank SL.UEM.1524.ZS) when you are confident; set confidence < 0.6 when unsure. Output JSON only."""

# Deterministic fallback dictionary: common abstract concepts → measures.
# Not exhaustive by design — it is the *fallback*, the LLM is the primary path.
FALLBACK_MEASURES: dict[str, dict] = {
    "digital_economy": {
        "preferred_measure": "数字经济核心产业增加值占GDP比重",
        "alternatives": [
            {"measure": "信息传输、软件和信息技术服务业增加值", "kind": "alternative", "source_hint": "国家统计局/城市统计年鉴", "indicator_code_hint": ""},
            {"measure": "电信业务总量", "kind": "proxy", "source_hint": "工信部/统计局", "indicator_code_hint": ""},
        ],
        "unit": "percent / CNY", "aggregation_semantics": "last", "confidence": 0.55,
    },
    "innovation": {
        "preferred_measure": "专利授权量（每万人）",
        "alternatives": [
            {"measure": "R&D经费投入强度（R&D/GDP）", "kind": "alternative", "source_hint": "科技部/统计局", "indicator_code_hint": ""},
            {"measure": "高新技术企业数量", "kind": "proxy", "source_hint": "科技部火炬中心", "indicator_code_hint": ""},
        ],
        "unit": "count per 10k / percent", "aggregation_semantics": "sum", "confidence": 0.55,
    },
    "aging": {
        "preferred_measure": "60岁及以上人口占比",
        "alternatives": [
            {"measure": "65岁及以上人口占比", "kind": "alternative", "source_hint": "统计局/UN", "indicator_code_hint": "SP.POP.65UP.TO.ZS"},
        ],
        "unit": "percent", "aggregation_semantics": "mean", "confidence": 0.6,
    },
    "environmental_regulation": {
        "preferred_measure": "节能环保支出占一般公共预算支出比重",
        "alternatives": [
            {"measure": "工业二氧化硫排放强度（排放/工业增加值）", "kind": "proxy", "source_hint": "生态环境部/城市统计年鉴", "indicator_code_hint": ""},
            {"measure": "PITI 环境监管指数", "kind": "alternative", "source_hint": "IPE（非官方）", "indicator_code_hint": ""},
        ],
        "unit": "percent", "aggregation_semantics": "mean", "confidence": 0.5,
    },
    "fiscal_pressure": {
        "preferred_measure": "土地出让收入/一般公共预算收入（土地财政依赖度）",
        "alternatives": [
            {"measure": "财政自给率（一般公共预算收入/支出）", "kind": "alternative", "source_hint": "财政厅/统计局", "indicator_code_hint": ""},
            {"measure": "人均财政缺口", "kind": "proxy", "source_hint": "统计局", "indicator_code_hint": ""},
        ],
        "unit": "ratio", "aggregation_semantics": "last", "confidence": 0.55,
    },
    "industrial_upgrading": {
        "preferred_measure": "产业结构高级化（第三产业增加值/GDP）",
        "alternatives": [
            {"measure": "第二产业占比下降幅度", "kind": "alternative", "source_hint": "统计局", "indicator_code_hint": ""},
            {"measure": "产业结构合理化（泰尔指数）", "kind": "proxy", "source_hint": "自算", "indicator_code_hint": ""},
        ],
        "unit": "ratio", "aggregation_semantics": "last", "confidence": 0.55,
    },
}


async def plan_measurements(concepts: list[dict]) -> list[VariableMeasurementPlan]:
    """concepts: [{concept, role}]. LLM primary; deterministic dictionary fallback."""
    if _llm_configured():
        try:
            client = LLMClient()
            user = "\n".join(f"- {c['concept']} (role={c.get('role', 'control')})" for c in concepts)
            raw = await client.complete_json(SYSTEM_PROMPT, user)
            plans = [VariableMeasurementPlan(**p) for p in raw.get("plans", [])]
            if plans:
                return plans
        except Exception as exc:  # noqa: BLE001
            log.warning_ctx("llm measurement planning failed; using dictionary fallback", error=str(exc)[:200])
    return _fallback_plans(concepts)


def _fallback_plans(concepts: list[dict]) -> list[VariableMeasurementPlan]:
    out: list[VariableMeasurementPlan] = []
    for c in concepts:
        concept = str(c.get("concept", "")).strip()
        key = concept.lower().replace(" ", "_").replace("-", "_")
        entry = FALLBACK_MEASURES.get(key)
        # also try Chinese-lexicon canonical names produced by the rule parser
        if entry is None:
            entry = next((v for k, v in FALLBACK_MEASURES.items() if k in concept or concept in k), None)
        if entry is None:
            out.append(
                VariableMeasurementPlan(
                    concept=concept,
                    role=str(c.get("role", "control")),
                    preferred_measure=f"[unresolved] {concept} — no deterministic measure; needs LLM or user input",
                    unit="UNKNOWN",
                    aggregation_semantics="unknown",
                    confidence=0.05,
                    notes="not in fallback dictionary; flagged for review",
                )
            )
            continue
        out.append(
            VariableMeasurementPlan(
                concept=concept,
                role=str(c.get("role", "control")),
                preferred_measure=entry["preferred_measure"],
                alternative_measures=[MeasurementCandidate(**{**a, "kind": a.get("kind", "alternative")}) for a in entry["alternatives"]],
                unit=entry["unit"],
                aggregation_semantics=entry["aggregation_semantics"],
                confidence=entry["confidence"],
                notes="deterministic fallback dictionary",
            )
        )
    return out


def _llm_configured() -> bool:
    import os

    return bool(os.environ.get("METIS_LLM_BASE_URL", "").strip()) and bool(os.environ.get("METIS_LLM_MODEL", "").strip())
