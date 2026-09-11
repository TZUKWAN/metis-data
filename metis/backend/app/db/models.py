"""SQLAlchemy models — persistence layer (P01-010). JSON columns hold pydantic schemas."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class RequirementRow(Base):
    __tablename__ = "requirements"
    requirement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    raw_request: Mapped[str] = mapped_column(Text)  # original text preserved (A1)
    data_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SearchRunRow(Base):
    __tablename__ = "search_runs"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    query_plan_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provider_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ProviderTaskRow(Base):
    __tablename__ = "provider_tasks"
    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # queued/running/done/error/timeout/cancelled
    query: Mapped[str] = mapped_column(Text, default="")
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CandidateRow(Base):
    __tablename__ = "candidates"
    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    dedup_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    data_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DownloadJobRow(Base):
    __tablename__ = "download_jobs"
    download_job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    dataset_ref: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(24), index=True)
    access_mode: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    license: Mapped[str] = mapped_column(String(128), default="UNKNOWN")
    bytes_downloaded: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ArtifactRow(Base):
    __tablename__ = "artifacts"
    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    download_job_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    dataset_ref: Mapped[str] = mapped_column(String(256))
    raw_path: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_format: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    license: Mapped[str] = mapped_column(String(128), default="UNKNOWN")
    status: Mapped[str] = mapped_column(String(24), default="REGISTERED")
    profile_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BuildRow(Base):
    __tablename__ = "builds"
    build_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requirement_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), index=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    checkpoints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BuildOperationRow(Base):
    """Transformation provenance (PRD §27)."""
    __tablename__ = "build_operations"
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    build_id: Mapped[str] = mapped_column(String(64), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    operation_type: Mapped[str] = mapped_column(String(48))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    input_artifacts: Mapped[list] = mapped_column(JSON, default=list)
    output_artifacts: Mapped[list] = mapped_column(JSON, default=list)
    row_count_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    code_version: Mapped[str] = mapped_column(String(32), default="v1")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FieldLineageRow(Base):
    __tablename__ = "field_lineage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    build_id: Mapped[str] = mapped_column(String(64), index=True)
    final_field: Mapped[str] = mapped_column(String(128), index=True)
    lineage_json: Mapped[dict] = mapped_column(JSON)  # chain to source field/raw/provider/URL/DOI


class ValidationRow(Base):
    __tablename__ = "validations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    build_id: Mapped[str] = mapped_column(String(64), index=True)
    code: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    affected_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VariableSemanticRow(Base):
    __tablename__ = "variable_semantics"
    semantic_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    build_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    canonical_name: Mapped[str] = mapped_column(String(128), index=True)
    original_name: Mapped[str] = mapped_column(String(128))
    data_json: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)


class CredentialRow(Base):
    __tablename__ = "credentials"
    credential_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="password")
    account_label: Mapped[str] = mapped_column(String(256), default="")
    vault_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="STORED")
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AccountRow(Base):
    __tablename__ = "accounts"
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), default="NONE")
    auto_register_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_verified_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    registration_result: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SessionRow(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    vault_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="VALID")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class IdentityRow(Base):
    __tablename__ = "data_identity"
    identity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data_json: Mapped[dict] = mapped_column(JSON)


class BrowserEventRow(Base):
    """Persisted browser action events (event stream survives restart, A3 search history etc.)."""
    __tablename__ = "browser_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    kind: Mapped[str] = mapped_column(String(40))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class UiEventRow(Base):
    """Global UI event log (agent tool events / warnings / interventions)."""
    __tablename__ = "ui_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderHealthRow(Base):
    __tablename__ = "provider_health"
    provider_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="unknown")  # healthy|degraded|down|unknown
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    circuit_open: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CapabilityAuditRow(Base):
    """Evidence trail for integration level claims (A2: 不虚报)."""
    __tablename__ = "capability_audits"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    integration_level: Mapped[int] = mapped_column(Integer, default=0)
    target_level: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[str] = mapped_column(String(40))


class AccessJobRow(Base):
    __tablename__ = "access_jobs"
    access_job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), default="")
    download_job_id: Mapped[str] = mapped_column(String(64), default="")
    state: Mapped[str] = mapped_column(String(40), index=True)
    data_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
