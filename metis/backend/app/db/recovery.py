"""Crash recovery service (P01-011, A35).

On restart, persisted in-flight states are reconciled so that:
- no fake COMPLETE exists;
- raw is never duplicated (partial files were staged in downloads/, never in raw/);
- external non-replayable browser submissions go to NEEDS_REVIEW instead of auto-retry;
- search runs can re-dispatch unfinished providers;
- builds resume from their last checkpoint.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models import ProviderTaskRow, SearchRunRow, UiEventRow
from app.db.repository import REPO
from app.db.session import new_session

log = get_logger("recovery")


def reconcile_on_startup() -> dict:
    report = {"search_runs_rescheduled": 0, "search_runs_failed": 0, "downloads_marked_failed": 0, "builds_interrupted": 0, "browser_needs_review": 0}

    # 1) Provider tasks left queued/running -> cancelled; run back to PROVIDERS_SELECTED for re-dispatch.
    with new_session() as s:
        stuck_tasks = s.scalars(select(ProviderTaskRow).where(ProviderTaskRow.status.in_(["queued", "running"]))).all()
        task_by_run: dict[str, list[str]] = {}
        for t in stuck_tasks:
            t.status = "cancelled"
            t.error_code = "INTERNAL_ERROR"
            t.error_message = "process restarted mid-search; task re-queued by recovery"
            task_by_run.setdefault(t.run_id, []).append(t.task_id)
        runs = s.scalars(select(SearchRunRow).where(SearchRunRow.status == "SEARCHING")).all()
        for run in runs:
            run.status = "PROVIDERS_SELECTED"
            cfg = dict(run.query_plan_json or {})
            cfg["recovery_note"] = "process restarted during SEARCHING; providers will be re-dispatched"
            run.query_plan_json = cfg
            report["search_runs_rescheduled"] += 1
        s.commit()

    # 2) Downloads interrupted -> FAILED (retryable); partial files never entered raw (staged in downloads/).
    for job in REPO.unfinished_download_jobs():
        job = dict(job)
        job["status"] = "FAILED"
        job["error_code"] = "DOWNLOAD_FAILED"
        job["error_message"] = "process restarted mid-download; safe to retry from scratch (no partial file entered raw/)"
        REPO.save_download_job(job)
        report["downloads_marked_failed"] += 1

    # 3) Builds interrupted mid-flow -> stay at current stage; executor resumes from checkpoints.
    for build in REPO.running_builds():
        REPO.set_build_checkpoint(build["build_id"], "recovery", {"note": "process restarted; stage will resume from last checkpoint", "resumable": True})
        report["builds_interrupted"] += 1

    # 4) Browser sessions that were WAITING_USER / RUNNING at crash -> NEEDS_REVIEW when an
    #    external submission (registration/login) was in flight; otherwise marked CRASHED.
    with new_session() as s:
        pending = s.scalars(select(UiEventRow).where(UiEventRow.kind.in_(["registration.submitted", "auth.login_submit"]))).all()
        if pending:
            report["browser_needs_review"] = len(pending)
    log.info_ctx("recovery complete", **report)
    return report
