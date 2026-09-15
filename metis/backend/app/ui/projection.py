"""UI projection layer: converts internal models to user-facing views.

Candidate / Artifact / Build → ResultView
Task states → TaskView
Interventions → InterventionView
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ResultState(Enum):
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


# UI-facing state copy (§9) — FOUND/ACQUIRING/... → 已找到/正在获取/...
STATE_LABELS = {
    "FOUND": "已找到",
    "ACQUIRING": "正在获取",
    "WAITING_USER": "需要登录",
    "READY": "可用",
    "BUILDING": "正在整理",
    "FINAL": "最终数据集",
    "FAILED": "获取失败",
}


def result_view_for_link(link: dict) -> ResultView:
    """Project a stable ConversationResultLink into the user-facing ResultView (P0-02/P0-10).

    Dispatch by link state:
    - FOUND       → candidate metadata view (no preview; download available)
    - READY       → artifact view (real data preview + export)
    - FINAL       → final build view (preview + export)
    - in-between  → same identity, transitional state copy
    The result_id is ALWAYS the link's stable id — never candidate_id/artifact_id.
    """
    from app.db.repository import REPO

    rid = link["result_id"]
    state = str(link.get("state") or "FOUND")
    base = dict(link.get("data") or {})
    view = ResultView(
        result_id=rid,
        title=link.get("title", ""),
        source_name=link.get("provider_id", ""),
        state=STATE_LABELS.get(state, state),
    )
    kind = link.get("source_kind", "candidate")

    if kind == "candidate" and state in ("FOUND", "ACQUIRING", "WAITING_USER", "FAILED"):
        c = REPO.get_candidate(link.get("source_ref") or "") or {}
        provider_id = c.get("provider_id") or link.get("provider_id", "")
        tc = c.get("time_coverage") or {}
        reasons = c.get("reasons") or []
        view = ResultView(
            result_id=rid,
            title=link.get("title") or c.get("title", ""),
            source_name=provider_id,
            publisher=c.get("publisher", ""),
            description=(c.get("description") or "")[:300],
            geography=", ".join(c.get("geography") or []),
            time_range=f"{tc.get('start', '?')}–{tc.get('end', '?')}" if tc.get("start") else "",
            format=(((c.get("sources") or [{}])[0]).get("file_format") or "UNKNOWN"),
            license_label=_license_label(c.get("license", "UNKNOWN")),
            trust_label=_trust_label(provider_id),
            state=STATE_LABELS.get(state, state),
            recommendation=(reasons[0] if reasons else "")[:200],
            preview_available=False,
            download_available=state == "FOUND",
            internal_ref={"candidate_id": link.get("source_ref"), "provider_id": provider_id},
        )
    elif kind == "artifact" and state == "READY":
        a = REPO.get_artifact(link.get("source_ref") or "") or {}
        view = ResultView(
            result_id=rid,
            title=link.get("title") or a.get("dataset_title") or a.get("dataset_ref", ""),
            source_name=a.get("provider_id") or link.get("provider_id", ""),
            description="已获取并校验的数据文件，可预览与导出。",
            format=str(base.get("file_format") or a.get("file_format") or ""),
            license_label=_license_label(a.get("license", "")),
            trust_label=_trust_label(a.get("provider_id") or link.get("provider_id", "")),
            state=STATE_LABELS.get(state, state),
            preview_available=True,
            download_available=True,
            artifact_id=link.get("source_ref"),
            export_formats=["csv", "parquet", "xlsx"],
            internal_ref={"artifact_id": link.get("source_ref"), "raw_path": a.get("raw_path", "")},
        )
    elif kind == "build" and state == "FINAL":
        b = REPO.get_build(link.get("source_ref") or "") or {}
        n_inputs = int(base.get("n_inputs") or 0)
        view = ResultView(
            result_id=rid,
            title=link.get("title") or str(b.get("title") or "最终数据集"),
            source_name="metis",
            description=f"由 {n_inputs} 份数据合成的最终数据集，可直接预览与导出。" if n_inputs else "由本会话数据合成的最终数据集，可直接预览与导出。",
            format="csv",
            license_label="可公开使用",
            trust_label="官方/国际组织",
            state=STATE_LABELS.get(state, state),
            preview_available=True,
            download_available=True,
            export_formats=["csv", "xlsx", "parquet"],
            internal_ref={"build_id": link.get("source_ref")},
        )
    view.state = STATE_LABELS.get(state, state)
    return view


def link_to_task_view(t: dict) -> TaskView:
    return TaskView(
        task_id=t["task_id"],
        state=t["state"],
        title=t.get("stage_label", ""),
        message=t.get("error_message") or "",
        progress=t.get("progress"),
        cancellable=t.get("state") not in ("COMPLETE", "FAILED", "CANCELLED"),
        needs_user=t.get("state") == "WAITING_USER",
    )


def intervention_to_view(i: dict) -> InterventionView:
    kind_titles = {
        "LOGIN_REQUIRED": "需要登录",
        "CAPTCHA": "需要验证码",
        "MFA": "需要两步验证",
        "AGREEMENT": "需要同意条款",
        "PAYMENT": "需要付费授权",
    }
    return InterventionView(
        intervention_id=i["intervention_id"],
        kind=i.get("kind", "LOGIN_REQUIRED"),
        provider_name=i.get("provider_name", ""),
        title=kind_titles.get(i.get("kind", ""), "需要你的操作"),
        message=i.get("message", ""),
        browser_session_id=i.get("browser_session_id"),
        actions=["open_browser", "confirm_done", "skip"],
    )
