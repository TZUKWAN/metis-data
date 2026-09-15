"""UI projection layer: converts internal models to user-facing views.

Candidate / Artifact / Build → ResultView
Task states → TaskView
Interventions → InterventionView
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class ResultState(str, Enum):
    FOUND = "found"
    ACQUIRING = "acquiring"
    WAITING_USER = "waiting_user"
    READY = "ready"
    BUILDING = "building"
    FINAL = "final"
    FAILED = "failed"


class ResultView(BaseModel):
    result_id: str
    kind: str = "dataset"  # dataset | web_doc | social | paper
    title: str = ""
    source_name: str = ""
    publisher: str = ""
    description: str = ""
    geography: str = ""
    time_range: str = ""
    unit: str = ""
    format: str = ""
    license_label: str = "使用条件未知"
    trust_label: str = "社区数据"
    state: str = ResultState.FOUND
    recommendation: str = ""
    preview_available: bool = False
    download_available: bool = False
    export_formats: list[str] = []
    artifact_id: str | None = None
    internal_ref: dict = {}


class TaskView(BaseModel):
    task_id: str
    state: str
    title: str = ""
    message: str = ""
    progress: float | None = None
    cancellable: bool = True
    needs_user: bool = False


class InterventionView(BaseModel):
    intervention_id: str
    kind: str  # LOGIN_REQUIRED | CAPTCHA | MFA | AGREEMENT | PAYMENT
    provider_name: str = ""
    title: str = ""
    message: str = ""
    browser_session_id: str | None = None
    actions: list[str] = []


def _trust_label(provider_id: str) -> str:
    official = {"world_bank", "eurostat", "ilostat", "oecd", "un_comtrade", "us_census", "usgs", "un_databases", "nbs_china"}
    academic = {"zenodo", "harvard_dataverse", "dryad", "osf", "figshare"}
    if provider_id in official:
        return "官方/国际组织"
    if provider_id in academic:
        return "学术仓储"
    return "社区数据"


def _license_label(license_str: str) -> str:
    if not license_str or license_str == "UNKNOWN":
        return "使用条件未知"
    import re

    if re.search(r"CC0|public.?domain|usgov", license_str, re.I):
        return "可公开使用"
    if re.search(r"CC-BY|attribution|ogl", license_str, re.I):
        return "需署名"
    if re.search(r"restricted|commercial", license_str, re.I):
        return "受限"
    return license_str


def candidate_to_result_view(c: dict, task_state: str = "found") -> ResultView:
    """Project a search Candidate into a user-facing ResultView."""
    provider_id = c.get("provider_id", "")
    tc = c.get("time_coverage") or {}
    time_range = f"{tc.get('start', '?')}–{tc.get('end', '?')}" if tc.get("start") else ""
    reasons = c.get("reasons") or []
    recommendation = reasons[0] if reasons else ""
    state_map = {"AUTHORIZED": ResultState.READY}
    return ResultView(
        result_id=c.get("candidate_id", ""),
        kind="dataset",
        title=c.get("title", ""),
        source_name=provider_id,
        publisher=c.get("publisher", ""),
        description=(c.get("description") or "")[:300],
        geography=", ".join(c.get("geography", [])),
        time_range=time_range,
        format=(((c.get("sources") or [{}])[0]).get("file_format") or "UNKNOWN"),
        license_label=_license_label(c.get("license", "UNKNOWN")),
        trust_label=_trust_label(provider_id),
        state=task_state,
        recommendation=recommendation[:200],
        preview_available=False,
        download_available=task_state == "found",
        internal_ref={"candidate_id": c.get("candidate_id"), "provider_id": provider_id, "source_ref": (c.get("sources") or [{}])[0].get("source_ref", "")},
    )


def artifact_to_result_view(a: dict) -> ResultView:
    return ResultView(
        result_id=a.get("artifact_id", ""),
        kind="dataset",
        title=a.get("dataset_title") or a.get("dataset_ref", ""),
        source_name=a.get("provider_id", ""),
        format=a.get("file_format", ""),
        license_label=_license_label(a.get("license", "")),
        trust_label=_trust_label(a.get("provider_id", "")),
        state=ResultState.READY,
        preview_available=True,
        download_available=True,
        artifact_id=a.get("artifact_id"),
        export_formats=["csv", "parquet", "xlsx"],
        internal_ref={"artifact_id": a.get("artifact_id"), "raw_path": a.get("raw_path", "")},
    )
