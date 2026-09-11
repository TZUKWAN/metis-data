"""Strict agent schemas (P01-004). Every LLM output must validate here before entering downstream.

非法输出不能进入下游：all planners MUST return instances of these models or raise AgentError.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# LLM 输出一律禁止额外字段，防止自由文本混入结构化数据
_STRICT = ConfigDict(extra="forbid")


class VariableConcept(BaseModel):
    model_config = _STRICT
    concept: str = Field(min_length=1)
    role: Literal["outcome", "exposure", "mediator", "moderator", "control", "identifier"] = "control"
    description: str = ""


class DataRequirementPlan(BaseModel):
    model_config = _STRICT
    research_goal: str = Field(min_length=1)
    unit_of_analysis: str = "unknown"
    geography: list[str] = []
    time_range: dict[str, int | None] = {}
    frequency: str = "unknown"
    variables: list[VariableConcept] = []
    constraints: dict[str, Any] = {}
    preferred_sources: list[str] = []
    deliverables: list[str] = []
    assumptions: list[str] = []
    questions: list[str] = []  # unclear items shown to user (P01-012)

    @field_validator("unit_of_analysis")
    @classmethod
    def _unit(cls, v: str) -> str:
        allowed = {"country", "province", "prefecture", "city", "individual", "firm", "household", "entity", "year", "unknown"}
        v = v.strip().lower() or "unknown"
        return v if v in allowed else "unknown"

    @field_validator("frequency")
    @classmethod
    def _freq(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in {"annual", "quarterly", "monthly", "daily", "unknown"} else "unknown"


class MeasurementCandidate(BaseModel):
    model_config = _STRICT
    measure: str = Field(min_length=1)
    kind: Literal["preferred", "alternative", "proxy"] = "alternative"
    source_hint: str = ""
    indicator_code_hint: str = ""  # e.g. WB "SL.UEM.1524.ZS"


class VariableMeasurementPlan(BaseModel):
    model_config = _STRICT
    concept: str = Field(min_length=1)
    role: str = "control"
    preferred_measure: str = Field(min_length=1)
    alternative_measures: list[MeasurementCandidate] = []
    proxy_variables: list[MeasurementCandidate] = []
    unit: str = "UNKNOWN"
    frequency: str = "unknown"
    aggregation_semantics: Literal["mean", "sum", "last", "first", "median", "weighted_mean", "min", "max", "none", "unknown"] = "unknown"
    notes: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SourcePlan(BaseModel):
    model_config = _STRICT
    provider_priorities: list[str] = []
    provider_queries: dict[str, list[str]] = {}
    search_languages: list[str] = []
    fallbacks: list[str] = []
    rationale: list[str] = []


class SearchQueryPlan(BaseModel):
    model_config = _STRICT
    provider_id: str = Field(min_length=1)
    queries: list[str] = Field(min_length=1)
    indicator_code_hints: list[str] = []


class CandidateAnalysis(BaseModel):
    model_config = _STRICT
    candidate_id: str = ""
    relevance: Literal["high", "medium", "low", "unknown"] = "unknown"
    variable_coverage: list[str] = []
    limitations: list[str] = []
    license_concern: str = ""
    reasons: list[str] = []


class ReviewPoint(BaseModel):
    model_config = _STRICT
    severity: Literal["info", "warning", "blocking"] = "warning"
    topic: str = Field(min_length=1)
    message: str = Field(min_length=1)
    remediation: str = ""


class CriticReview(BaseModel):
    model_config = _STRICT
    ok: bool = True
    review_points: list[ReviewPoint] = []


class FieldMapping(BaseModel):
    model_config = _STRICT
    source_artifact_id: str
    source_field: str
    target_field: str


class JoinPlan(BaseModel):
    model_config = _STRICT
    left_input: str
    right_input: str
    keys: list[str] = Field(min_length=1)
    expected_cardinality: Literal["1:1", "1:m", "m:1", "m:m", "unknown"] = "unknown"
    join_type: Literal["inner", "left", "right", "outer"] = "inner"
    coverage_requirement: float = Field(default=0.8, ge=0.0, le=1.0)


class AggregationPlan(BaseModel):
    model_config = _STRICT
    field: str
    method: Literal["mean", "sum", "last", "first", "median", "weighted_mean", "min", "max", "none"]
    weight_field: str | None = None
    rationale: str = ""


class BuildPlan(BaseModel):
    model_config = _STRICT
    target_schema: list[str] = []
    inputs: list[str] = []
    input_roles: dict[str, str] = {}
    field_mappings: list[FieldMapping] = []
    entity_strategy: str = "country"
    time_strategy: str = "annual"
    unit_conversions: list[dict[str, Any]] = []
    aggregations: list[AggregationPlan] = []
    joins: list[JoinPlan] = []
    missing_policy: list[dict[str, Any]] = []
    derived_variables: list[dict[str, Any]] = []
    validations: list[str] = []
    review_points: list[ReviewPoint] = []
