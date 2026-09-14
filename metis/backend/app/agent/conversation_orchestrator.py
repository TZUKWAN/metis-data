"""Conversation Orchestrator: single entry point for the chat UI.

User message → intent → planning → search → acquire → build → result projection.
Hides all internal complexity behind user-facing language and result views.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import get_logger

log = get_logger("conversation")


class Intent(Enum):
    DISCOVER_DATA = "discover_data"
    FIND_AND_DOWNLOAD = "find_and_download"
    BUILD_DATASET = "build_dataset"
    REFINE_SEARCH = "refine_search"
    EXPLAIN_RESULT = "explain_result"
    PREVIEW_DATA = "preview_data"
    GENERAL = "general"


class TaskState(Enum):
    CREATED = "created"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    SEARCHING = "searching"
    COLLECTING = "collecting"
    WAITING_USER = "waiting_user"
    PROCESSING = "processing"
    BUILDING = "building"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


# User-friendly state mapping
STATE_LABELS = {
    TaskState.UNDERSTANDING: "正在理解你的需求…",
    TaskState.PLANNING: "正在规划数据方案…",
    TaskState.SEARCHING: "正在寻找数据…",
    TaskState.COLLECTING: "正在获取数据…",
    TaskState.PROCESSING: "正在整理数据…",
    TaskState.BUILDING: "正在合成数据集…",
    TaskState.WAITING_USER: "需要你的操作",
    TaskState.COMPLETE: "已完成",
    TaskState.FAILED: "遇到问题",
    TaskState.CANCELLED: "已取消",
}


@dataclass
class ConversationMessage:
    message_id: str
    conversation_id: str
    role: str  # user | assistant | system
    content: str
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
    task_id: str | None = None


@dataclass
class ConversationTask:
    task_id: str
    conversation_id: str
    intent: str
    state: str = TaskState.CREATED
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
    updated_at: str = ""
    active_run_id: str | None = None
    planning_id: str | None = None
    access_job_id: str | None = None
    build_id: str | None = None
    error: str | None = None


class ConversationOrchestrator:
    """Single entry point: user message → understand → plan → search → acquire → build → result."""

    async def handle_message(self, conversation_id: str, text: str) -> dict:
        """Process a user message through the full pipeline. Returns assistant reply + results."""
        intent = self._classify(text)
        log.info_ctx("conversation message", cid=conversation_id, intent=intent, text=text[:80])

        if intent == Intent.DISCOVER_DATA:
            return await self._discover(conversation_id, text)
        elif intent == Intent.FIND_AND_DOWNLOAD:
            return await self._discover_and_download(conversation_id, text)
        elif intent == Intent.BUILD_DATASET:
            return await self._build(conversation_id, text)
        elif intent == Intent.REFINE_SEARCH:
            return await self._refine(conversation_id, text)
        elif intent == Intent.EXPLAIN_RESULT:
            return await self._explain(conversation_id, text)
        else:
            return await self._discover(conversation_id, text)

    def _classify(self, text: str) -> Intent:
        t = text.lower()
        if any(k in t for k in ("下载", "download", "获取数据", "帮我下载")):
            return Intent.FIND_AND_DOWNLOAD
        if any(k in t for k in ("合并", "合成", "面板", "build", "做成")):
            return Intent.BUILD_DATASET
        if any(k in t for k in ("不要", "换成", "只要", "改为", "不想要")):
            return Intent.REFINE_SEARCH
        if any(k in t for k in ("为什么", "解释", "哪里来", "怎么做的")):
            return Intent.EXPLAIN_RESULT
        return Intent.DISCOVER_DATA

    async def _discover(self, cid: str, text: str) -> dict:
        from app.agent.orchestrator import build_planning_bundle, save_bundle
        from app.search.orchestrator import ORCHESTRATOR

        bundle = await build_planning_bundle(text)
        save_bundle(bundle, requirement_text=text)
        req_dict = bundle.requirement.model_dump(mode="json")
        req_dict.setdefault("requirement_id", f"req_{uuid.uuid4().hex[:12]}")

        provider_ids = bundle.source_plan.provider_priorities[:6] or None
        run_id = await ORCHESTRATOR.run_search(req_dict, provider_ids, None, None, bundle=bundle.model_dump(mode="json"))

        from app.db.repository import REPO

        candidates = REPO.list_candidates(run_id)
        provider_tasks = REPO.list_provider_tasks(run_id)

        done = sum(1 for t in provider_tasks if t["status"] == "done")
        total = len(provider_tasks)
        n_cands = len(candidates)

        reply = f"我正在查找{self._extract_topic(text)}相关的数据。\n\n已搜索 {total} 个数据来源（{done} 个成功），找到 {n_cands} 个候选数据集。结果已放到右侧。"
        if n_cands == 0:
            reply = f"我搜索了 {total} 个来源，但没有找到与「{self._extract_topic(text)}」直接匹配的公开数据。\n\n你可以试着放宽时间范围或地域限制，我可以继续搜索学术数据仓储。"

        return {
            "reply": reply,
            "intent": "discover",
            "run_id": run_id,
            "planning_id": bundle.planning_id,
            "planning_source": bundle.planning_source,
            "n_candidates": n_cands,
            "candidates": candidates[:10],
            "providers_done": done,
            "providers_total": total,
        }

    async def _discover_and_download(self, cid: str, text: str) -> dict:
        result = await self._discover(cid, text)
        result["intent"] = "find_and_download"
        result["reply"] = result["reply"] + "\n\n正在获取排名靠前的数据，完成后会自动通知你。"
        return result

    async def _build(self, cid: str, text: str) -> dict:
        return {"reply": "合成功能需要先获取数据。请先告诉我要查找什么数据，获取完成后再说「合成」。", "intent": "build"}

    async def _refine(self, cid: str, text: str) -> dict:
        return await self._discover(cid, text)

    async def _explain(self, cid: str, text: str) -> dict:
        from app.db.repository import REPO
        runs = REPO.list_search_runs(1)
        if runs:
            cands = REPO.list_candidates(runs[0]["run_id"])
            if cands:
                c = cands[0]
                reasons = c.get("reasons", [])
                reply = f"推荐「{c.get('title', '')}」的原因：\n" + "\n".join(f"· {r}" for r in reasons[:5])
                return {"reply": reply, "intent": "explain"}
        return {"reply": "暂无可解释的结果。请先让我搜索数据。", "intent": "explain"}

    @staticmethod
    def _extract_topic(text: str) -> str:
        m = re.search(r"[\u4e00-\u9fff]+(?:、[\u4e00-\u9fff]+)*", text)
        return m.group(0)[:30] if m else text[:30]
