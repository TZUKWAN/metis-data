"""Pydantic domain schemas (P01-001 .. P01-008). JSON-serializable; persisted as JSON columns."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


# ---------------- P01-001 DataRequirement ----------------
class VariableRequest(BaseModel):
    outcomes: list[str] = []
    exposures: list[str] = []
    mediators: list[str] = []
    moderators: list[str] = []
    controls: list[str] = []
    identifiers: list[str] = []
    optional: list[str] = []

    def all_named(self) -> list[str]:
        return self.outcomes + self.exposures + self.mediators + self.moderators + self.controls + self.identifiers + self.optional


class DataRequirement(BaseModel):
    requirement_id: str = Field(default_factory=lambda: new_id("req"))
    goal: str = ""
    research_question: str = ""
    raw_request: str = ""  # original user text, never mutated
    data_task_type: str = "panel"  # panel | cross_section | time_series | ml_training | ...
    unit_of_analysis: str = ""  # country | individual | province | firm | unknown
    population: str = ""
    geography: list[str] = []
    time_range: tuple[int, int] | None = None
    frequency: str = "annual"  # annual | quarterly | monthly | daily | unknown

    variables: VariableRequest = Field(default_factory=VariableRequest)
    preferred_sources: list[str] = []
    excluded_sources: list[str] = []
    trust_requirement: str = ""  # official | international_org | any
    license_requirement: str = ""  # open | any
    access_tolerance: str = "public_first"  # public_only | public_first | account_ok
    format_preferences: list[str] = []
    max_missing_rate: float | None = None
    notes: str = ""
    assumptions: list[str] = []  # every important inference shown explicitly (A1)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ---------------- P01-002 Provider ----------------
class ProviderCapabilities(BaseModel):
    discovery_api: bool = False
    discovery_http: bool = False
    discovery_browser: bool = False
    metadata_api: bool = False
    preview: bool = False
    anonymous_download: bool = False
    authenticated_download: bool = False
    registration: bool = False
    oauth: bool = False
    api_key: bool = False
    restricted_data: bool = False


class ProviderRecord(BaseModel):
    provider_id: str
    name: str
    category: str  # international_org | us_gov | europe | cn_gov | research_repo | ai_community | catalog
    country_or_region: str
    homepage: str
    trust_class: str  # official | international | academic | community | commercial
    status: str = "active"  # active | degraded | inactive
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    auth_modes: list[str] = []  # none | api_key | oauth | form_login
    formats: list[str] = []
    licenses: list[str] = []
    rate_limit_notes: str = ""
    browser_required_for: list[str] = []
    terms_url: str = ""
    privacy_url: str = ""
    adapter_version: str = ""
    integration_level: int = 0
    last_verified_at: str | None = None
    blocking_reason: str | None = None  # evidence when a target level is not reached


# ---------------- P01-003 DatasetCandidate ----------------
class AcquisitionSource(BaseModel):
    """One concrete way to obtain the dataset (mirrors preserved through dedup)."""
    provider_id: str
    source_url: str
    source_ref: str = ""
    direct_file_url: str | None = None
    file_format: str | None = None
    size_hint: str | None = None


class TimeCoverage(BaseModel):
    start: str | None = None
    end: str | None = None
    note: str = ""


class RecommendationBreakdown(BaseModel):
    topic: float = 0.0
    variables: float = 0.0
    unit: float = 0.0
    time: float = 0.0
    geography: float = 0.0
    source_trust: float = 0.0
    doi_publication: float = 0.0
    license: float = 0.0
    access: float = 0.0
    documentation: float = 0.0


class DatasetCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("cand"))
    title: str = ""
    description: str = ""
    provider_id: str = ""
    publisher: str = ""
    authors: list[str] = []
    doi: str | None = None  # normalized (https://doi.org/10.xxxx form)
    version: str | None = None
    license: str = "UNKNOWN"  # UNKNOWN never treated as open (A5)
    access_mode: str = "UNKNOWN"
    requires_login: bool = False
    restricted: bool = False
    time_coverage: TimeCoverage = Field(default_factory=TimeCoverage)
    geography: list[str] = []
    unit_of_analysis: str = "UNKNOWN"
    variable_hints: list[str] = []
    files: list[AcquisitionSource] = []
    sources: list[AcquisitionSource] = []  # all mirrors kept after dedup
    raw_metadata_ref: str | None = None
    dedup_group_id: str | None = None
    is_primary: bool = True
    recommendation: RecommendationBreakdown = Field(default_factory=RecommendationBreakdown)
    score: float = 0.0
    reasons: list[str] = []
    limitations: list[str] = []
    unknowns: list[str] = []
    selected: bool = False
    created_at: datetime = Field(default_factory=utcnow)


# ---------------- P01-004 DatasetArtifact ----------------
class DatasetArtifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: new_id("art"))
    download_job_id: str = ""
    provider_id: str = ""
    dataset_ref: str = ""
    dataset_title: str = ""
    version: str | None = None
    raw_path: str = ""  # relative to workspace raw root
    checksum_sha256: str = ""
    size_bytes: int = 0
    file_format: str = "UNKNOWN"
    license: str = "UNKNOWN"
    source_url: str = ""
    profile_id: str | None = None
    status: str = "REGISTERED"  # REGISTERED | PROFILED | FAILED
    created_at: datetime = Field(default_factory=utcnow)


# ---------------- P01-005 VariableSemantic ----------------
class VariableSemantic(BaseModel):
    semantic_id: str = Field(default_factory=lambda: new_id("vs"))
    build_id: str | None = None
    artifact_id: str | None = None
    canonical_name: str = ""
    original_name: str = ""
    display_name: str = ""
    definition: str = ""
    unit: str = "UNKNOWN"  # percent | fraction | usd | local_currency | count | index | ...
    scale: str = "UNKNOWN"  # current_price | constant_price | unknown
    coding: dict[str, Any] | None = None  # category mapping e.g. {"M":"male","F":"female"}
    frequency: str = "UNKNOWN"
    geography_level: str = "UNKNOWN"  # country | province | prefecture | individual
    population: str = "UNKNOWN"  # e.g. youth 15-24
    price_basis: str = "UNKNOWN"  # nominal | real | unknown
    currency: str = "UNKNOWN"
    base_year: int | None = None
    source_dataset: str = ""
    source_field: str = ""
    confidence: float = 0.0
    notes: str = ""


# ---------------- P01-006 DownloadJob ----------------
class DownloadJob(BaseModel):
    download_job_id: str = Field(default_factory=lambda: new_id("dl"))
    provider_id: str = ""
    dataset_ref: str = ""
    dataset_title: str = ""
    source_url: str = ""
    version: str | None = None
    access_mode: str = "UNKNOWN"
    license: str = "UNKNOWN"
    expected_files: list[str] = []
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str = "CREATED"
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    error_code: str | None = None
    files: list[dict[str, Any]] = []  # [{path, sha256, size, format}]
    created_at: datetime = Field(default_factory=utcnow)


# ---------------- P01-007 Build ----------------
class BuildInputRef(BaseModel):
    artifact_id: str
    alias: str = ""
    filter: dict[str, str] = {}  # column equality filters (e.g. {"sex": "T"}) applied at load


class BuildPlanStep(BaseModel):
    step_id: str
    kind: str  # semantic_mapping | entity_resolution | time_alignment | unit_conversion | transform | join | missing_policy | derived | validation | export
    params: dict[str, Any] = {}
    warnings: list[str] = []


class BuildConfig(BaseModel):
    build_id: str = Field(default_factory=lambda: new_id("build"))
    title: str = ""
    requirement_id: str | None = None
    inputs: list[BuildInputRef] = []
    target_unit: str = ""  # country | province | prefecture
    keys: list[str] = []  # e.g. ["iso3","year"]
    time_frequency: str = "annual"
    missing_policy: str = "none"  # none is default (A28)
    missing_policy_params: dict[str, Any] = {}
    aggregations: list[dict[str, Any]] = []  # [{field, method, weight_field?}] - P19
    derived_variables: list[dict[str, Any]] = []
    validation_profile: str = "default"
    exports: list[str] = ["parquet", "csv", "xlsx"]
    allow_mm_join: bool = False  # m:m blocked by default (A26)
    plan: list[BuildPlanStep] = []
    plan_snapshot: dict[str, Any] = {}  # original agent BuildPlan (dict) + review points recorded at planning time
    status: str = "BUILD_CREATED"
    stage_checkpoints: dict[str, Any] = {}
    created_at: datetime = Field(default_factory=utcnow)


# ---------------- P01-008 CredentialRef ----------------
class CredentialRef(BaseModel):
    """DB stores ONLY this metadata. Secret material lives in the OS vault."""
    credential_id: str = Field(default_factory=lambda: new_id("cred"))
    provider_id: str = ""
    kind: str = "password"  # password | api_key | oauth | session
    account_label: str = ""  # email/username identifier (not the secret)
    vault_key: str = ""  # lookup key in vault
    session_ref: str | None = None
    status: str = "STORED"
    created_at: datetime = Field(default_factory=utcnow)
    last_verified_at: str | None = None


class StoredSession(BaseModel):
    session_id: str = Field(default_factory=lambda: new_id("sess"))
    provider_id: str = ""
    vault_key: str = ""  # serialized cookies/storage_state live encrypted in vault
    status: str = "VALID"  # VALID | EXPIRED | REVOKED
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None


# ---------------- Phase H: build planning request (agent → builds) ----------------
class BuildPlanInputRef(BaseModel):
    """One planned input: a registered artifact plus optional column equality filters."""

    artifact_id: str
    filter: dict[str, Any] = {}  # column equality filters applied at load (e.g. {"sex": "T"})


class BuildPlanRequest(BaseModel):
    """Request to plan a build from a structured requirement + selected assets.

    requirement is the raw requirement JSON (DataRequirement-shaped dict); inputs
    reference already-registered artifacts. llm_enabled=False forces the
    deterministic planner (plan_build_sync) — the default for no-LLM environments.
    """

    title: str = ""
    requirement: dict[str, Any] = {}
    inputs: list[BuildPlanInputRef] = []
    llm_enabled: bool = False
