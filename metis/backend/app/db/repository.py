"""Repository layer (P01-010): the only DB access path for business modules."""
from __future__ import annotations

import json
from typing import Any, TypeVar

from sqlalchemy import select

from app.db.models import (
    AccessJobRow,
    AccountRow,
    ArtifactRow,
    BrowserEventRow,
    BuildOperationRow,
    BuildRow,
    CandidateRow,
    CapabilityAuditRow,
    CredentialRow,
    DownloadJobRow,
    FieldLineageRow,
    ProjectRow,
    ProviderHealthRow,
    ProviderTaskRow,
    RequirementRow,
    SearchRunRow,
    SessionRow,
    TaskRow,
    UiEventRow,
    ValidationRow,
    VariableSemanticRow,
)
from app.db.session import new_session
from app.domain.enums import BUILD_FLOW, SEARCH_RUN_FLOW, assert_transition
from app.domain.schemas import new_id, utcnow

T = TypeVar("T")


def _to_json(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return json.loads(model.model_dump_json())
    return model


def _task_to_dict(row: TaskRow) -> dict:
    return {
        "task_id": row.task_id,
        "project_id": row.project_id,
        "kind": row.kind,
        "ref_id": row.ref_id,
        "status": row.status,
        "data": row.data_json,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


class Repository:
    """Coarse-grained, typed persistence API. Transactions are short-lived."""

    # ---- requirements ----
    def save_requirement(self, data) -> str:
        payload = data if isinstance(data, dict) else _to_json(data)
        with new_session() as s:
            row = s.get(RequirementRow, payload["requirement_id"])
            if row is None:
                row = RequirementRow(requirement_id=payload["requirement_id"], raw_request=payload.get("raw_request", ""), data_json=payload)
                s.add(row)
            else:
                row.data_json = payload
                row.raw_request = payload.get("raw_request", "")
            s.commit()
            return payload["requirement_id"]

    def get_requirement(self, requirement_id: str):
        with new_session() as s:
            row = s.get(RequirementRow, requirement_id)
            return row.data_json if row else None

    def list_requirements(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(RequirementRow).order_by(RequirementRow.created_at.desc())).all()
            return [r.data_json for r in rows]

    # ---- search runs ----
    def save_search_run(self, run_id: str, requirement_id: str, status: str, query_plan: dict | None = None, provider_ids: list | None = None) -> None:
        with new_session() as s:
            row = s.get(SearchRunRow, run_id)
            if row is None:
                row = SearchRunRow(run_id=run_id, requirement_id=requirement_id, status=status)
                s.add(row)
            row.status = status
            if query_plan is not None:
                row.query_plan_json = query_plan
            if provider_ids is not None:
                row.provider_ids = provider_ids
            s.commit()

    def get_search_run(self, run_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(SearchRunRow, run_id)
            if row is None:
                return None
            return {
                "run_id": row.run_id,
                "requirement_id": row.requirement_id,
                "status": row.status,
                "query_plan": row.query_plan_json,
                "provider_ids": row.provider_ids,
                "created_at": row.created_at.isoformat(),
            }

    def transition_search_run(self, run_id: str, target: str) -> None:
        with new_session() as s:
            row = s.get(SearchRunRow, run_id)
            assert row is not None, f"search run {run_id} not found"
            assert_transition(SEARCH_RUN_FLOW, row.status, target, "search run")
            row.status = target
            s.commit()

    def list_search_runs(self, limit: int = 50) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(SearchRunRow).order_by(SearchRunRow.created_at.desc()).limit(limit)).all()
            return [
                {"run_id": r.run_id, "requirement_id": r.requirement_id, "status": r.status, "created_at": r.created_at.isoformat()}
                for r in rows
            ]

    # ---- provider tasks ----
    def upsert_provider_task(self, task_id: str, run_id: str, provider_id: str, status: str, query: str = "", **kw: Any) -> None:
        with new_session() as s:
            row = s.get(ProviderTaskRow, task_id)
            if row is None:
                row = ProviderTaskRow(task_id=task_id, run_id=run_id, provider_id=provider_id, status=status, query=query)
                s.add(row)
            row.status = status
            for k, v in kw.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if "started_at" in kw and kw["started_at"] is True:
                row.started_at = utcnow()
            s.commit()

    def finish_provider_task(self, task_id: str, status: str, error_code: str | None = None, error_message: str | None = None, result_count: int | None = None) -> None:
        with new_session() as s:
            row = s.get(ProviderTaskRow, task_id)
            assert row is not None
            row.status = status
            row.finished_at = utcnow()
            if error_code:
                row.error_code = error_code
            if error_message:
                row.error_message = error_message
            if result_count is not None:
                row.result_count = result_count
            s.commit()

    def list_provider_tasks(self, run_id: str) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(ProviderTaskRow).where(ProviderTaskRow.run_id == run_id)).all()
            return [
                {
                    "task_id": r.task_id,
                    "provider_id": r.provider_id,
                    "status": r.status,
                    "result_count": r.result_count,
                    "error_code": r.error_code,
                    "error_message": r.error_message,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in rows
            ]

    def incomplete_provider_tasks(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(ProviderTaskRow).where(ProviderTaskRow.status.in_(["queued", "running"]))).all()
            return [{"task_id": r.task_id, "run_id": r.run_id, "provider_id": r.provider_id} for r in rows]

    # ---- candidates ----
    def save_candidate(self, run_id: str, candidate) -> str:
        payload = candidate if isinstance(candidate, dict) else _to_json(candidate)
        with new_session() as s:
            row = s.get(CandidateRow, payload["candidate_id"])
            if row is None:
                row = CandidateRow(
                    candidate_id=payload["candidate_id"],
                    run_id=run_id,
                    provider_id=payload.get("provider_id", ""),
                    doi=payload.get("doi"),
                    dedup_group_id=payload.get("dedup_group_id"),
                    title=payload.get("title", ""),
                    score=payload.get("score", 0.0),
                    selected=bool(payload.get("selected", False)),
                )
                s.add(row)
            row.data_json = payload
            row.doi = payload.get("doi")
            row.dedup_group_id = payload.get("dedup_group_id")
            row.title = payload.get("title", "")
            row.score = payload.get("score", 0.0)
            row.selected = bool(payload.get("selected", False))
            s.commit()
            return payload["candidate_id"]

    def get_candidate(self, candidate_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(CandidateRow, candidate_id)
            return row.data_json if row else None

    def list_candidates(self, run_id: str, dedup_only: bool = True) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(CandidateRow).where(CandidateRow.run_id == run_id).order_by(CandidateRow.score.desc())).all()
            out = [r.data_json for r in rows]
        if dedup_only:
            out = [c for c in out if c.get("is_primary", True)]
        return out

    def set_candidate_selected(self, candidate_id: str, selected: bool) -> None:
        with new_session() as s:
            row = s.get(CandidateRow, candidate_id)
            assert row is not None
            row.selected = selected
            data = dict(row.data_json)
            data["selected"] = selected
            row.data_json = data
            s.commit()

    # ---- download jobs ----
    def save_download_job(self, job) -> str:
        payload = job if isinstance(job, dict) else _to_json(job)
        with new_session() as s:
            row = s.get(DownloadJobRow, payload["download_job_id"])
            if row is None:
                row = DownloadJobRow(download_job_id=payload["download_job_id"], provider_id=payload.get("provider_id", ""), dataset_ref=payload.get("dataset_ref", ""), status=payload.get("status", "CREATED"))
                s.add(row)
            row.status = payload.get("status", row.status)
            row.access_mode = payload.get("access_mode", "UNKNOWN")
            row.license = payload.get("license", "UNKNOWN")
            row.bytes_downloaded = payload.get("bytes_downloaded", 0)
            row.total_bytes = payload.get("total_bytes")
            row.error_code = payload.get("error_code")
            row.data_json = payload
            s.commit()
            return payload["download_job_id"]

    def get_download_job(self, job_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(DownloadJobRow, job_id)
            return row.data_json if row else None

    def list_download_jobs(self, limit: int = 100) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(DownloadJobRow).order_by(DownloadJobRow.created_at.desc()).limit(limit)).all()
            return [r.data_json for r in rows]

    def unfinished_download_jobs(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(DownloadJobRow).where(DownloadJobRow.status.in_(["CREATED", "RUNNING", "VERIFYING"]))).all()
            return [r.data_json for r in rows]

    # ---- artifacts ----
    def save_artifact(self, artifact) -> str:
        payload = _to_json(artifact)
        with new_session() as s:
            row = s.get(ArtifactRow, payload["artifact_id"])
            if row is None:
                row = ArtifactRow(
                    artifact_id=payload["artifact_id"],
                    download_job_id=payload.get("download_job_id", ""),
                    provider_id=payload.get("provider_id", ""),
                    dataset_ref=payload.get("dataset_ref", ""),
                    raw_path=payload.get("raw_path", ""),
                    checksum_sha256=payload.get("checksum_sha256", ""),
                    size_bytes=payload.get("size_bytes", 0),
                    file_format=payload.get("file_format", "UNKNOWN"),
                    license=payload.get("license", "UNKNOWN"),
                    status=payload.get("status", "REGISTERED"),
                )
                s.add(row)
            for k in ("raw_path", "checksum_sha256", "size_bytes", "file_format", "license", "status", "profile_json"):
                if k in payload:
                    setattr(row, k, payload[k])
            row.data_json = payload
            s.commit()
            return payload["artifact_id"]

    def get_artifact(self, artifact_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(ArtifactRow, artifact_id)
            if row is None:
                return None
            d = dict(row.data_json)
            d.setdefault("artifact_id", row.artifact_id)
            d["profile"] = row.profile_json
            d["status"] = row.status
            return d

    def list_artifacts(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(ArtifactRow).order_by(ArtifactRow.created_at.desc())).all()
            return [r.data_json for r in rows]

    # ---- builds ----
    def save_build(self, config) -> str:
        payload = _to_json(config)
        with new_session() as s:
            row = s.get(BuildRow, payload["build_id"])
            if row is None:
                row = BuildRow(build_id=payload["build_id"], requirement_id=payload.get("requirement_id"), title=payload.get("title", ""), status=payload.get("status", "BUILD_CREATED"))
                s.add(row)
            row.status = payload.get("status", row.status)
            row.config_json = payload
            row.checkpoints_json = payload.get("stage_checkpoints", {})
            s.commit()
            return payload["build_id"]

    def get_build(self, build_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(BuildRow, build_id)
            return row.config_json if row else None

    def list_builds(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(BuildRow).order_by(BuildRow.created_at.desc())).all()
            return [r.config_json for r in rows]

    def transition_build(self, build_id: str, target: str) -> None:
        with new_session() as s:
            row = s.get(BuildRow, build_id)
            assert row is not None
            assert_transition(BUILD_FLOW, row.status, target, "build")
            row.status = target
            cfg = dict(row.config_json)
            cfg["status"] = target
            row.config_json = cfg
            s.commit()

    def set_build_checkpoint(self, build_id: str, stage: str, checkpoint: dict) -> None:
        with new_session() as s:
            row = s.get(BuildRow, build_id)
            assert row is not None
            cps = dict(row.checkpoints_json or {})
            cps[stage] = checkpoint
            row.checkpoints_json = cps
            cfg = dict(row.config_json)
            cfg["stage_checkpoints"] = cps
            row.config_json = cfg
            s.commit()

    def running_builds(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(BuildRow).where(BuildRow.status.notin_(["COMPLETE", "FAILED", "CANCELLED"]))).all()
            return [r.config_json for r in rows]

    # ---- build operations / lineage / validation ----
    def add_build_operation(self, **kw: Any) -> str:
        with new_session() as s:
            row = BuildOperationRow(**kw)
            s.add(row)
            s.commit()
            return row.operation_id

    def list_build_operations(self, build_id: str) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(BuildOperationRow).where(BuildOperationRow.build_id == build_id).order_by(BuildOperationRow.seq)).all()
            return [
                {
                    "operation_id": r.operation_id,
                    "seq": r.seq,
                    "operation_type": r.operation_type,
                    "parameters": r.parameters,
                    "input_artifacts": r.input_artifacts,
                    "output_artifacts": r.output_artifacts,
                    "row_count_before": r.row_count_before,
                    "row_count_after": r.row_count_after,
                    "column_count_before": r.column_count_before,
                    "column_count_after": r.column_count_after,
                    "warnings": r.warnings,
                    "code_version": r.code_version,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in rows
            ]

    def add_field_lineage(self, build_id: str, final_field: str, lineage: dict) -> None:
        with new_session() as s:
            s.add(FieldLineageRow(build_id=build_id, final_field=final_field, lineage_json=lineage))
            s.commit()

    def list_field_lineage(self, build_id: str) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(FieldLineageRow).where(FieldLineageRow.build_id == build_id)).all()
            return [{"final_field": r.final_field, "lineage": r.lineage_json} for r in rows]

    def add_validation(self, **kw: Any) -> None:
        if "details" in kw:
            kw["details_json"] = kw.pop("details")
        with new_session() as s:
            s.add(ValidationRow(**kw))
            s.commit()

    def list_validations(self, build_id: str) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(ValidationRow).where(ValidationRow.build_id == build_id)).all()
            return [
                {
                    "code": r.code,
                    "severity": r.severity,
                    "message": r.message,
                    "field": r.field,
                    "affected_rows": r.affected_rows,
                    "remediation": r.remediation,
                    "details": r.details_json,
                }
                for r in rows
            ]

    # ---- variable semantics ----
    def save_variable_semantic(self, vs) -> str:
        payload = _to_json(vs)
        with new_session() as s:
            row = s.get(VariableSemanticRow, payload["semantic_id"])
            if row is None:
                row = VariableSemanticRow(
                    semantic_id=payload["semantic_id"],
                    build_id=payload.get("build_id"),
                    artifact_id=payload.get("artifact_id"),
                    canonical_name=payload.get("canonical_name", ""),
                    original_name=payload.get("original_name", ""),
                    confidence=payload.get("confidence", 0.0),
                )
                s.add(row)
            row.data_json = payload
            row.canonical_name = payload.get("canonical_name", "")
            row.confidence = payload.get("confidence", 0.0)
            s.commit()
            return payload["semantic_id"]

    def list_variable_semantics(self, build_id: str | None = None) -> list[dict]:
        stmt = select(VariableSemanticRow)
        if build_id:
            stmt = stmt.where(VariableSemanticRow.build_id == build_id)
        with new_session() as s:
            rows = s.scalars(stmt).all()
            return [r.data_json for r in rows]

    # ---- accounts / credentials / sessions ----
    def upsert_account(self, account_id: str, provider_id: str, **kw: Any) -> None:
        with new_session() as s:
            row = s.get(AccountRow, account_id)
            if row is None:
                row = AccountRow(account_id=account_id, provider_id=provider_id, status=kw.get("status", "NONE"))
                s.add(row)
            for k, v in kw.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            if "data_json" in kw and isinstance(kw["data_json"], dict):
                merged = dict(row.data_json or {})
                merged.update(kw["data_json"])
                row.data_json = merged
            s.commit()

    def get_account(self, account_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(AccountRow, account_id)
            if row is None:
                return None
            return {
                "account_id": row.account_id,
                "provider_id": row.provider_id,
                "status": row.status,
                "auto_register_enabled": row.auto_register_enabled,
                "registration_result": row.registration_result,
                "last_verified_at": row.last_verified_at,
                "data": row.data_json,
            }

    def list_accounts(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(AccountRow)).all()
            return [
                {
                    "account_id": r.account_id,
                    "provider_id": r.provider_id,
                    "status": r.status,
                    "auto_register_enabled": r.auto_register_enabled,
                    "registration_result": r.registration_result,
                    "last_verified_at": r.last_verified_at,
                    "data": r.data_json,
                }
                for r in rows
            ]

    def add_credential(self, credential_id: str, provider_id: str, kind: str, account_label: str, vault_key: str, status: str = "STORED", extra: dict | None = None) -> None:
        with new_session() as s:
            row = s.get(CredentialRow, credential_id)
            if row is None:
                row = CredentialRow(credential_id=credential_id, provider_id=provider_id, kind=kind, account_label=account_label, vault_key=vault_key, status=status)
                s.add(row)
            row.status = status
            if extra:
                row.data_json = extra
            s.commit()

    def list_credentials(self, provider_id: str | None = None) -> list[dict]:
        stmt = select(CredentialRow)
        if provider_id:
            stmt = stmt.where(CredentialRow.provider_id == provider_id)
        with new_session() as s:
            rows = s.scalars(stmt).all()
            return [
                {"credential_id": r.credential_id, "provider_id": r.provider_id, "kind": r.kind, "account_label": r.account_label, "vault_key": r.vault_key, "status": r.status}
                for r in rows
            ]

    def delete_credential(self, credential_id: str) -> None:
        with new_session() as s:
            row = s.get(CredentialRow, credential_id)
            if row is not None:
                s.delete(row)
                s.commit()

    def upsert_session(self, session_id: str, provider_id: str, vault_key: str, status: str = "VALID", account_id: str | None = None, expires_at=None) -> None:
        with new_session() as s:
            row = s.get(SessionRow, session_id)
            if row is None:
                row = SessionRow(session_id=session_id, provider_id=provider_id, vault_key=vault_key, status=status, account_id=account_id, expires_at=expires_at)
                s.add(row)
            else:
                row.status = status
                if expires_at is not None:
                    row.expires_at = expires_at
            s.commit()

    def get_session(self, session_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(SessionRow, session_id)
            if row is None:
                return None
            return {
                "session_id": row.session_id,
                "provider_id": row.provider_id,
                "account_id": row.account_id,
                "vault_key": row.vault_key,
                "status": row.status,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            }

    def list_sessions(self, provider_id: str | None = None) -> list[dict]:
        stmt = select(SessionRow)
        if provider_id:
            stmt = stmt.where(SessionRow.provider_id == provider_id)
        with new_session() as s:
            rows = s.scalars(stmt).all()
            return [{"session_id": r.session_id, "provider_id": r.provider_id, "status": r.status, "vault_key": r.vault_key} for r in rows]

    # ---- events ----
    def add_ui_event(self, kind: str, severity: str = "INFO", task_id: str | None = None, provider_id: str | None = None, payload: dict | None = None) -> int:
        with new_session() as s:
            row = UiEventRow(kind=kind, severity=severity, task_id=task_id, provider_id=provider_id, payload_json=payload or {})
            s.add(row)
            s.commit()
            return row.id

    def list_ui_events(self, limit: int = 200) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(UiEventRow).order_by(UiEventRow.id.desc()).limit(limit)).all()
            return [
                {
                    "id": r.id,
                    "ts": r.ts.isoformat(),
                    "kind": r.kind,
                    "severity": r.severity,
                    "task_id": r.task_id,
                    "provider_id": r.provider_id,
                    "payload": r.payload_json,
                }
                for r in reversed(rows)
            ]

    def add_browser_event(self, session_id: str, seq: int, kind: str, payload: dict) -> None:
        with new_session() as s:
            s.add(BrowserEventRow(session_id=session_id, seq=seq, kind=kind, payload_json=payload))
            s.commit()

    def list_browser_events(self, session_id: str | None = None, limit: int = 500) -> list[dict]:
        stmt = select(BrowserEventRow).order_by(BrowserEventRow.id.desc()).limit(limit)
        if session_id:
            stmt = stmt.where(BrowserEventRow.session_id == session_id)
        with new_session() as s:
            rows = s.scalars(stmt).all()
            return [
                {"id": r.id, "session_id": r.session_id, "seq": r.seq, "ts": r.ts.isoformat(), "kind": r.kind, "payload": r.payload_json}
                for r in reversed(rows)
            ]

    # ---- access jobs ----
    def upsert_access_job(self, payload: dict) -> None:
        with new_session() as s:
            row = s.get(AccessJobRow, payload["access_job_id"])
            if row is None:
                row = AccessJobRow(access_job_id=payload["access_job_id"], provider_id=payload.get("provider_id", ""), state=payload.get("state", ""), data_json=payload)
                s.add(row)
            row.state = payload.get("state", row.state)
            row.data_json = payload
            s.commit()

    def get_access_job(self, access_job_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(AccessJobRow, access_job_id)
            return row.data_json if row else None

    def list_access_jobs(self, provider_id: str | None = None, limit: int = 50) -> list[dict]:
        stmt = select(AccessJobRow).order_by(AccessJobRow.created_at.desc()).limit(limit)
        if provider_id:
            stmt = stmt.where(AccessJobRow.provider_id == provider_id)
        with new_session() as s:
            rows = s.scalars(stmt).all()
            return [r.data_json for r in rows]

    # ---- provider health / audits ----
    def upsert_provider_health(self, provider_id: str, status: str, consecutive_failures: int = 0, circuit_open: bool = False, last_error: str | None = None) -> None:
        with new_session() as s:
            row = s.get(ProviderHealthRow, provider_id)
            if row is None:
                row = ProviderHealthRow(provider_id=provider_id, status=status)
                s.add(row)
            row.status = status
            row.consecutive_failures = consecutive_failures
            row.circuit_open = circuit_open
            row.last_checked_at = utcnow()
            row.last_error = last_error
            s.commit()

    def get_provider_health(self, provider_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(ProviderHealthRow, provider_id)
            if row is None:
                return None
            return {
                "provider_id": row.provider_id,
                "status": row.status,
                "consecutive_failures": row.consecutive_failures,
                "circuit_open": row.circuit_open,
                "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
                "last_error": row.last_error,
            }

    def add_capability_audit(self, provider_id: str, integration_level: int, target_level: int, evidence: str, blocking_reason: str | None, last_verified_at: str) -> None:
        with new_session() as s:
            s.add(
                CapabilityAuditRow(
                    provider_id=provider_id,
                    integration_level=integration_level,
                    target_level=target_level,
                    evidence=evidence,
                    blocking_reason=blocking_reason,
                    last_verified_at=last_verified_at,
                )
            )
            s.commit()

    def list_capability_audits(self, provider_id: str | None = None) -> list[dict]:
        stmt = select(CapabilityAuditRow).order_by(CapabilityAuditRow.id.desc())
        if provider_id:
            stmt = stmt.where(CapabilityAuditRow.provider_id == provider_id)
        with new_session() as s:
            rows = s.scalars(stmt).all()
            return [
                {
                    "provider_id": r.provider_id,
                    "integration_level": r.integration_level,
                    "target_level": r.target_level,
                    "evidence": r.evidence,
                    "blocking_reason": r.blocking_reason,
                    "last_verified_at": r.last_verified_at,
                }
                for r in rows
            ]


    # ---- projects / tasks (P24-001) ----
    def upsert_project(self, payload: dict) -> str:
        with new_session() as s:
            row = s.get(ProjectRow, payload["project_id"])
            if row is None:
                row = ProjectRow(project_id=payload["project_id"], title=payload.get("title", ""), data_json=payload)
                s.add(row)
            else:
                row.title = payload.get("title", row.title)
                row.data_json = payload
            s.commit()
            return payload["project_id"]

    def list_projects(self) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(ProjectRow).order_by(ProjectRow.created_at.desc())).all()
            counts: dict[str, int] = {}
            for pid in s.scalars(select(TaskRow.project_id)).all():
                counts[pid] = counts.get(pid, 0) + 1
            return [
                {
                    "project_id": r.project_id,
                    "title": r.title,
                    "task_count": counts.get(r.project_id, 0),
                    "data": r.data_json,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows
            ]

    def get_project(self, project_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(ProjectRow, project_id)
            if row is None:
                return None
            tasks = s.scalars(select(TaskRow).where(TaskRow.project_id == project_id).order_by(TaskRow.created_at.desc())).all()
            return {
                "project": {
                    "project_id": row.project_id,
                    "title": row.title,
                    "data": row.data_json,
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat(),
                },
                "tasks": [_task_to_dict(t) for t in tasks],
            }

    def add_task(self, project_id: str, kind: str, ref_id: str, status: str = "OPEN") -> dict:
        with new_session() as s:
            row = TaskRow(task_id=new_id("task"), project_id=project_id, kind=kind, ref_id=ref_id, status=status)
            s.add(row)
            s.commit()
            return _task_to_dict(row)

    def list_tasks(self, project_id: str) -> list[dict]:
        with new_session() as s:
            rows = s.scalars(select(TaskRow).where(TaskRow.project_id == project_id).order_by(TaskRow.created_at.desc())).all()
            return [_task_to_dict(r) for r in rows]

    def get_task(self, task_id: str) -> dict | None:
        with new_session() as s:
            row = s.get(TaskRow, task_id)
            return _task_to_dict(row) if row else None

    def set_task_status(self, task_id: str, status: str) -> dict | None:
        with new_session() as s:
            row = s.get(TaskRow, task_id)
            if row is None:
                return None
            row.status = status
            s.commit()
            return _task_to_dict(row)


REPO = Repository()
