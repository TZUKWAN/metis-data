"""Search orchestration (P10-005/016, A3): real parallel multi-provider search.

- asyncio tasks with per-provider timeout, retry/backoff, cancel;
- one provider failing/timing out never fails the run (isolated);
- per-provider task statuses queued/running/done/error/timeout/cancelled persisted;
- run state machine transitions persisted; searchable history after restart.
"""
from __future__ import annotations

import asyncio
import uuid

from app.core.config import get_settings
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.db.repository import REPO
from app.domain.enums import ProviderTaskStatus, SearchRunStatus
from app.domain.schemas import DatasetCandidate, new_id
from app.providers.base import available_adapters, get_adapter
from app.providers.http_client import RATE_LIMITER
from app.search.dedup import deduplicate
from app.search.recommend import evaluate_candidates

log = get_logger("search")


class SearchOrchestrator:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()

    async def run_search(
        self,
        requirement: dict,
        provider_ids: list[str] | None = None,
        query_plan: dict[str, list[str]] | None = None,
        run_id: str | None = None,
        bundle: dict | None = None,
    ) -> str:
        """Run a parallel multi-provider search.

        Phase B: when `bundle` (a persisted PlanningBundle) is provided it drives
        the run — provider_ids default to bundle["source_plan"]["provider_priorities"]
        (when the caller passes none) and queries default to bundle["query_plans"];
        the bundle is persisted verbatim in the run's query_plan under the key
        "planning_bundle" (incl. planning_source). Without a bundle the behaviour
        is exactly as before (backward compatible).
        """
        run_id = run_id or f"run_{uuid.uuid4().hex[:16]}"
        if bundle:
            if provider_ids is None:
                provider_ids = [p for p in (bundle.get("source_plan") or {}).get("provider_priorities") or [] if p]
            bundle_queries = {
                str(qp.get("provider_id")): [str(q) for q in qp.get("queries") or []]
                for qp in bundle.get("query_plans") or []
                if isinstance(qp, dict) and qp.get("provider_id")
            }
            query_plan = {**bundle_queries, **(query_plan or {})}
        provider_ids = list(provider_ids or [])
        query_plan = dict(query_plan or {})
        persisted_plan = dict(query_plan)
        if bundle:
            persisted_plan["planning_bundle"] = bundle
        # bundle-driven runs may carry a PlanningBundle requirement without an id —
        # synthesize + persist one so the run stays traceable to the requirement
        if not requirement.get("requirement_id"):
            # synthesize a minimal persisted requirement from bundle fields only
            from app.domain.schemas import DataRequirement

            br = (bundle or {}).get("requirement") or {}
            fallback_req = {
                "raw_request": br.get("research_goal") or br.get("research_question") or json.dumps(br, ensure_ascii=False)[:300],
                "unit_of_analysis": br.get("unit_of_analysis") or "unknown",
                "geography": br.get("geography") or [],
                "time_range": tuple(br["time_range"].values()) if br.get("time_range") and all(br["time_range"].values()) else None,
                "frequency": br.get("frequency") or "unknown",
                "assumptions": br.get("assumptions") or [],
                "notes": "derived from planning bundle",
            }
            if fallback_req["time_range"] is None:
                fallback_req.pop("time_range")
            req_obj = DataRequirement(**fallback_req)
            requirement = dict(requirement)
            requirement["requirement_id"] = req_obj.requirement_id
            REPO.save_requirement(req_obj)
        REPO.save_search_run(run_id, requirement["requirement_id"], SearchRunStatus.PROVIDERS_SELECTED, query_plan=persisted_plan, provider_ids=provider_ids)
        self._cancelled.discard(run_id)

        # seed provider task rows
        for pid in provider_ids:
            REPO.upsert_provider_task(new_id("pt"), run_id, pid, ProviderTaskStatus.QUEUED, query="; ".join(query_plan.get(pid, []))[:400])
        REPO.transition_search_run(run_id, SearchRunStatus.SEARCHING)

        tasks = REPO.list_provider_tasks(run_id)
        cfg = get_settings()
        sem = asyncio.Semaphore(cfg.search_max_concurrency)

        async def worker(task_id: str, pid: str, query: str) -> None:
            async with sem:
                if run_id in self._cancelled:
                    REPO.finish_provider_task(task_id, ProviderTaskStatus.CANCELLED)
                    return
                if pid not in available_adapters():
                    # Phase C: BROWSER discovery strategy — no HTTP adapter but a
                    # browser search recipe exists → drive the real Live Browser
                    from app.auth.recipes import BROWSER_SEARCH_RECIPES

                    recipe = BROWSER_SEARCH_RECIPES.get(pid)
                    if recipe is None:
                        REPO.finish_provider_task(task_id, ProviderTaskStatus.ERROR, error_code="PROVIDER_CAPABILITY_MISSING", error_message=f"no search adapter or browser recipe for {pid} (registered only)")
                        return
                    # P03-002: try/finally guarantees session reclamation on
                    # success/timeout/cancel/error alike; user takeover transfers
                    # ownership and keeps the window alive.
                    from app.providers.registry import get_registry
                    from app.search.browser_worker import BrowserSearchWorker

                    home = get_registry().get(pid).homepage
                    worker = BrowserSearchWorker(pid, recipe, base_url=home if str(home).startswith("http") else None)
                    try:
                        results = []
                        for q in (query_plan.get(pid) or [query])[:2]:
                            results.extend(await worker.search(q, limit=10))
                        for c in results[:12]:
                            REPO.save_candidate(run_id, c)
                        REPO.finish_provider_task(task_id, ProviderTaskStatus.DONE, result_count=len(results))
                    except MetisError as e:
                        if e.code == "USER_INTERVENTION_REQUIRED" and worker.session is not None:
                            worker.transfer_ownership("user")  # keep the window for the user
                            REPO.upsert_provider_task(task_id, run_id, pid, ProviderTaskStatus.RUNNING, browser_session_id=worker.session.session_id)
                            REPO.add_ui_event("browser.search_handover", "WARNING", task_id=run_id, provider_id=pid, payload={"session_id": worker.session.session_id})
                        REPO.finish_provider_task(task_id, ProviderTaskStatus.ERROR, error_code=e.code, error_message=e.message)
                    except asyncio.CancelledError:
                        REPO.finish_provider_task(task_id, ProviderTaskStatus.CANCELLED)
                        raise
                    except Exception as e:  # noqa: BLE001
                        REPO.finish_provider_task(task_id, ProviderTaskStatus.ERROR, error_code="PROVIDER_HTTP_ERROR", error_message=f"browser search: {e}"[:200])
                    finally:
                        await worker.close()  # P03-002: worker-owned sessions always reclaimed
                    return
                REPO.upsert_provider_task(task_id, run_id, pid, ProviderTaskStatus.RUNNING, started_at=True)
                try:
                    await RATE_LIMITER.acquire(pid, min_interval_s=0.2)
                    adapter = get_adapter(pid)
                    all_cands: list[DatasetCandidate] = []
                    for q in (query_plan.get(pid) or [query])[:3]:
                        if run_id in self._cancelled:
                            REPO.finish_provider_task(task_id, ProviderTaskStatus.CANCELLED)
                            return
                        cands = await asyncio.wait_for(adapter.search_datasets(q, limit=10), timeout=cfg.search_provider_timeout_s)
                        all_cands.extend(cands)
                    seen_refs: set[str] = set()
                    uniq: list[DatasetCandidate] = []
                    for c in all_cands:
                        key = c.doi or c.sources[0].source_url or c.title
                        if key in seen_refs:
                            continue
                        seen_refs.add(key)
                        uniq.append(c)
                    for c in uniq[:12]:
                        REPO.save_candidate(run_id, c)
                    REPO.finish_provider_task(task_id, ProviderTaskStatus.DONE, result_count=len(uniq))
                except TimeoutError:
                    REPO.finish_provider_task(task_id, ProviderTaskStatus.TIMEOUT, error_code="PROVIDER_TIMEOUT", error_message=f"provider exceeded {cfg.search_provider_timeout_s}s")
                except asyncio.CancelledError:
                    REPO.finish_provider_task(task_id, ProviderTaskStatus.CANCELLED)
                    raise
                except MetisError as e:
                    REPO.finish_provider_task(task_id, ProviderTaskStatus.ERROR, error_code=e.code, error_message=e.message)
                except Exception as e:  # noqa: BLE001
                    code = "PROVIDER_HTTP_ERROR"
                    msg = f"{type(e).__name__}: {e}"[:300]
                    if "401" in msg or "PermissionError" in type(e).__name__:
                        code = "INVALID_CREDENTIALS"
                    REPO.finish_provider_task(task_id, ProviderTaskStatus.ERROR, error_code=code, error_message=msg)

        workers = [asyncio.create_task(worker(t["task_id"], t["provider_id"], t.get("query", ""))) for t in tasks]
        self._tasks[run_id] = asyncio.gather(*workers)
        try:
            await self._tasks[run_id]
        except asyncio.CancelledError:
            pass
        finally:
            self._tasks.pop(run_id, None)

        if run_id in self._cancelled:
            self._cancelled.discard(run_id)
            REPO.transition_search_run(run_id, SearchRunStatus.CANCELLED)
            return run_id

        REPO.transition_search_run(run_id, SearchRunStatus.CANDIDATES_NORMALIZED)
        cands = REPO.list_candidates(run_id, dedup_only=False)
        dedup_groups = deduplicate(cands)
        for group in dedup_groups:
            for c in group:
                REPO.save_candidate(run_id, c)
        REPO.transition_search_run(run_id, SearchRunStatus.CANDIDATES_EVALUATED)
        evaluated = evaluate_candidates(REPO.list_candidates(run_id, dedup_only=True), requirement)
        for c in evaluated:
            REPO.save_candidate(run_id, c)
        REPO.transition_search_run(run_id, SearchRunStatus.AUTO_SELECTED)
        REPO.transition_search_run(run_id, SearchRunStatus.COMPLETED)
        return run_id

    async def cancel(self, run_id: str) -> bool:
        """A3/A36: cancellation stops new provider requests; workers observe flag."""
        self._cancelled.add(run_id)
        task = self._tasks.get(run_id)
        tasks = REPO.list_provider_tasks(run_id)
        n = 0
        for t in tasks:
            if t["status"] in ("queued", "running"):
                REPO.finish_provider_task(t["task_id"], ProviderTaskStatus.CANCELLED)
                n += 1
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            REPO.transition_search_run(run_id, SearchRunStatus.CANCELLED)
        except MetisError:
            REPO.save_search_run(run_id, REPO.get_search_run(run_id)["requirement_id"] if REPO.get_search_run(run_id) else "", SearchRunStatus.CANCELLED)
        log.info_ctx("search cancelled", run_id=run_id, tasks_cancelled=n)
        return True


ORCHESTRATOR = SearchOrchestrator()
