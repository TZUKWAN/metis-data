"""Conversation Task Manager (§10 / P0-11 / P0-12).

Owns every background conversation pipeline asyncio.Task:
- start / cancel / track / failure capture / cleanup / restart reconcile
- every state transition is persisted (task.updated event to the conversation WS)
- exceptions ALWAYS converge the task to FAILED — never a stuck UNDERSTANDING
- on service restart: RUNNING tasks are reconciled to FAILED_INTERRUPTED (no ghost tasks)
"""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from app.core.logging import get_logger
from app.events.bus import publish
from app.ui.conversation_store import STORE

log = get_logger("conversation.tasks")


def emit(cid: str, kind: str, payload: dict) -> None:
    """Push a conversation-scoped realtime event (WS clients + persisted event log)."""
    publish(f"conversation.{kind}", "INFO", task_id=cid, payload={"conversation_id": cid, **payload})


class ConversationTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def start(self, task_id: str, coro: Coroutine) -> asyncio.Task:
        """Wrap pipeline in failure-converging supervisor (P0-11)."""

        async def _supervised() -> None:
            try:
                await coro
            except asyncio.CancelledError:
                STORE.update_task(task_id, state="CANCELLED", stage_label="已取消")
                t = STORE.get_task(task_id) or {}
                emit(t.get("conversation_id", ""), "task.updated", {"task_id": task_id, "state": "CANCELLED"})
                raise
            except Exception as e:  # noqa: BLE001 — the boundary: nothing escapes un-persisted
                log.error_ctx("conversation pipeline crashed", task_id=task_id, error=str(e)[:400])
                code = str(getattr(e, "code", "PIPELINE_ERROR"))
                t = STORE.get_task(task_id) or {}
                cid = t.get("conversation_id", "")
                STORE.update_task(
                    task_id,
                    state="FAILED",
                    error_code=code,
                    error_message=str(e)[:500],
                    stage_label="遇到问题",
                )
                # user-facing failure copy in the chat itself — never a traceback (UAT-16)
                from app.agent.conversation_orchestrator import ERROR_COPY

                STORE.add_message(cid, "assistant", ERROR_COPY.get(code, "处理你的请求时遇到问题，请重试或换个说法。"), task_id=task_id)
                emit(cid, "task.failed", {"task_id": task_id, "state": "FAILED", "error_code": code, "error_message": str(e)[:300]})
            finally:
                self._tasks.pop(task_id, None)

        t = asyncio.create_task(_supervised())
        self._tasks[task_id] = t
        return t

    def cancel(self, task_id: str) -> bool:
        t = self._tasks.get(task_id)
        if t and not t.done():
            t.cancel()
            return True
        # not in memory (e.g. after restart) — persist CANCELLED directly
        STORE.update_task(task_id, state="CANCELLED", stage_label="已取消")
        return False

    def running_ids(self) -> list[str]:
        return [tid for tid, t in self._tasks.items() if not t.done()]

    def reconcile_on_startup(self) -> int:
        """Restart reconcile (§10): no ghost RUNNING tasks survive a restart."""
        n = 0
        for cid in [c["conversation_id"] for c in STORE.list_conversations(500)]:
            for t in STORE.list_tasks(cid):
                if t["state"] in ("UNDERSTANDING", "PLANNING", "SEARCHING", "COLLECTING", "PROCESSING", "BUILDING") and t["task_id"] not in self._tasks:
                    STORE.update_task(t["task_id"], state="FAILED", error_code="FAILED_INTERRUPTED", error_message="服务重启，任务被中断。请重试。", stage_label="已中断")
                    n += 1
        return n


MANAGER = ConversationTaskManager()
