"""FastAPI application — the ONLY UI↔backend boundary (REST + WebSocket)."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import MetisError
from app.core.logging import get_logger, setup_logging
from app.db.recovery import reconcile_on_startup
from app.db.repository import REPO
from app.db.session import init_db

log = get_logger("api")

TASKS: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(get_settings().log_level)
    get_settings().ensure_dirs()
    init_db()
    reconcile_on_startup()
    yield


app = FastAPI(title="Metis Data", version="1.0.0", lifespan=lifespan)


def err(e: MetisError):
    return JSONResponse(status_code=422 if e.code not in ("NOT_FOUND",) else 404, content=e.to_dict())


@app.exception_handler(MetisError)
async def metis_error_handler(_request, exc: MetisError):
    return err(exc)


# ---------------- models ----------------
class RequirementIn(BaseModel):
    text: str


class RequirementEdit(BaseModel):
    unit_of_analysis: str | None = None
    time_range: list[int] | None = None
    frequency: str | None = None
    variables: dict | None = None
    preferred_sources: list[str] | None = None
    excluded_sources: list[str] | None = None
    trust_requirement: str | None = None
    access_tolerance: str | None = None
    notes: str | None = None


class SearchRunIn(BaseModel):
    requirement_id: str | None = None  # optional when planning_id carries the requirement
    provider_ids: list[str] | None = None
    max_providers: int = 8
    planning_id: str | None = None  # Phase B: bundle drives the run when provided


class DownloadIn(BaseModel):
    provider_id: str
    dataset_ref: str
    source_url: str
    dataset_title: str = ""
    version: str | None = None
    license: str = "UNKNOWN"
    access_mode: str = "UNKNOWN"


class BuildIn(BaseModel):
    title: str = ""
    requirement_id: str | None = None
    inputs: list[dict]
    keys: list[str] = ["country", "year"]
    target_unit: str = "country"
    time_frequency: str = "annual"
    missing_policy: str = "none"
    missing_policy_params: dict = {}
    derived_variables: list[dict] = []
    allow_mm_join: bool = False
    exports: list[str] = ["parquet", "csv", "xlsx"]


class BrowserCreateSessionRequest(BaseModel):
    """P02-001: create does NOT require session_id (a session id is created, not supplied)."""
    task_label: str = ""
    provider_id: str | None = None
    task_id: str | None = None
    access_job_id: str | None = None
    download_job_id: str | None = None


class BrowserActionRequest(BaseModel):
    session_id: str
    url: str | None = None
    target: dict | None = None
    text: str | None = None
    secret: bool = False
    key: str | None = None
    dx: int = 0
    dy: int = 0
    value: str | None = None
    index: int | None = None
    file_path: str | None = None
    task_label: str = ""


# backwards-compatible alias for existing imports
BrowserActionIn = BrowserActionRequest


class BindIn(BaseModel):
    provider_id: str
    account_label: str
    password: str


class AutoRegisterIn(BaseModel):
    enabled: bool


class IdentityIn(BaseModel):
    updates: dict
    disabled_fields: list[str] | None = None


# ---------------- requirements (A1) ----------------
@app.post("/api/requirements")
async def create_requirement(body: RequirementIn):
    from app.search.parser import parse_requirement, validate_requirement

    req = parse_requirement(body.text)
    problems = validate_requirement(req)
    REPO.save_requirement(req)
    REPO.add_ui_event("requirement.created", payload={"requirement_id": req.requirement_id, "assumptions": req.assumptions})
    return {**req.model_dump(mode="json"), "conflicts": problems}


@app.get("/api/requirements")
async def list_requirements():
    return REPO.list_requirements()


@app.get("/api/requirements/{rid}")
async def get_requirement(rid: str):
    r = REPO.get_requirement(rid)
    if not r:
        raise HTTPException(404, "requirement not found")
    return r


@app.put("/api/requirements/{rid}")
async def edit_requirement(rid: str, body: RequirementEdit):
    """User edits parsed fields; provider selection & query plan recompute downstream (A1)."""
    r = REPO.get_requirement(rid)
    if not r:
        raise HTTPException(404, "requirement not found")
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "time_range" and value and len(value) == 2:
            r["time_range"] = [int(value[0]), int(value[1])]
        else:
            r[field] = value
    r["updated_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    REPO.save_requirement(r)
    from app.domain.schemas import DataRequirement
    from app.search.parser import validate_requirement

    req_obj = DataRequirement(**r)
    return {"requirement": r, "conflicts": validate_requirement(req_obj), "plan_recomputed": True}


# ---------------- provider registry (A2) ----------------
@app.get("/api/providers")
async def providers():
    from app.providers.registry import get_registry

    return get_registry().integration_matrix()


@app.get("/api/providers/{pid}")
async def provider_detail(pid: str):
    from app.providers.registry import get_registry

    try:
        rec = get_registry().get(pid)
    except MetisError:
        raise HTTPException(404, pid)
    audits = REPO.list_capability_audits(pid)
    health = REPO.get_provider_health(pid)
    return {**rec.model_dump(), "audits": audits, "health": health}


# ---------------- search (A3) ----------------
def _bundle_query_plan(bundle: dict) -> dict[str, list[str]]:
    """Flatten bundle["query_plans"] into the {provider_id: [queries]} mapping."""
    return {
        str(qp.get("provider_id")): [str(q) for q in qp.get("queries") or []]
        for qp in bundle.get("query_plans") or []
        if isinstance(qp, dict) and qp.get("provider_id")
    }


def _requirement_from_bundle(bundle: dict) -> dict:
    """Phase B: derive and persist a DataRequirement from a planning bundle.

    unit_of_analysis/geography/time_range/frequency/variables map into the domain
    schema; raw_request keeps the original text; assumptions come from the bundle.
    """
    from app.domain.schemas import DataRequirement, VariableRequest

    reqp = bundle.get("requirement") or {}
    variables = VariableRequest()
    role_field = {"outcome": "outcomes", "exposure": "exposures", "mediator": "mediators", "moderator": "moderators", "control": "controls", "identifier": "identifiers"}
    for v in reqp.get("variables") or []:
        name = str((v or {}).get("concept", "")).strip()
        if not name:
            continue
        getattr(variables, role_field.get(str((v or {}).get("role", "control")), "controls")).append(name)
    tr = reqp.get("time_range") or {}
    start, end = tr.get("start"), tr.get("end")
    original_text = str(bundle.get("requirement_text") or reqp.get("research_goal") or "")
    req = DataRequirement(
        goal=str(reqp.get("research_goal") or ""),
        research_question=str(reqp.get("research_goal") or ""),
        raw_request=original_text,
        unit_of_analysis=str(reqp.get("unit_of_analysis") or "unknown"),
        geography=[str(g) for g in reqp.get("geography") or []],
        time_range=(int(start), int(end)) if start and end else None,
        frequency=str(reqp.get("frequency") or "unknown"),
        variables=variables,
        preferred_sources=[str(s) for s in reqp.get("preferred_sources") or []],
        assumptions=[str(a) for a in bundle.get("assumptions") or []],
    )
    payload = req.model_dump(mode="json")
    REPO.save_requirement(payload)
    REPO.add_ui_event("requirement.created_from_planning", payload={"requirement_id": req.requirement_id, "planning_id": bundle.get("planning_id", "")})
    return payload


@app.post("/api/search/runs")
async def start_search(body: SearchRunIn):
    from app.search.orchestrator import ORCHESTRATOR
    from app.search.selector import plan_queries, select_providers

    bundle: dict | None = None
    if body.planning_id:
        from app.agent.orchestrator import load_bundle

        bundle = load_bundle(body.planning_id)
        if not bundle:
            raise HTTPException(404, "planning not found")

    req: dict | None = None
    if body.requirement_id:
        req = REPO.get_requirement(body.requirement_id)
        if not req:
            raise HTTPException(404, "requirement not found")
    elif bundle:
        req = _requirement_from_bundle(bundle)
    if req is None:
        raise HTTPException(422, "requirement_id or planning_id is required")

    from app.domain.schemas import DataRequirement

    req_obj = DataRequirement(**req)
    provider_ids: list[str]
    plan: dict[str, list[str]]
    if body.provider_ids:
        from app.providers.registry import get_registry

        providers = [get_registry().get(p) for p in body.provider_ids]
        provider_ids = [p.provider_id for p in providers]
        plan = plan_queries(req_obj, providers)
    elif bundle:
        # planning bundle is the main chain: priorities + queries come from it
        provider_ids = [p for p in ((bundle.get("source_plan") or {}).get("provider_priorities") or []) if p]
        plan = _bundle_query_plan(bundle)
    else:
        providers = select_providers(req_obj, max_providers=body.max_providers)
        provider_ids = [p.provider_id for p in providers]
        plan = plan_queries(req_obj, providers)

    run_id = await ORCHESTRATOR.run_search(req, provider_ids, plan, bundle=bundle)
    resp: dict = {"run_id": run_id, "providers": provider_ids, "query_plan": plan}
    if bundle:
        resp["planning_source"] = str(bundle.get("planning_source", "fallback"))
    return resp


@app.get("/api/search/runs")
async def list_runs():
    return REPO.list_search_runs()


@app.get("/api/search/runs/{run_id}")
async def get_run(run_id: str):
    run = REPO.get_search_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    run["provider_tasks"] = REPO.list_provider_tasks(run_id)
    run["candidates"] = REPO.list_candidates(run_id, dedup_only=True)
    run["fuzzy_review"] = []
    from app.search.dedup import fuzzy_merge_review

    run["fuzzy_review"] = fuzzy_merge_review([[c] for c in run["candidates"]])
    return run


@app.post("/api/search/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    from app.search.orchestrator import ORCHESTRATOR

    await ORCHESTRATOR.cancel(run_id)
    return {"cancelled": True}


@app.post("/api/candidates/{candidate_id}/select")
async def select_candidate(candidate_id: str, selected: bool = True):
    REPO.set_candidate_selected(candidate_id, selected)
    return {"candidate_id": candidate_id, "selected": selected}


# ---------------- downloads (A14-A18) ----------------
@app.post("/api/downloads")
async def create_download(body: DownloadIn):
    """P04-012: Download Request → AccessJob → Authorized → Acquisition.

    If access cannot be resolved without the user, returns 202 with the access
    job state (WAITING_USER / LOGIN flow) instead of acquiring.
    """
    from app.access.executor import resolve_access
    from app.downloads.service import MANAGER

    job = MANAGER.create_job(body.provider_id, body.dataset_ref, body.source_url, dataset_title=body.dataset_title, version=body.version, license=body.license, access_mode=body.access_mode)
    try:
        access_job = await resolve_access(body.provider_id, body.dataset_ref, download_job_id=job.download_job_id)
    except MetisError as e:
        REPO.save_download_job({**job.model_dump(mode="json"), "status": "FAILED", "error_code": e.code, "error_message": e.message})
        return err(e)

    if access_job.state != "AUTHORIZED":
        return JSONResponse(status_code=202, content={"download_job": job.model_dump(mode="json"), "access_job": access_job.model_dump(mode="json"), "next": "complete access via Account Center / browser takeover — acquisition auto-resumes after login"})

    async def _run():
        from app.access.machine import AccessState, transition
        from app.acquisition.service import ACQUISITION

        staging = Path(get_settings().workspace_dir) / "downloads" / job.download_job_id
        staging.mkdir(parents=True, exist_ok=True)
        # Phase F: the ONLY production acquisition path — AcquisitionService
        # (v2 descriptor → DownloadManager stream → verify → raw commit)
        await ACQUISITION.acquire(access_job.model_dump(mode="json"), REPO.get_download_job(job.download_job_id), staging)
        transition(access_job, AccessState.COMPLETE, "acquisition + verification complete")

    TASKS[job.download_job_id] = asyncio.create_task(_run())
    return {**job.model_dump(mode="json"), "access_job_id": access_job.access_job_id}


@app.get("/api/downloads")
async def list_downloads():
    return REPO.list_download_jobs()


@app.post("/api/downloads/{job_id}/cancel")
async def cancel_download(job_id: str):
    from app.downloads.service import MANAGER

    MANAGER.cancel(job_id)
    return {"cancelled": True}


# ---------------- artifacts / profile (A20/A21) ----------------
@app.get("/api/artifacts")
async def list_artifacts():
    return REPO.list_artifacts()


@app.get("/api/artifacts/{artifact_id}")
async def artifact_detail(artifact_id: str):
    a = REPO.get_artifact(artifact_id)
    if not a:
        raise HTTPException(404, "artifact not found")
    return a


@app.post("/api/artifacts/{artifact_id}/profile")
async def profile_artifact_api(artifact_id: str):
    from app.datasets.profile import profile_artifact

    a = REPO.get_artifact(artifact_id)
    if not a:
        raise HTTPException(404, "artifact not found")
    prof = profile_artifact(artifact_id, a["raw_path"])
    return prof


@app.get("/api/artifacts/{artifact_id}/preview")
async def artifact_preview(artifact_id: str, rows: int = 50):
    a = REPO.get_artifact(artifact_id)
    if not a:
        raise HTTPException(404, "artifact not found")
    from app.core.paths import raw_root
    from app.datasets.parsers import parse_table

    df = parse_table(raw_root() / a["raw_path"]).df
    return {"columns": list(map(str, df.columns)), "rows": json.loads(df.head(rows).to_json(orient="records", force_ascii=False)), "total_rows": int(len(df))}


# ---------------- builds (A26-A34) ----------------
@app.post("/api/builds")
async def create_build(body: BuildIn):
    from app.builds.executor import BuildExecutor
    from app.domain.schemas import BuildConfig, BuildInputRef

    cfg = BuildConfig(
        title=body.title,
        requirement_id=body.requirement_id,
        inputs=[BuildInputRef(**i) for i in body.inputs],
        keys=body.keys,
        target_unit=body.target_unit,
        time_frequency=body.time_frequency,
        missing_policy=body.missing_policy,
        missing_policy_params=body.missing_policy_params,
        derived_variables=body.derived_variables,
        allow_mm_join=body.allow_mm_join,
        exports=body.exports,
    )
    REPO.save_build(cfg)
    ex = BuildExecutor(cfg.build_id)
    ex.generate_plan(cfg, [])
    REPO.save_build(cfg)
    return cfg.model_dump(mode="json")


# ---------------- Phase H: Build Planner → production builds ----------------
@app.post("/api/builds/plan")
async def plan_and_create_build(body: BuildPlanIn):
    """Phase H: selected artifacts → profiles → BuildPlanner → BuildPlan → BuildExecutor.

    No hardcoded country/year: entity strategy, keys, aggregations come from the plan
    (derived from real asset profiles); review points flag anything unknown.
    """
    from app.agent.build_planner import plan_build, plan_build_sync
    from app.builds.executor import BuildExecutor

    assets = []
    for inp in body.inputs:
        art = REPO.get_artifact(inp["artifact_id"])
        if not art:
            raise HTTPException(404, f"artifact {inp['artifact_id']} not found")
        assets.append({"artifact_id": inp["artifact_id"], "profile": art.get("profile") or {}, "variables": []})
    if not assets:
        raise HTTPException(422, "no input assets")

    if body.llm_enabled:
        plan = await plan_build(body.requirement, assets)
    else:
        plan = plan_build_sync(body.requirement, assets)

    executor = BuildExecutor.from_build_plan(plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan, title=body.title or "agent-planned build")
    review = (REPO.get_build(executor.build_id) or {}).get("plan_snapshot", {}).get("review_points", [])
    blocking = [r for r in review if r.get("severity") == "blocking"]
    if blocking and not body.auto_run:
        return JSONResponse(status_code=202, content={"build_id": executor.build_id, "plan": plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan, "review_points": review, "next": "blocking review points — edit plan or approve to run"})
    if body.auto_run or not review:
        TASKS[f"build_{executor.build_id}"] = asyncio.create_task(_run_build_safe(executor.build_id))
    return {"build_id": executor.build_id, "plan": plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan, "review_points": review, "running": body.auto_run or not review}


async def _run_build_safe(build_id: str):
    from app.builds.executor import BuildExecutor

    try:
        await BuildExecutor(build_id).run()
    except MetisError as e:
        REPO.add_ui_event("build.failed", "ERROR", task_id=build_id, payload=e.to_dict())
    except Exception as e:  # noqa: BLE001
        REPO.add_ui_event("build.failed", "ERROR", task_id=build_id, payload={"error": str(e)[:300]})


@app.post("/api/builds/{build_id}/approve")
async def approve_build(build_id: str):
    """User reviewed the blocking plan → run it now."""
    b = REPO.get_build(build_id)
    if not b:
        raise HTTPException(404, "build not found")
    TASKS[f"build_{build_id}"] = asyncio.create_task(_run_build_safe(build_id))
    return {"build_id": build_id, "running": True}


@app.get("/api/builds")
async def list_builds():
    return REPO.list_builds()


@app.get("/api/builds/{build_id}")
async def get_build(build_id: str):
    b = REPO.get_build(build_id)
    if not b:
        raise HTTPException(404, "build not found")
    b["operations"] = REPO.list_build_operations(build_id)
    b["validations"] = REPO.list_validations(build_id)
    b["field_lineage"] = REPO.list_field_lineage(build_id)
    return b


@app.post("/api/builds/{build_id}/run")
async def run_build(build_id: str):
    from app.builds.executor import BuildExecutor

    async def _run():
        try:
            await BuildExecutor(build_id).run()
        except MetisError as e:
            REPO.add_ui_event("build.failed", "ERROR", task_id=build_id, payload=e.to_dict())
            log.error_ctx("build failed", build_id=build_id, error=e.message)
        except Exception as e:  # noqa: BLE001
            REPO.add_ui_event("build.failed", "ERROR", task_id=build_id, payload={"error": str(e)[:300]})
            log.error_ctx("build crashed", build_id=build_id, error=str(e))

    TASKS[f"build_{build_id}"] = asyncio.create_task(_run())
    return {"build_id": build_id, "started": True}


@app.get("/api/builds/{build_id}/package/{path:path}")
async def package_file(build_id: str, path: str):
    from app.core.paths import final_dir

    p = (final_dir(build_id) / path).resolve()
    if not str(p).startswith(str(final_dir(build_id).resolve())) or not p.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(p)


# ---------------- browser (A6-A9) ----------------
@app.post("/api/browser/sessions")
async def new_browser_session(body: BrowserCreateSessionRequest):
    from app.browser.runtime import MANAGER

    sess = await MANAGER.new_session(body.task_label)
    if body.provider_id or body.task_id or body.download_job_id or body.access_job_id:
        sess.bind_task(
            provider_id=body.provider_id,
            task_id=body.task_id,
            access_job_id=body.access_job_id,
            download_job_id=body.download_job_id,
        )
    return {"session_id": sess.session_id, "state": sess.state, "owner": sess.owner}


@app.get("/api/browser/sessions")
async def browser_sessions():
    from app.browser.runtime import MANAGER

    return MANAGER.sessions()


@app.post("/api/browser/{action}")
async def browser_action(action: str, body: BrowserActionIn):
    from app.browser.runtime import MANAGER, LocatorTarget

    sess = MANAGER.get(body.session_id)
    tgt = None
    if body.target:
        tgt = LocatorTarget(**body.target)
    try:
        if action == "navigate":
            return await sess.navigate(body.url)
        if action == "back":
            return await sess.back()
        if action == "forward":
            return await sess.forward()
        if action == "click":
            return await sess.click(tgt)
        if action == "double_click":
            return await sess.double_click(tgt)
        if action == "type":
            return await sess.type_text(tgt, body.text or "", secret=body.secret)
        if action == "key":
            return await sess.press_key(body.key or "Enter")
        if action == "scroll":
            return await sess.scroll(body.dx, body.dy)
        if action == "select":
            return await sess.select_option(tgt, body.value or "")
        if action == "upload":
            return await sess.upload_file(tgt, body.file_path)
        if action == "new_tab":
            return await sess.new_tab(body.url)
        if action == "close_tab":
            return await sess.close_tab()
        if action == "switch_tab":
            return await sess.switch_tab(body.index or 0)
        if action == "read_dom":
            r = await sess.read_dom()
            r.pop("html", None)
            return r
        if action == "read_accessibility":
            return {"nodes": await sess.read_accessibility()}
        if action == "pause":
            sess.pause()
            return {"state": sess.state}
        if action == "resume":
            sess.resume()
            return {"state": sess.state}
        if action == "takeover":
            sess.take_over()
            return {"owner": sess.owner, "state": sess.state}
        if action == "return":
            return await sess.return_to_agent()
        if action == "screenshot":
            return {"image": await sess.screenshot()}
        raise HTTPException(400, f"unknown browser action {action}")
    except MetisError as e:
        return err(e)


@app.get("/api/browser/sessions/{session_id}/events")
async def browser_events(session_id: str):
    return REPO.list_browser_events(session_id)


@app.get("/api/browser/sessions/{session_id}/downloads")
async def browser_downloads(session_id: str):
    from app.browser.runtime import MANAGER

    return MANAGER.get(session_id).downloads


# ---------------- accounts / identity / vault (A10-A13) ----------------
@app.get("/api/identity")
async def get_identity():
    from app.auth.accounts import IDENTITY

    return IDENTITY.get_identity()


@app.put("/api/identity")
async def put_identity(body: IdentityIn):
    from app.auth.accounts import IDENTITY

    return IDENTITY.update_identity(body.updates, body.disabled_fields)


@app.get("/api/accounts")
async def accounts():
    return REPO.list_accounts()


@app.post("/api/accounts/{provider_id}/auto_register")
async def set_auto_register(provider_id: str, body: AutoRegisterIn):
    from app.auth.accounts import ACCOUNTS

    return ACCOUNTS.set_auto_register(provider_id, body.enabled)


@app.post("/api/accounts/bind")
async def bind_account(body: BindIn):
    from app.auth.accounts import ACCOUNTS
    from app.auth.vault import get_vault
    from app.domain.schemas import new_id

    ACCOUNTS.account_for(body.provider_id, create=True)
    vault_key = f"{body.provider_id}.credentials"
    get_vault().set_secret(vault_key, body.password)
    REPO.add_credential(new_id("cred"), body.provider_id, "password", body.account_label, vault_key)
    REPO.add_ui_event("auth.bound", payload={"provider": body.provider_id, "account": body.account_label})
    return {"bound": True, "provider_id": body.provider_id}


@app.delete("/api/accounts/{provider_id}")
async def delete_account(provider_id: str):
    from app.auth.accounts import ACCOUNTS

    return ACCOUNTS.delete_account(provider_id)


@app.get("/api/vault/keys")
async def vault_keys():
    from app.auth.vault import get_vault

    return {"keys": get_vault().list_keys()}  # never returns values


# ---------------- agent planning (P01-011) ----------------
class AgentPlanIn(BaseModel):
    text: str


class MeasurementPlanIn(BaseModel):
    concepts: list[dict]  # [{concept, role}]


class BuildPlanIn(BaseModel):
    requirement: dict
    assets: list[dict]


@app.post("/api/agent/requirements/plan")
async def agent_plan_requirement(body: AgentPlanIn):
    from app.agent.requirement_planner import plan_requirement

    plan, source = await plan_requirement(body.text)
    return {"plan": plan.model_dump(mode="json"), "source": source}


@app.post("/api/agent/measurements/plan")
async def agent_plan_measurements(body: MeasurementPlanIn):
    from app.agent.measurement_planner import plan_measurements

    plans = await plan_measurements(body.concepts)
    return {"plans": [p.model_dump(mode="json") for p in plans]}


@app.post("/api/agent/sources/plan")
async def agent_plan_sources(body: dict):
    from app.agent.measurement_planner import plan_measurements
    from app.agent.schemas import DataRequirementPlan, VariableMeasurementPlan
    from app.agent.source_planner import plan_queries, plan_sources

    req = DataRequirementPlan(**body["requirement"])
    raw_measurements = body.get("measurements")
    if raw_measurements:
        measurements = [VariableMeasurementPlan(**m) for m in raw_measurements]
    else:
        measurements = await plan_measurements([{"concept": v.concept, "role": v.role} for v in req.variables])
    source_plan, problems = await plan_sources(req, measurements)
    queries = await plan_queries(req, source_plan, measurements)
    return {
        "source_plan": source_plan.model_dump(mode="json"),
        "query_plans": [q.model_dump(mode="json") for q in queries],
        "policy_problems": problems,
    }


# ---------------- planning chain (Phase B: LLM planning as the search main chain) ----------------
class PlanningIn(BaseModel):
    text: str


@app.post("/api/agent/planning")
async def create_planning(body: PlanningIn):
    """Run the full planning chain (requirement → measurements → sources → queries),
    persist the bundle and return it. The returned planning_id drives /api/search/runs."""
    from app.agent.orchestrator import build_planning_bundle, save_bundle

    bundle = await build_planning_bundle(body.text)
    save_bundle(bundle, requirement_text=body.text)
    return {
        "planning_id": bundle.planning_id,
        "planning_source": bundle.planning_source,
        "bundle": bundle.model_dump(mode="json"),
    }


@app.get("/api/agent/planning")
async def list_plannings(limit: int = 20):
    return REPO.list_planning_runs(limit)


@app.get("/api/agent/planning/{planning_id}")
async def get_planning(planning_id: str):
    from app.agent.orchestrator import load_bundle

    bundle = load_bundle(planning_id)
    if not bundle:
        raise HTTPException(404, "planning not found")
    return bundle


# ---------------- account center: login/register APIs (P05-003/005) ----------------
class LoginIn(BaseModel):
    base_url: str | None = None  # for fixture/test providers with relative recipe URLs


class RegisterIn(BaseModel):
    register_url: str | None = None
    base_url: str | None = None


@app.post("/api/accounts/{provider_id}/login")
async def account_login(provider_id: str, body: LoginIn):
    """Drive the real login flow in the live browser, persist storage_state, resume pending access jobs."""
    from app.auth.accounts import LoginExecutor
    from app.auth.recipes import PROVIDER_RECIPES, resolve_url
    from app.browser.runtime import MANAGER, LocatorTarget

    recipe = PROVIDER_RECIPES.get(provider_id)
    if not recipe or "login" not in recipe:
        raise HTTPException(404, f"no login recipe for {provider_id}")
    base = body.base_url or get_settings().fixture_server

    class Driver:
        def __init__(self, session):
            self.browser_session = session

        async def open(self, url):
            await self.browser_session.navigate(url)

        async def fill(self, selector, value):
            await self.browser_session.type_text(LocatorTarget(css=selector), value, secret=("password" in selector))

        async def click(self, selector):
            await self.browser_session.click(LocatorTarget(css=selector))

        async def current_url(self):
            return self.browser_session.page.url

        async def body_text(self):
            return await self.browser_session.page.inner_text("body")

    session = await MANAGER.new_session(f"login:{provider_id}")
    driver = Driver(session)
    form = {"email": recipe["login"]["email"], "password": recipe["login"]["password"], "_submit": recipe["login"]["submit"]}
    result = await LoginExecutor(provider_id, driver).login(resolve_url(base, recipe["login_url"]), form)

    # P04-010 + Phase D: login success → AUTHORIZED → AUTO-RESUME the original download
    resumed = None
    acquisition = None
    if result["result"] == "SUCCESS":
        pending = [j for j in REPO.list_access_jobs(provider_id) if j["state"] in ("LOGGING_IN", "LOGIN_REQUIRED", "WAITING_USER", "SESSION_EXPIRED")]
        if pending:
            from app.access.executor import resume_after_user

            access_job = await resume_after_user(pending[0]["access_job_id"], "success")
            resumed = access_job.model_dump(mode="json")
            # Phase D: user must NOT click download twice — auto-resume acquisition
            if access_job.state == "AUTHORIZED" and access_job.download_job_id:
                from app.access.resume import RESUME_COORDINATOR

                try:
                    acquisition = await RESUME_COORDINATOR.resume_access_job(access_job.access_job_id)
                except Exception as e:  # noqa: BLE001 — surfaced to UI, download job already FAILED
                    acquisition = {"resumed": False, "error": str(e)[:200]}
    return {"result": result, "access_job": resumed, "acquisition": acquisition, "session_id": session.session_id}


@app.post("/api/accounts/{provider_id}/register")
async def account_register(provider_id: str, body: RegisterIn):
    """Drive ordinary self-service registration (only when the user enabled it)."""
    from app.auth.accounts import ACCOUNTS, RegistrationExecutor
    from app.auth.recipes import PROVIDER_RECIPES, resolve_url
    from app.browser.runtime import MANAGER, LocatorTarget

    recipe = PROVIDER_RECIPES.get(provider_id)
    if not recipe or "registration" not in recipe:
        raise HTTPException(404, f"no registration recipe for {provider_id}")
    if not ACCOUNTS.auto_register_allowed(provider_id):
        raise MetisError("REGISTRATION_BLOCKED", "auto registration is disabled for this provider")
    # P05-012 retry guard: max 3 registration attempts per provider
    attempts = [e for e in REPO.list_ui_events(200) if e["kind"] == "registration.submitted" and (e["payload"] or {}).get("provider") == provider_id]
    if len(attempts) >= 3:
        raise MetisError("REGISTRATION_BLOCKED", "registration retry limit reached for this provider")

    base = body.base_url or get_settings().fixture_server
    session = await MANAGER.new_session(f"register:{provider_id}")

    class Driver:
        browser_session = session

        async def open(self, url):
            await session.navigate(url)

        async def fill(self, selector, value):
            await session.type_text(LocatorTarget(css=selector), value, secret=("password" in selector))

        async def click(self, selector):
            await session.click(LocatorTarget(css=selector))

        async def current_url(self):
            return session.page.url

        async def body_text(self):
            return await session.page.inner_text("body")

    reg = recipe["registration"]
    form_map = {**reg["fields"], "_submit": reg["submit"]}
    ex = RegistrationExecutor(provider_id, Driver())
    result = await ex.run(resolve_url(base, reg["url"]), form_map, password_rules=recipe.get("password_policy"))
    return {**result, "session_id": session.session_id}


# ---------------- conversations (simple UI) ----------------
class ChatMessageIn(BaseModel):
    text: str


@app.post("/api/conversations/{cid}/messages")
async def conversation_message(cid: str, body: ChatMessageIn):
    """Single entry point: user message → intent → plan → search → acquire → result."""
    from app.agent.conversation_orchestrator import ConversationOrchestrator

    orch = ConversationOrchestrator()
    result = await orch.handle_message(cid, body.text)
    return {"conversation_id": cid, **result}


@app.post("/api/conversations")
async def create_conversation():
    import uuid
    return {"conversation_id": f"conv_{uuid.uuid4().hex[:12]}"}


# ---------------- events / health ----------------
@app.get("/api/events")
async def events(limit: int = 100):
    return REPO.list_ui_events(limit)


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}


# ---------------- projects / tasks (P24-001) ----------------
class ProjectIn(BaseModel):
    title: str


class TaskLinkIn(BaseModel):
    kind: str  # requirement|search_run|download_job|access_job|build
    ref_id: str = ""
    status: str = "OPEN"


class TaskStatusIn(BaseModel):
    status: str


@app.post("/api/projects")
async def create_project(body: ProjectIn):
    from app.domain.schemas import new_id

    pid = new_id("proj")
    REPO.upsert_project({"project_id": pid, "title": body.title})
    return REPO.get_project(pid)


@app.get("/api/projects")
async def list_projects():
    return REPO.list_projects()


@app.get("/api/projects/{pid}")
async def get_project_detail(pid: str):
    p = REPO.get_project(pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@app.post("/api/projects/{pid}/tasks")
async def add_project_task(pid: str, body: TaskLinkIn):
    if not REPO.get_project(pid):
        raise HTTPException(404, "project not found")
    return REPO.add_task(pid, body.kind, body.ref_id, body.status)


@app.patch("/api/tasks/{tid}")
async def patch_task(tid: str, body: TaskStatusIn):
    t = REPO.set_task_status(tid, body.status)
    if not t:
        raise HTTPException(404, "task not found")
    return t


# ---------------- agent chat (P25: deterministic core, answers only from real DB state) ----------------
class AgentChatIn(BaseModel):
    question: str
    task_id: str | None = None
    project_id: str | None = None
    action: dict | None = None  # proposed action; gated by requires_confirmation (P25-003), never executed here


CONFIRMABLE_KINDS = {"register_account", "delete_account", "allow_mm_join", "missing_policy_not_none"}


def requires_confirmation(action: dict) -> bool:
    """P25-003: destructive / policy-changing actions always need explicit user confirmation."""
    if not action:
        return False
    return action.get("kind") in CONFIRMABLE_KINDS


def _chat_progress(project_id: str | None = None) -> dict:
    """Summarize REAL pipeline state from the DB (ids quoted verbatim, nothing fabricated)."""
    evidence: list[str] = []
    parts: list[str] = []

    reqs = REPO.list_requirements()
    if reqs:
        req = reqs[0]
        rid = str(req.get("requirement_id", "?"))
        evidence.append(rid)
        tr = req.get("time_range")
        tr_txt = f"{tr[0]}—{tr[1]}" if isinstance(tr, (list, tuple)) and len(tr) == 2 else "未识别"
        assumptions = req.get("assumptions") or []
        unit = req.get("unit_of_analysis") or "未识别"
        parts.append(f"最近需求 {rid}：研究单位 {unit}，时间范围 {tr_txt}，假设 {len(assumptions)} 条")

    runs = REPO.list_search_runs()
    if runs:
        run = runs[0]
        tasks = REPO.list_provider_tasks(run["run_id"])
        done = sum(1 for t in tasks if t["status"] == "done")
        running = sum(1 for t in tasks if t["status"] in ("queued", "running"))
        results = sum(int(t.get("result_count") or 0) for t in tasks)
        evidence.append(run["run_id"])
        parts.append(f"最近搜索 {run['run_id']} 状态 {run['status']}：provider 任务 {done}/{len(tasks)} 完成、{running} 进行中，共 {results} 条结果")

    jobs = REPO.list_download_jobs()
    if jobs:
        dist: dict[str, int] = {}
        for j in jobs:
            st = str(j.get("status", "?"))
            dist[st] = dist.get(st, 0) + 1
        for j in jobs[:5]:
            if j.get("download_job_id"):
                evidence.append(str(j["download_job_id"]))
        dist_txt = "、".join(f"{k} {v}" for k, v in sorted(dist.items()))
        parts.append(f"下载任务 {len(jobs)} 个（{dist_txt}）")

    builds = REPO.list_builds()
    if builds:
        b = builds[0]
        bid = str(b.get("build_id", "?"))
        evidence.append(bid)
        parts.append(f"最近 Build {bid} 状态 {b.get('status', '?')}")

    if project_id:
        tasks = REPO.list_tasks(project_id)
        for t in tasks:
            evidence.append(t["task_id"])
        if tasks:
            detail = "、".join(f"{t['kind']}:{t['ref_id'] or t['task_id']}({t['status']})" for t in tasks)
            parts.append(f"项目 {project_id} 关联任务 {len(tasks)} 个：{detail}")

    answer = "当前进度（真实数据库状态）：" + "；".join(parts) if parts else "数据库中暂无需求 / 搜索 / 下载 / Build 记录。"
    return {"answer": answer, "evidence": evidence, "needs_confirmation": False}


def _chat_recommendation(question: str) -> dict:
    """Explain a recommendation from the most recent run that has candidates (title substring match)."""
    needle = question.replace("为什么推荐", "").replace("推荐理由", "").strip().lower().translate(str.maketrans("", "", "？?。.！!，,；;"))
    match = None
    fallback: list[dict] = []
    for run in REPO.list_search_runs():
        cands = REPO.list_candidates(run["run_id"])
        if not fallback:
            fallback = cands
        if not needle:
            continue
        for c in cands:
            if needle in str(c.get("title", "")).lower():
                match = (run, c)
                break
        if match:
            break
    if match:
        run, c = match
        rec = c.get("recommendation") or {}
        rec_txt = "、".join(f"{k} {float(v) * 100:.0f}" for k, v in rec.items() if isinstance(v, (int, float)) and v) or "无分项评分"
        reasons = [str(x) for x in (c.get("reasons") or [])]
        limitations = [str(x) for x in (c.get("limitations") or [])]
        unknowns = [str(x) for x in (c.get("unknowns") or [])]
        answer = (
            f"推荐《{c.get('title', '?')}》（{c.get('provider_id', '?')}，候选 {c.get('candidate_id', '?')}，来自搜索 {run['run_id']}）："
            f"推荐分项 {rec_txt}；理由：{'；'.join(reasons) or '无'}；限制：{'；'.join(limitations) or '无'}；未知：{'；'.join(unknowns) or '无'}。"
        )
        return {"answer": answer, "evidence": [str(e) for e in [c.get("candidate_id", ""), run["run_id"], *reasons] if e], "needs_confirmation": False}
    names = [str(c.get("title", "")) for c in fallback][:5]
    answer = "未找到与问题匹配的候选数据集。" + (f"当前可用候选：{'、'.join(names)}" if names else "数据库中还没有候选数据集。")
    return {"answer": answer, "evidence": [], "needs_confirmation": False}


def _chat_build_explain() -> dict:
    """Explain the most recent build's synthesis plan: keys / missing_policy / aggregations / operations."""
    builds = REPO.list_builds()
    if not builds:
        return {"answer": "数据库中还没有 Build，无法解释合成方案。", "evidence": [], "needs_confirmation": False}
    b = builds[0]
    bid = str(b.get("build_id", "?"))
    ops = REPO.list_build_operations(bid)
    keys = [str(k) for k in (b.get("keys") or [])]
    mp = str(b.get("missing_policy", "none"))
    aggs = b.get("aggregations") or []
    agg_txt = "、".join(f"{a.get('field', '?')}→{a.get('method', '?')}" for a in aggs) if aggs else "无"
    op_txt = " → ".join(str(o["operation_type"]) for o in ops) if ops else "尚无操作记录"
    answer = (
        f"Build {bid}（状态 {b.get('status', '?')}）的合成方案：键 {('/'.join(keys)) or '未设置'}；"
        f"缺失策略 missing_policy={mp}（none 表示含缺失的键组合不插补、不静默填充，缺失将显式保留）；"
        f"聚合：{agg_txt}；m:m 连接默认{'允许' if b.get('allow_mm_join') else '阻止'}；"
        f"操作序列：{op_txt}。"
    )
    return {"answer": answer, "evidence": [bid] + [str(o["operation_id"]) for o in ops[:5]], "needs_confirmation": False}


@app.post("/api/agent/chat")
async def agent_chat(body: AgentChatIn):
    """P25-003: a proposed confirmable action is NEVER executed — it is echoed back for user confirmation."""
    if body.action and requires_confirmation(body.action):
        kind = str(body.action.get("kind", ""))
        return {
            "answer": f"操作 {kind} 属于需确认动作（注册/删除账号、放宽 m:m 连接、非 none 缺失策略），需您确认后才会执行。",
            "evidence": [kind],
            "needs_confirmation": True,
            "confirm_action": body.action,
        }
    q = body.question or ""
    if "为什么推荐" in q or "推荐理由" in q:
        return _chat_recommendation(q)
    if "join" in q.lower() or "聚合" in q or "缺失" in q or "怎么合成" in q:
        return _chat_build_explain()
    return _chat_progress(body.project_id)  # progress / status questions + deterministic fallback


# ---------------- websocket event bus ----------------
CLIENTS: set[WebSocket] = set()


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    from app.events.bus import subscribe

    await ws.accept()
    q = subscribe()
    CLIENTS.add(ws)
    try:
        while True:
            event = await q.get()
            await ws.send_text(json.dumps(event, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(ws)


# ---------------- live browser stream (P02-002/003) ----------------
@app.websocket("/ws/browser/{session_id}")
async def ws_browser_stream(ws: WebSocket, session_id: str):
    """Binary-ish live view: JSON messages with JPEG frames + cursor/click/typing meta.

    Backpressure: a slow client never grows a queue — we measure send time and
    degrade frame rate; frames are dropped, never queued unboundedly.
    """
    from app.browser.runtime import MANAGER

    await ws.accept()
    session = MANAGER.get(session_id)
    interval = 1 / 15.0  # target 15 FPS
    try:
        while True:
            t0 = asyncio.get_event_loop().time()
            if await session.check_crashed():
                await ws.send_text(json.dumps({"t": "crashed"}))
                break
            frame = await session.get_frame()
            if not frame.get("alive"):
                break
            try:
                await ws.send_text(json.dumps({"t": "frame", **frame}))
            except Exception:  # noqa: BLE001 — client gone
                break
            # backpressure: if the send itself took longer than a frame budget, slow down
            elapsed = asyncio.get_event_loop().time() - t0
            await asyncio.sleep(max(interval - elapsed, interval * (elapsed > interval)))
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass


# ---------------- tab model (P02-010) ----------------
@app.get("/api/browser/sessions/{session_id}/tabs")
async def browser_tabs(session_id: str):
    from app.browser.runtime import MANAGER

    sess = MANAGER.get(session_id)
    tabs = []
    for i, page in enumerate(sess._pages):
        try:
            closed = page.is_closed()
        except Exception:  # noqa: BLE001
            closed = True
        tabs.append({"index": i, "active": i == sess._current, "closed": closed, "url": sess._safe_url() if page is sess.page else page.url, "title": "" if closed else await page.title()})
    return {"tabs": tabs}


# ---------------- static frontend ----------------
FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "static"
if FRONTEND.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND), html=True), name="ui")


@app.get("/")
async def index():
    index_file = FRONTEND / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Metis Data API</h1><p>UI not built. See /docs</p>")
