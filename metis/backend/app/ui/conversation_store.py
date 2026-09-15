"""Conversation persistence + ConversationContext (P0-03/P0-10, §6/§7).

The single access path for conversations / messages / tasks / result links /
interventions. Every state transition the pipeline makes goes through here so
that refresh-restore, multi-conversation isolation and failure convergence all
read the same truth.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.core.logging import get_logger
from app.db.session import new_session
from app.ui.models import (
    ConversationInterventionRow,
    ConversationMessageRow,
    ConversationResultLinkRow,
    ConversationRow,
    ConversationTaskRow,
)

log = get_logger("conversation.store")


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ConversationStore:
    # -- conversations -------------------------------------------------------
    def ensure_conversation(self, cid: str, title: str = "") -> None:
        with new_session() as s:
            row = s.execute(select(ConversationRow).where(ConversationRow.conversation_id == cid)).scalar_one_or_none()
            if row is None:
                s.add(ConversationRow(conversation_id=cid, title=title[:80] or "新任务", status="active", created_at=_now()))
                s.commit()

    def create_conversation(self, title: str = "新任务") -> str:
        cid = _new_id("conv")
        self.ensure_conversation(cid, title)
        return cid

    def list_conversations(self, limit: int = 50) -> list[dict]:
        with new_session() as s:
            rows = s.execute(
                select(ConversationRow).order_by(ConversationRow.updated_at.desc()).limit(limit)
            ).scalars().all()
            return [{"conversation_id": r.conversation_id, "title": r.title, "status": r.status, "created_at": r.created_at.isoformat()} for r in rows]

    # -- messages ------------------------------------------------------------
    def add_message(self, cid: str, role: str, content: str, task_id: str | None = None, data: dict | None = None) -> str:
        mid = _new_id("msg")
        with new_session() as s:
            s.add(ConversationMessageRow(message_id=mid, conversation_id=cid, role=role, content=content, task_id=task_id, data_json=data or {}, created_at=_now()))
            s.commit()
        return mid

    def list_messages(self, cid: str) -> list[dict]:
        with new_session() as s:
            rows = s.execute(
                select(ConversationMessageRow).where(ConversationMessageRow.conversation_id == cid).order_by(ConversationMessageRow.created_at, ConversationMessageRow.message_id)
            ).scalars().all()
            return [
                {
                    "message_id": r.message_id,
                    "role": r.role,
                    "content": r.content,
                    "task_id": r.task_id,
                    "data": r.data_json or {},
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]

    # -- tasks ---------------------------------------------------------------
    def create_task(self, cid: str, intent: str, goal: str = "discover_only") -> str:
        tid = _new_id("ctask")
        with new_session() as s:
            s.add(ConversationTaskRow(task_id=tid, conversation_id=cid, intent=intent, goal=goal, state="UNDERSTANDING", stage_label="正在理解你的需求…", created_at=_now()))
            s.commit()
        return tid

    def update_task(self, task_id: str, **fields) -> None:
        if not fields:
            return
        if "data" in fields:  # callers use the external name; the column is data_json
            fields["data_json"] = fields.pop("data")
        fields["updated_at"] = _now()
        with new_session() as s:
            s.execute(sa_update(ConversationTaskRow).where(ConversationTaskRow.task_id == task_id).values(**fields))
            s.commit()

    def get_task(self, task_id: str) -> dict | None:
        with new_session() as s:
            r = s.execute(select(ConversationTaskRow).where(ConversationTaskRow.task_id == task_id)).scalar_one_or_none()
            if r is None:
                return None
            return self._task_dict(r)

    def latest_task(self, cid: str) -> dict | None:
        with new_session() as s:
            r = s.execute(
                select(ConversationTaskRow).where(ConversationTaskRow.conversation_id == cid).order_by(ConversationTaskRow.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            return self._task_dict(r) if r else None

    def list_tasks(self, cid: str) -> list[dict]:
        with new_session() as s:
            rows = s.execute(
                select(ConversationTaskRow).where(ConversationTaskRow.conversation_id == cid).order_by(ConversationTaskRow.created_at.desc())
            ).scalars().all()
            return [self._task_dict(r) for r in rows]

    @staticmethod
    def _task_dict(r: ConversationTaskRow) -> dict:
        return {
            "task_id": r.task_id,
            "conversation_id": r.conversation_id,
            "goal": r.goal,
            "intent": r.intent,
            "state": r.state,
            "stage_label": r.stage_label,
            "progress": r.progress,
            "planning_id": r.planning_id,
            "run_id": r.run_id,
            "access_job_id": r.access_job_id,
            "download_job_ids": r.download_job_ids or [],
            "build_id": r.build_id,
            "error_code": r.error_code,
            "error_message": r.error_message,
            "data": r.data_json or {},
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }

    # -- result links (P0-10: stable result_id across the whole lifecycle) ----
    def add_result_link(self, cid: str, task_id: str | None, source_kind: str, source_ref: str, title: str = "", provider_id: str = "", state: str = "FOUND", data: dict | None = None) -> str:
        """Create a link with a NEW stable result_id. The id never changes again —
        candidate→artifact→build transitions only update state/source_ref."""
        rid = _new_id("res")
        with new_session() as s:
            pos = len(self.list_result_links(cid))
            s.add(ConversationResultLinkRow(
                conversation_id=cid, result_id=rid, task_id=task_id, source_kind=source_kind,
                source_ref=source_ref, position=pos, state=state, title=title,
                provider_id=provider_id, data_json=data or {}, created_at=_now(),
            ))
            s.commit()
        return rid

    def update_result_link(self, result_id: str, **fields) -> None:
        if "data" in fields:
            fields["data_json"] = fields.pop("data")
        fields["updated_at"] = _now()
        with new_session() as s:
            s.execute(sa_update(ConversationResultLinkRow).where(ConversationResultLinkRow.result_id == result_id).values(**fields))
            s.commit()

    def get_result_link(self, result_id: str) -> dict | None:
        with new_session() as s:
            r = s.execute(select(ConversationResultLinkRow).where(ConversationResultLinkRow.result_id == result_id)).scalar_one_or_none()
            return self._link_dict(r) if r else None

    def list_result_links(self, cid: str) -> list[dict]:
        with new_session() as s:
            rows = s.execute(
                select(ConversationResultLinkRow).where(ConversationResultLinkRow.conversation_id == cid).order_by(ConversationResultLinkRow.position, ConversationResultLinkRow.id)
            ).scalars().all()
            return [self._link_dict(r) for r in rows]

    @staticmethod
    def _link_dict(r: ConversationResultLinkRow) -> dict:
        return {
            "result_id": r.result_id,
            "conversation_id": r.conversation_id,
            "task_id": r.task_id,
            "source_kind": r.source_kind,
            "source_ref": r.source_ref,
            "position": r.position,
            "state": r.state,
            "title": r.title,
            "provider_id": r.provider_id,
            "data": r.data_json or {},
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }

    # -- interventions (P0-13) ------------------------------------------------
    def create_intervention(self, cid: str, kind: str, provider_name: str, message: str, *, task_id: str | None = None, result_id: str | None = None, access_job_id: str | None = None, download_job_id: str | None = None, browser_session_id: str | None = None, data: dict | None = None) -> str:
        iid = _new_id("intv")
        with new_session() as s:
            s.add(ConversationInterventionRow(
                intervention_id=iid, conversation_id=cid, kind=kind, provider_name=provider_name,
                message=message, task_id=task_id, result_id=result_id, access_job_id=access_job_id,
                download_job_id=download_job_id, browser_session_id=browser_session_id,
                state="WAITING_USER", data_json=data or {}, created_at=_now(),
            ))
            s.commit()
        return iid

    def get_intervention(self, intervention_id: str) -> dict | None:
        with new_session() as s:
            r = s.execute(select(ConversationInterventionRow).where(ConversationInterventionRow.intervention_id == intervention_id)).scalar_one_or_none()
            return self._intervention_dict(r) if r else None

    def update_intervention(self, intervention_id: str, **fields) -> None:
        if "data" in fields:
            fields["data_json"] = fields.pop("data")
        fields["updated_at"] = _now()
        with new_session() as s:
            s.execute(sa_update(ConversationInterventionRow).where(ConversationInterventionRow.intervention_id == intervention_id).values(**fields))
            s.commit()

    def list_interventions(self, cid: str, state: str | None = None) -> list[dict]:
        q = select(ConversationInterventionRow).where(ConversationInterventionRow.conversation_id == cid)
        if state:
            q = q.where(ConversationInterventionRow.state == state)
        with new_session() as s:
            rows = s.execute(q.order_by(ConversationInterventionRow.created_at.desc())).scalars().all()
            return [self._intervention_dict(r) for r in rows]

    @staticmethod
    def _intervention_dict(r: ConversationInterventionRow) -> dict:
        return {
            "intervention_id": r.intervention_id,
            "conversation_id": r.conversation_id,
            "task_id": r.task_id,
            "result_id": r.result_id,
            "access_job_id": r.access_job_id,
            "download_job_id": r.download_job_id,
            "browser_session_id": r.browser_session_id,
            "kind": r.kind,
            "provider_name": r.provider_name,
            "state": r.state,
            "message": r.message,
            "data": r.data_json or {},
            "created_at": r.created_at.isoformat(),
        }

    # -- ConversationContext (§7) ---------------------------------------------
    def load_context(self, cid: str) -> dict:
        """Unified context: everything follow-up messages need from prior turns."""
        links = self.list_result_links(cid)
        tasks = self.list_tasks(cid)
        latest_task = tasks[0] if tasks else None
        messages = self.list_messages(cid)

        def _by_state(state: str) -> list[dict]:
            return [lnk for lnk in links if lnk["state"] == state]

        context = {
            "conversation_id": cid,
            "latest_requirement": (latest_task or {}).get("data", {}).get("requirement_text", ""),
            "latest_planning_id": (latest_task or {}).get("planning_id"),
            "latest_run_id": (latest_task or {}).get("run_id"),
            "latest_build_id": (latest_task or {}).get("build_id"),
            "selected_result_ids": [lnk["result_id"] for lnk in links if lnk ["data"].get("selected")],
            "ready_result_ids": [lnk["result_id"] for lnk in _by_state("READY")],
            "ready_artifact_ids": [lnk["source_ref"] for lnk in _by_state("READY") if lnk ["source_kind"] == "artifact"],
            "final_result_ids": [lnk["result_id"] for lnk in _by_state("FINAL")],
            "result_links": links,
            "user_constraints": {},
            "history_summary": " ".join(m["content"][:120] for m in messages[-6:]),
        }
        # constraints accumulated across refine turns live on the latest task WITH data —
        # the newest row is usually the just-created current task (still empty)
        prior_task = next((t for t in tasks if (t.get("data") or {}).get("requirement_text")), None)
        if prior_task:
            context["user_constraints"] = prior_task.get("data", {}).get("user_constraints") or {}
            context["latest_requirement"] = prior_task.get("data", {}).get("requirement_text") or context["latest_requirement"]
        return context


STORE = ConversationStore()
