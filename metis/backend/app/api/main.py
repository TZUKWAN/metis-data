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
    requirement_id: str
    provider_ids: list[str] | None = None
    max_providers: int = 8


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
@app.post("/api/search/runs")
async def start_search(body: SearchRunIn):
    from app.search.orchestrator import ORCHESTRATOR
    from app.search.selector import plan_queries, select_providers

    req = REPO.get_requirement(body.requirement_id)
    if not req:
        raise HTTPException(404, "requirement not found")
    from app.domain.schemas import DataRequirement

    req_obj = DataRequirement(**req)
    if body.provider_ids:
        from app.providers.registry import get_registry

        providers = [get_registry().get(p) for p in body.provider_ids]
    else:
        providers = select_providers(req_obj, max_providers=body.max_providers)
    provider_ids = [p.provider_id for p in providers]
    plan = plan_queries(req_obj, providers)
    run_id = await ORCHESTRATOR.run_search(req, provider_ids, plan)
    return {"run_id": run_id, "providers": provider_ids, "query_plan": plan}


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
    from app.downloads.service import MANAGER

    job = MANAGER.create_job(body.provider_id, body.dataset_ref, body.source_url, dataset_title=body.dataset_title, version=body.version, license=body.license, access_mode=body.access_mode)

    async def _run():
        from app.providers.base import get_adapter

        adapter = get_adapter(body.provider_id)

        staging = Path(get_settings().workspace_dir) / "downloads" / job.download_job_id
        staging.mkdir(parents=True, exist_ok=True)
        files = await adapter.acquire_dataset(body.dataset_ref, staging, {})
        # commit through verification & raw registration
        job2 = REPO.get_download_job(job.download_job_id)
        job2["status"] = "VERIFYING"
        REPO.save_download_job(job2)
        from app.downloads.service import MANAGER as M

        for f in files:
            await M._verify_and_commit(Path(f), job2, Path(f).stat().st_size)

    TASKS[job.download_job_id] = asyncio.create_task(_run())
    return job.model_dump(mode="json")


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
    from app.agent.source_planner import plan_queries, plan_sources
    from app.agent.schemas import DataRequirementPlan, VariableMeasurementPlan

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


# ---------------- events / health ----------------
@app.get("/api/events")
async def events(limit: int = 100):
    return REPO.list_ui_events(limit)


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}


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
