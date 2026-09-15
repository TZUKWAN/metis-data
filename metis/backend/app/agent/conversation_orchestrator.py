"""Conversation Orchestrator — the single entry point for the chat UI (P0-05/06/07/08/09).

User message → UserGoal → pipeline with persisted intermediate states:
UNDERSTANDING → PLANNING → SEARCHING → COLLECTING → (WAITING_USER) → BUILDING → COMPLETE/FAILED

Every pipeline run:
- writes its state transitions to conversation_tasks (P0-12)
- links search candidates into conversation_result_links with a STABLE result_id
  that survives candidate→artifact→build transitions (P0-10)
- streams results into the right pane as soon as the first candidate lands (§13)
- converges any exception to FAILED with a user-understandable message (P0-11)
"""
from __future__ import annotations

import asyncio
import re
import uuid
from enum import StrEnum

from app.core.logging import get_logger
from app.events.bus import publish
from app.ui.conversation_store import STORE

log = get_logger("conversation")

# stage → (state, user-facing label, progress) — P0-12: every stage is persisted
STAGES: dict[str, tuple[str, str, float]] = {
    "understanding": ("UNDERSTANDING", "正在理解你的需求…", 0.05),
    "planning": ("PLANNING", "正在规划数据方案…", 0.15),
    "searching": ("SEARCHING", "正在寻找数据…", 0.30),
    "collecting": ("COLLECTING", "正在获取数据…", 0.60),
    "waiting_user": ("WAITING_USER", "需要你的操作", 0.65),
    "processing": ("PROCESSING", "正在整理数据…", 0.75),
    "building": ("BUILDING", "正在合成数据集…", 0.85),
    "complete": ("COMPLETE", "已完成", 1.0),
    "failed": ("FAILED", "遇到问题", 1.0),
}

# user-understandable error copy — no tracebacks ever reach the chat (UAT-16)
ERROR_COPY: dict[str, str] = {
    "LLM_UNAVAILABLE": "AI 服务暂时不可用，请稍后重试。",
    "LLM_TIMEOUT": "AI 响应超时，请重试或换个说法。",
    "ACQUISITION_FAILED": "这份数据暂时获取失败，你可以尝试其他来源。",
    "INVALID_DOWNLOAD_CONTENT": "下载的内容不是有效的数据文件（可能需要登录），任务已停止。",
    "PROVIDER_TIMEOUT": "部分数据来源响应超时。",
    "ALL_PROVIDERS_FAILED": "所有数据来源都无法访问，请稍后重试或换个说法。",
    "BUILD_FAILED": "数据合成失败，请检查数据来源后重试。",
}


class UserGoal(StrEnum):
    DISCOVER_ONLY = "discover_only"
    DISCOVER_AND_ACQUIRE = "discover_and_acquire"
    DISCOVER_ACQUIRE_BUILD = "discover_acquire_build"
    OPERATE_ON_EXISTING_RESULTS = "operate_on_existing_results"
    REFINE_EXISTING_TASK = "refine_existing_task"
    EXPLAIN = "explain"


GOAL_INTENT = {
    UserGoal.DISCOVER_ONLY: "discover_data",
    UserGoal.DISCOVER_AND_ACQUIRE: "find_and_download",
    UserGoal.DISCOVER_ACQUIRE_BUILD: "build_dataset",
    UserGoal.OPERATE_ON_EXISTING_RESULTS: "build_dataset",
    UserGoal.REFINE_EXISTING_TASK: "refine_search",
    UserGoal.EXPLAIN: "explain_result",
}

GOAL_SYSTEM_PROMPT = """你是 Metis Data 的意图分类器。根据用户消息和当前会话上下文，输出严格 JSON：
{"goal": "...", "topic": "...", "constraints": {"exclude_providers": [], "only_providers": []}, "language": "zh"}
goal 必须是以下之一：
- discover_only: 只想找数据/看有什么数据
- discover_and_acquire: 找到并下载/获取数据
- discover_acquire_build: 一句话要求"构建面板/合成数据集"，且会话中还没有可用数据 → 需要完整走 查找→获取→合成
- operate_on_existing_results: 对会话中已有的数据做合成/合并/操作（如"把这两个合并"）
- refine_existing_task: 修改或缩小之前的查找条件（如"不要世界银行，只用OECD"）
- explain: 解释之前的结果/推荐理由
Output JSON only."""

# intervention → pipeline waiter registry (P0-15: login resumes the ORIGINAL download)
WAITERS: dict[str, asyncio.Event] = {}

INTERVENTION_WAIT_S = 900  # 15 min max wait for user auth
SEARCH_POLL_S = 1.0


def emit(cid: str, kind: str, payload: dict) -> None:
    publish(f"conversation.{kind}", "INFO", task_id=cid, payload={"conversation_id": cid, **payload})


def set_stage(cid: str, task_id: str, stage: str, **extra) -> None:
    state, label, progress = STAGES[stage]
    fields = {"state": state, "stage_label": label, "progress": progress, **extra}
    STORE.update_task(task_id, **fields)
    emit(cid, "task.updated", {"task_id": task_id, "state": state, "stage_label": label, "progress": progress, **extra})


class ConversationOrchestrator:
    """Single entry point: user message → understand → plan → search → acquire → build → result."""

    async def handle_message(self, conversation_id: str, text: str, task_id: str) -> dict:
        """Process one user message through the full pipeline. Returns the assistant reply payload."""
        ctx = STORE.load_context(conversation_id)
        set_stage(conversation_id, task_id, "understanding")
        understanding = await self.classify_goal(text, ctx)
        goal = understanding["goal"]
        STORE.update_task(task_id, goal=goal.value if isinstance(goal, UserGoal) else str(goal))
        log.info_ctx("conversation message", cid=conversation_id, goal=str(goal), text=text[:80])

        if goal == UserGoal.EXPLAIN:
            return await self._explain(conversation_id, task_id, text)
        if goal == UserGoal.REFINE_EXISTING_TASK:
            return await self._refine(conversation_id, task_id, text, understanding)
        if goal == UserGoal.OPERATE_ON_EXISTING_RESULTS:
            return await self._build_existing(conversation_id, task_id, text)
        if goal == UserGoal.DISCOVER_AND_ACQUIRE:
            return await self._discover_and_download(conversation_id, task_id, text, understanding, build=False)
        if goal == UserGoal.DISCOVER_ACQUIRE_BUILD:
            return await self._discover_and_download(conversation_id, task_id, text, understanding, build=True)
        return await self._discover(conversation_id, task_id, text, understanding)

    # ---------------- understanding (P0-07) ----------------
    async def classify_goal(self, text: str, ctx: dict) -> dict:
        """LLM structured output first; deterministic rules as fallback (P0-07)."""
        understanding: dict = {"goal": UserGoal.DISCOVER_ONLY, "topic": "", "constraints": {"exclude_providers": [], "only_providers": []}}
        try:
            from app.agent.client import LLMClient

            client = LLMClient()
            context_brief = {
                "has_ready_artifacts": bool(ctx.get("ready_artifact_ids")),
                "n_results": len(ctx.get("result_links") or []),
                "latest_requirement": (ctx.get("latest_requirement") or "")[:200],
            }
            out = await client.complete_json(GOAL_SYSTEM_PROMPT, f"用户消息: {text}\n会话上下文: {context_brief}")
            g = str(out.get("goal", ""))
            if g in {m.value for m in UserGoal}:
                understanding["goal"] = UserGoal(g)
            understanding["topic"] = str(out.get("topic", ""))
            c = out.get("constraints") or {}
            understanding["constraints"] = {
                "exclude_providers": [str(x) for x in (c.get("exclude_providers") or [])],
                "only_providers": [str(x) for x in (c.get("only_providers") or [])],
            }
            return understanding
        except Exception as e:  # noqa: BLE001 — LLM unavailable → rules
            log.info_ctx("goal llm classify failed, rules fallback", error=str(e)[:160])
        return self._classify_rules(text, ctx)

    @staticmethod
    def _classify_rules(text: str, ctx: dict) -> dict:
        t = text.lower()
        understanding = {
            "goal": UserGoal.DISCOVER_ONLY,
            "topic": ConversationOrchestrator._extract_topic(text),
            "constraints": {"exclude_providers": [], "only_providers": []},
        }
        # refine signals: negation/limitation of a previous search
        if any(k in t for k in ("不要", "换成", "只用", "只要", "改为", "不想要", "排除")) and (ctx.get("result_links") or ctx.get("latest_run_id")):
            understanding["goal"] = UserGoal.REFINE_EXISTING_TASK
            if any(p in t for p in ("世界银行", "world_bank", "worldbank")):
                understanding["constraints"]["exclude_providers"].append("world_bank")
            if any(p in t for p in ("oecd", "经合组织")):
                understanding["constraints"]["only_providers"].append("oecd")
            if any(p in t for p in ("ilo", "ilostat", "国际劳工")):
                understanding["constraints"]["only_providers"].append("ilostat")
            return understanding
        if any(k in t for k in ("为什么", "解释", "哪里来", "怎么做的", "推荐理由")):
            understanding["goal"] = UserGoal.EXPLAIN
            return understanding
        wants_build = any(k in t for k in ("合并", "合成", "构建", "做成", "面板", "build", "merge"))
        wants_download = any(k in t for k in ("下载", "download", "获取数据", "拿到", "导出"))
        if wants_build:
            if ctx.get("ready_artifact_ids") or ctx.get("ready_result_ids"):
                understanding["goal"] = UserGoal.OPERATE_ON_EXISTING_RESULTS
            else:
                # one-shot: build requested but no data yet → full discover→acquire→build (P0-07)
                understanding["goal"] = UserGoal.DISCOVER_ACQUIRE_BUILD
            return understanding
        if wants_download:
            understanding["goal"] = UserGoal.DISCOVER_AND_ACQUIRE
        return understanding

    # ---------------- discover (search + stream results) ----------------
    async def _discover(self, cid: str, task_id: str, text: str, understanding: dict, *, build: bool = False) -> dict:
        """PLANNING → SEARCHING with first-result streaming (P0-01, §13)."""
        set_stage(cid, task_id, "planning")
        bundle = await self._plan(cid, task_id, text, understanding)

        run_id = await self._search_and_stream(cid, task_id, bundle, text)

        links = [lnk for lnk in STORE.list_result_links(cid) if lnk["task_id"] == task_id]
        topic = understanding.get("topic") or self._extract_topic(text)
        n = len(links)

        if n == 0:
            reply = (
                f"我没有找到与「{topic}」直接匹配的公开数据。\n\n"
                "你可以试着放宽时间范围或地域限制，我可以继续搜索学术数据仓储。"
            )
        elif build:
            reply = f"已找到 {n} 个与「{topic}」相关的候选数据，正在获取并合成面板数据。"
        else:
            reply = f"我找到了 {n} 个与「{topic}」相关的候选数据集，已放到右侧。你可以预览，或让我直接下载。"

        STORE.update_task(task_id, run_id=run_id, planning_id=bundle.get("planning_id"))
        return {
            "reply": reply,
            "goal": understanding["goal"].value if isinstance(understanding["goal"], UserGoal) else str(understanding["goal"]),
            "run_id": run_id,
            "planning_id": bundle.get("planning_id"),
            "n_results": n,
        }

    async def _plan(self, cid: str, task_id: str, text: str, understanding: dict) -> dict:
        from app.agent.orchestrator import build_planning_bundle, save_bundle

        bundle_model = await build_planning_bundle(text)
        bundle = bundle_model.model_dump(mode="json")
        constraints = understanding.get("constraints") or {}
        if constraints.get("only_providers"):
            bundle.setdefault("source_plan", {})["provider_priorities"] = constraints["only_providers"]
        if constraints.get("exclude_providers"):
            bundle.setdefault("source_plan", {})["provider_priorities"] = [
                p for p in bundle.get("source_plan", {}).get("provider_priorities", []) if p not in constraints["exclude_providers"]
            ]
        planning_id = save_bundle(bundle, requirement_text=text)
        bundle["planning_id"] = planning_id
        return bundle

    async def _search_and_stream(self, cid: str, task_id: str, bundle: dict, text: str) -> str:
        """Run the search in the background while streaming new candidates into
        result links (P0-01/P0-10/§13) — the pane fills as results land."""
        from app.search.orchestrator import ORCHESTRATOR as SEARCH_ORCH

        req_dict = dict(bundle.get("requirement") or {})
        req_dict.setdefault("requirement_id", f"req_{uuid.uuid4().hex[:12]}")
        provider_ids = bundle.get("source_plan", {}).get("provider_priorities")[:6] or None
        run_id = f"run_{uuid.uuid4().hex[:16]}"

        set_stage(cid, task_id, "searching", run_id=run_id)
        STORE.update_task(task_id, run_id=run_id, data_json={"requirement_text": text})

        search_task = asyncio.create_task(
            SEARCH_ORCH.run_search(req_dict, provider_ids, None, run_id, bundle=bundle)
        )
        seen: set[str] = set()
        cancelled = False
        while not search_task.done():
            await asyncio.sleep(SEARCH_POLL_S)
            await self._ingest_candidates(cid, task_id, run_id=run_id, seen=seen)
            if (STORE.get_task(task_id) or {}).get("state") == "CANCELLED":
                await SEARCH_ORCH.cancel(run_id)  # stops provider workers via the flag
                cancelled = True
                break
        if cancelled:
            search_task.cancel()
            raise asyncio.CancelledError
        await search_task
        # final sweep — the post-search dedup/evaluate pass may add candidates
        await self._ingest_candidates(cid, task_id, run_id=run_id, seen=seen)
        return run_id

    async def _ingest_candidates(self, cid: str, task_id: str, run_id: str | None = None, seen: set[str] | None = None) -> None:
        """Turn freshly-landed candidates into result links the moment they appear."""
        from app.db.repository import REPO

        seen = seen if seen is not None else set()
        if not run_id:
            return
        for c in REPO.list_candidates(run_id):
            cand_id = c.get("candidate_id", "")
            if not cand_id or cand_id in seen:
                continue
            seen.add(cand_id)
            rid = STORE.add_result_link(
                cid, task_id, "candidate", cand_id,
                title=c.get("title", ""), provider_id=c.get("provider_id", ""),
                state="FOUND",
                data={"score": c.get("score"), "run_id": run_id},
            )
            emit(cid, "result.added", {"result_id": rid, "state": "FOUND", "title": c.get("title", ""), "source_name": c.get("provider_id", "")})

    # ---------------- discover + acquire (+ optional build) ----------------
    async def _discover_and_download(self, cid: str, task_id: str, text: str, understanding: dict, *, build: bool) -> dict:
        """P0-05/P0-06: real execution — discover → rank → acquire → (build) → READY/FINAL."""
        discover = await self._discover(cid, task_id, text, understanding, build=build)
        links = [lnk for lnk in STORE.list_result_links(cid) if lnk["task_id"] == task_id and lnk["state"] == "FOUND"]
        links.sort(key=lambda lnk: (lnk.get("data") or {}).get("score") or 0, reverse=True)

        if not links:
            return {**discover, "reply": discover["reply"] + "\n\n没有可获取的数据，因此未执行下载。"}

        set_stage(cid, task_id, "collecting")
        # "这两份 / 两个都 / 全部" → acquire more than one (user plural intent)
        plural = any(k in text for k in ("两份", "两个", "全部", "都下载", "这几份"))
        n_pick = 2 if (build or plural) else 1
        acquired: list[str] = []
        blocked: list[str] = []
        for link in links[:n_pick]:
            ok, note = await self._acquire_link(cid, task_id, link)
            (acquired if ok else blocked).append(f"《{(link.get('title') or '')[:40]}》{note}")

        ready = [lnk for lnk in STORE.list_result_links(cid) if lnk["task_id"] == task_id and lnk["state"] == "READY"]
        reply_parts = []
        if acquired:
            reply_parts.append("已成功获取 " + "、".join(acquired))
        if blocked:
            reply_parts.append("未能获取 " + "、".join(blocked))

        if build:
            if not ready:
                return {**discover, "reply": "；".join(reply_parts) + "。\n\n可用数据不足，暂时无法合成面板。你可以让我换其他来源再试。"}
            set_stage(cid, task_id, "building")
            final = await self._build_from_links(cid, task_id)
            if final:
                reply_parts.append(f"合成完成：{final['title']}，已放到右侧（可下载 CSV / XLSX / Parquet）")
                return {**discover, "reply": "；".join(reply_parts) + "。", "final_result_id": final["result_id"]}
            return {**discover, "reply": "；".join(reply_parts) + "。\n\n合成失败，请让我重试或换个说法。"}

        reply = "；".join(reply_parts) + "。" if reply_parts else discover["reply"]
        return {**discover, "reply": reply, "ready_result_ids": [lnk["result_id"] for lnk in ready]}

    async def _acquire_link(self, cid: str, task_id: str, link: dict) -> tuple[bool, str]:
        """Full chain for ONE result link: DownloadJob → Access → (Intervention) → Acquisition → artifact.

        The link keeps its result_id through the whole transition FOUND→ACQUIRING→(WAITING_USER)→READY.
        """
        from app.access.executor import resolve_access
        from app.db.repository import REPO
        from app.downloads.service import MANAGER

        rid = link["result_id"]
        c = REPO.get_candidate(link["source_ref"]) or {}
        provider_id = c.get("provider_id") or link["provider_id"]
        src = (c.get("sources") or [{}])[0]
        dataset_ref = src.get("source_ref") or link["source_ref"]
        source_url = src.get("source_url") or ""

        STORE.update_result_link(rid, state="ACQUIRING")
        emit(cid, "result.updated", {"result_id": rid, "state": "ACQUIRING"})

        job = MANAGER.create_job(provider_id, dataset_ref, source_url, dataset_title=c.get("title", ""), license=c.get("license", "UNKNOWN"))
        task = STORE.get_task(task_id) or {}
        STORE.update_task(task_id, download_job_ids=[*(task.get("download_job_ids") or []), job.download_job_id])

        try:
            access_job = await resolve_access(provider_id, dataset_ref, candidate_id=link["source_ref"], download_job_id=job.download_job_id)
        except Exception as e:  # noqa: BLE001
            self._fail_link(cid, rid, str(e))
            return False, str(getattr(e, "message", e))[:60]

        if access_job.state != "AUTHORIZED":
            return await self._wait_for_user_then_acquire(cid, task_id, link, provider_id, access_job, job)

        return await self._run_acquisition(cid, rid, access_job, job)

    def _fail_link(self, cid: str, rid: str, error: str) -> None:
        link = STORE.get_result_link(rid) or {}
        STORE.update_result_link(rid, state="FAILED", data={**(link.get("data") or {}), "error": error[:200]})
        emit(cid, "result.updated", {"result_id": rid, "state": "FAILED"})

    async def _wait_for_user_then_acquire(self, cid: str, task_id: str, link: dict, provider_id: str, access_job, job) -> tuple[bool, str]:
        """Access needs the user (P0-13): create intervention, pause, auto-resume (P0-14/15)."""
        rid = link["result_id"]
        iid = STORE.create_intervention(
            cid, "LOGIN_REQUIRED", provider_id,
            f"获取该数据需要登录 {provider_id}。已打开登录窗口，完成登录后任务会自动继续。",
            task_id=task_id, result_id=rid,
            access_job_id=getattr(access_job, "access_job_id", None),
            download_job_id=job.download_job_id,
            browser_session_id=getattr(access_job, "browser_session_id", None),
            data={"dataset_ref": job.dataset_ref},
        )
        STORE.update_result_link(rid, state="WAITING_USER")
        STORE.update_task(task_id, state="WAITING_USER", stage_label="需要你的操作", access_job_id=getattr(access_job, "access_job_id", None))
        emit(cid, "intervention.required", {"intervention_id": iid, "result_id": rid, "kind": "LOGIN_REQUIRED", "provider_name": provider_id, "browser_session_id": getattr(access_job, "browser_session_id", None)})
        set_stage(cid, task_id, "waiting_user")

        ev = WAITERS.setdefault(iid, asyncio.Event())
        try:
            await asyncio.wait_for(ev.wait(), timeout=INTERVENTION_WAIT_S)
        except TimeoutError:
            STORE.update_intervention(iid, state="EXPIRED", message="等待登录超时，已跳过该来源。")
            self._fail_link(cid, rid, "等待登录超时")
            return False, "等待登录超时"

        itv = STORE.get_intervention(iid) or {}
        if itv.get("state") != "RESOLVED":
            self._fail_link(cid, rid, "用户跳过了该来源")
            return False, "已跳过"

        # auto-resume: the ORIGINAL acquisition continues — no second click (P0-15)
        from app.access.executor import resolve_access

        access_job2 = await resolve_access(provider_id, job.dataset_ref, candidate_id=link["source_ref"], download_job_id=job.download_job_id)
        if access_job2.state != "AUTHORIZED":
            self._fail_link(cid, rid, "登录仍未生效")
            return False, "登录未生效"
        return await self._run_acquisition(cid, rid, access_job2, job)

    async def _run_acquisition(self, cid: str, rid: str, access_job, job) -> tuple[bool, str]:
        from app.acquisition.service import ACQUISITION
        from app.core.config import get_settings
        from app.db.repository import REPO

        staging = get_settings().workspace_dir / "downloads" / job.download_job_id
        staging.mkdir(parents=True, exist_ok=True)
        try:
            await ACQUISITION.acquire(access_job.model_dump(mode="json"), REPO.get_download_job(job.download_job_id), staging)
        except Exception as e:  # noqa: BLE001
            self._fail_link(cid, rid, str(getattr(e, "message", e)))
            return False, str(getattr(e, "message", e))[:60]

        artifact = _artifact_for_download_job(job.download_job_id)
        if not artifact:
            self._fail_link(cid, rid, "未生成数据文件")
            return False, "无产物"

        # SAME result_id transitions to READY (P0-10) — the card never changes identity
        link = STORE.get_result_link(rid) or {}
        STORE.update_result_link(
            rid, state="READY", source_kind="artifact", source_ref=artifact["artifact_id"],
            data={**(link.get("data") or {}), "artifact_id": artifact["artifact_id"], "file_format": str(artifact.get("file_format", ""))},
        )
        emit(cid, "result.updated", {"result_id": rid, "state": "READY", "artifact_id": artifact["artifact_id"]})
        return True, "已获取"

    # ---------------- build (P0-06) ----------------
    async def _build_existing(self, cid: str, task_id: str, text: str) -> dict:
        """OPERATE_ON_EXISTING_RESULTS: merge READY results in this conversation."""
        set_stage(cid, task_id, "planning")
        ready = [lnk for lnk in STORE.list_result_links(cid) if lnk["state"] == "READY"]
        if not ready:
            # P0-07: never a text-only stub — tell the truth and offer the full chain
            return {
                "reply": "当前会话还没有已获取（可用）的数据。告诉我你需要什么数据，我会走完整的 查找→获取→合成 流程。",
                "goal": "operate_on_existing_results",
            }
        set_stage(cid, task_id, "building")
        final = await self._build_from_links(cid, task_id)
        if final:
            return {
                "reply": f"已把 {len(ready)} 份数据合成最终数据集「{final['title']}」，已放到右侧。可以预览或下载 CSV / XLSX。",
                "goal": "build",
                "final_result_id": final["result_id"],
            }
        return {"reply": "合成过程中遇到问题，请让我重试。", "goal": "build"}

    async def _build_from_links(self, cid: str, task_id: str) -> dict | None:
        """READY links → BuildPlanner → BuildExecutor → FINAL link. Returns the final link dict."""
        from app.agent.build_planner import plan_build, plan_build_sync
        from app.builds.executor import BuildExecutor
        from app.db.repository import REPO

        ready = [lnk for lnk in STORE.list_result_links(cid) if lnk["state"] == "READY" and lnk["source_kind"] == "artifact"]
        assets = []
        for lnk in ready:
            art = REPO.get_artifact(lnk["source_ref"])
            if not art:
                continue
            if not (art.get("profile") or {}).get("columns"):
                from app.datasets.profile import profile_artifact

                try:
                    art["profile"] = profile_artifact(art["artifact_id"], art["raw_path"])
                except Exception as e:  # noqa: BLE001
                    log.info_ctx("profile failed", artifact_id=str(art.get("artifact_id")), error=str(e)[:120])
            assets.append({"artifact_id": art["artifact_id"], "profile": art.get("profile") or {}, "variables": []})
        if not assets:
            return None

        task = STORE.get_task(task_id) or {}
        requirement_text = (task.get("data_json") or {}).get("requirement_text") or "合并当前会话的数据集"
        try:
            plan = await plan_build({"research_goal": requirement_text}, assets)
        except Exception as e:  # noqa: BLE001
            log.info_ctx("llm build plan failed; deterministic", error=str(e)[:160])
            plan = plan_build_sync({"research_goal": requirement_text}, assets)

        plan_dict = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else dict(plan)
        try:
            executor = BuildExecutor.from_build_plan(plan_dict, title=f"会话数据集 {cid[-6:]}")
        except Exception as e:  # noqa: BLE001
            log.error_ctx("build plan derivation failed", error=str(e)[:300])
            return None
        STORE.update_task(task_id, build_id=executor.build_id)
        try:
            await executor.run()
        except Exception as e:  # noqa: BLE001
            log.error_ctx("build run failed", build_id=executor.build_id, error=str(e)[:300])
            return None

        build = REPO.get_build(executor.build_id) or {}
        if str(build.get("status")) not in ("COMPLETE", "COMPLETED"):
            return None

        rid = STORE.add_result_link(
            cid, task_id, "build", executor.build_id,
            title=str(build.get("title") or "最终数据集"), provider_id="metis",
            state="FINAL", data={"build_id": executor.build_id, "n_inputs": len(assets)},
        )
        emit(cid, "result.added", {"result_id": rid, "state": "FINAL", "title": str(build.get("title") or "最终数据集"), "source_name": "metis"})
        return STORE.get_result_link(rid)

    # ---------------- refine (P0-08) ----------------
    async def _refine(self, cid: str, task_id: str, text: str, understanding: dict) -> dict:
        """REFINE_EXISTING_TASK: load previous planning, keep topic/geo/time, merge source constraints."""
        ctx = STORE.load_context(cid)
        prior_text = ctx.get("latest_requirement") or ""
        merged_text = f"{prior_text}（修订：{text}）" if prior_text else text
        understanding.setdefault("constraints", {"exclude_providers": [], "only_providers": []})

        set_stage(cid, task_id, "planning")
        bundle = await self._plan(cid, task_id, merged_text, understanding)
        run_id = await self._search_and_stream(cid, task_id, bundle, merged_text)
        links = [lnk for lnk in STORE.list_result_links(cid) if lnk["task_id"] == task_id]
        STORE.update_task(task_id, run_id=run_id, planning_id=bundle.get("planning_id"), data_json={"requirement_text": merged_text, "user_constraints": understanding.get("constraints") or {}})
        only = (understanding.get("constraints") or {}).get("only_providers") or []
        excl = (understanding.get("constraints") or {}).get("exclude_providers") or []
        scope = ("，仅使用 " + "、".join(only)) if only else (("，已排除 " + "、".join(excl)) if excl else "")
        return {
            "reply": f"已按你的要求调整搜索条件{scope}，新找到 {len(links)} 个候选数据集，已更新到右侧。",
            "goal": "refine",
            "run_id": run_id,
            "planning_id": bundle.get("planning_id"),
            "n_results": len(links),
        }

    # ---------------- explain (P0-09) ----------------
    async def _explain(self, cid: str, task_id: str, text: str) -> dict:
        """Conversation-scoped explanation: only results linked to THIS conversation (P0-09)."""
        from app.db.repository import REPO

        links = STORE.list_result_links(cid)
        if not links:
            return {"reply": "当前会话还没有结果可以解释。先告诉我你需要什么数据。", "goal": "explain"}
        target = links[0]
        if len(links) > 1 and target["source_kind"] == "candidate":
            for lnk in links[1:]:
                cand = REPO.get_candidate(lnk["source_ref"]) if lnk["source_kind"] == "candidate" else None
                if cand and any(w and w in str(cand.get("title", "")) for w in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", text)):
                    target = lnk
                    break
        cand = REPO.get_candidate(target["source_ref"]) if target["source_kind"] == "candidate" else None
        if not cand:
            n_art = len([lnk for lnk in links if lnk["source_kind"] == "artifact"])
            return {
                "reply": f"「{target['title']}」是本会话的最终数据集，由 {n_art} 份已获取数据合成，来源与字段血缘可在预览中查看。",
                "goal": "explain",
            }
        reasons = [str(r) for r in (cand.get("reasons") or [])]
        rec = cand.get("recommendation") or {}
        rec_txt = "、".join(f"{k} {float(v) * 100:.0f}" for k, v in rec.items() if isinstance(v, (int, float)) and v)
        reply = f"推荐「{cand.get('title', target['title'])}」的原因：\n" + "\n".join(f"· {r}" for r in reasons[:5])
        if rec_txt:
            reply += f"\n\n评分构成：{rec_txt}"
        return {"reply": reply, "goal": "explain", "result_id": target["result_id"]}

    @staticmethod
    def _extract_topic(text: str) -> str:
        m = re.search(r"[\u4e00-\u9fff]+(?:、[\u4e00-\u9fff]+)*", text)
        return m.group(0)[:30] if m else text[:30]


def _artifact_for_download_job(download_job_id: str) -> dict | None:
    from app.db.repository import REPO

    for a in REPO.list_artifacts():
        if a.get("download_job_id") == download_job_id:
            return REPO.get_artifact(a["artifact_id"]) or a
    return None


ORCHESTRATOR_CONV = ConversationOrchestrator()
