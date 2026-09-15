"""Architecture invariants (P00-004/P01-005/P29-003). CI red on any regression."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / "metis" / "backend" / "app"
FRONTEND = ROOT / "metis" / "frontend" / "static"


def test_resume_no_empty_context():
    """ResumeCoordinator 禁止固定空 access_context。"""
    src = (APP / "access" / "resume.py").read_text(encoding="utf-8")
    assert 'access_context' not in src or not re.search(r'access_context["\']?\s*[:=]\s*\{\}', src), \
        "resume.py must not hardcode empty access_context"


def test_production_download_via_acquisition():
    """生产下载路径必须走 ACQUISITION.acquire，禁止直接 adapter.acquire_dataset。"""
    api = (APP / "api" / "main.py").read_text(encoding="utf-8")
    m = re.search(r"async def create_download\(.*?(?=\n@app\.|\Z)", api, re.S)
    assert m and "ACQUISITION.acquire" in m.group(0), "/api/downloads must call ACQUISITION.acquire"
    assert "acquire_dataset" not in m.group(0), "/api/downloads must not call adapter.acquire_dataset directly"


def test_no_raw_write_in_adapters():
    for f in (APP / "providers" / "adapters").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "raw_root(" not in src and "raw_dataset_dir(" not in src and "os.replace" not in src, f"{f.name} writes raw"


def test_build_no_country_year_hardcode():
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    assert 'keys: ["country", "year"]' not in js, "frontend must not hardcode country/year keys"


def test_no_shell_true():
    for f in APP.rglob("*.py"):
        assert "shell=True" not in f.read_text(encoding="utf-8"), f"{f.name} uses shell=True"


def test_no_mediacrawler_dependency():
    for f in APP.rglob("*.py"):
        src = f.read_text(encoding="utf-8").lower()
        assert "mediacrawler" not in src, f"{f.name} references MediaCrawler"


def test_untrusted_content_guard_exists():
    guard = (APP / "acquisition" / "injection_guard.py")
    assert guard.exists() or (APP / "acquisition" / "policy.py").exists(), "injection guard module missing"


# ---------------- §25: conversational product invariants (CI red on regression) ----------------

def test_frontend_never_treats_candidate_id_as_artifact_id():
    """§25-1: the frontend may not feed a candidate id into the artifact preview API."""
    for js in FRONTEND.glob("js/*.js"):
        src = js.read_text(encoding="utf-8")
        assert "/api/artifacts/" not in src, f"{js.name} calls the internal artifact API — use /api/results/{{id}}/preview"
        assert "/api/search/runs" not in src, f"{js.name} reads global search runs — user chain must be conversation-scoped"


def test_result_ui_consumes_only_projected_fields():
    """§25-9/§14: results.js must not read Candidate raw schema fields."""
    import re as _re

    src = (FRONTEND / "js" / "results.js").read_text(encoding="utf-8")
    for forbidden in (r"candidate_id", r"time_coverage", r"provider_id", r"\.reason", r"license(?!_label)"):
        assert not _re.search(forbidden, src), f"results.js consumes raw candidate field '{forbidden}' — use ResultView fields only"


def test_download_button_uses_result_api():
    """§25-2/P0-04: the only frontend download path is POST /api/results/{id}/download."""
    src = (FRONTEND / "js" / "results.js").read_text(encoding="utf-8")
    assert "/api/results/" in src and "/download" in src, "download must call the result API"


def test_post_messages_returns_202_without_waiting():
    """§25-8/§12: the messages endpoint must not await the pipeline — 202 + background task."""
    src = (APP / "api" / "main.py").read_text(encoding="utf-8")
    m = re.search(r"async def conversation_message\(.*?(?=\nasync def |\n@app\.|\Z)", src, re.S)
    assert m, "conversation_message endpoint missing"
    body = m.group(0)
    assert "CTM.start(" in body or "create_task" in body, "pipeline must be scheduled in the background"
    assert "await ORCHESTRATOR_CONV.handle_message" not in body.split("CTM.start(")[-1].split("create_task")[-1], "endpoint must not await the pipeline"


def test_discover_and_download_is_not_text_only():
    """§25-3/P0-05: the discover+acquire path must invoke real acquisition."""
    src = (APP / "agent" / "conversation_orchestrator.py").read_text(encoding="utf-8")
    assert "ACQUISITION.acquire" in src, "acquire path never invokes acquisition — text-only stub"
    assert "_wait_for_user_then_acquire" in src, "auth-required acquire must create interventions"


def test_build_is_not_reply_only_stub():
    """§25-4/P0-06: BUILD must call BuildPlanner + BuildExecutor."""
    src = (APP / "agent" / "conversation_orchestrator.py").read_text(encoding="utf-8")
    assert "plan_build" in src and "BuildExecutor.from_build_plan" in src, "build path must invoke BuildPlanner/BuildExecutor"


def test_refine_keeps_previous_context():
    """§25-5/P0-08: refine must merge prior requirement text, not start fresh."""
    src = (APP / "agent" / "conversation_orchestrator.py").read_text(encoding="utf-8")
    m = re.search(r"async def _refine\(.*?(?=\n    async def |\n    # -{2,}|\Z)", src, re.S)
    assert m, "_refine missing"
    body = m.group(0)
    assert "latest_requirement" in body, "refine must load previous requirement from conversation context"


def test_explain_is_conversation_scoped():
    """§25-6/P0-09: explain may not use the global latest search run."""
    src = (APP / "agent" / "conversation_orchestrator.py").read_text(encoding="utf-8")
    m = re.search(r"async def _explain\(.*?(?=\n    @staticmethod|\n    # -{2,}|\Z)", src, re.S)
    assert m, "_explain missing"
    body = m.group(0)
    assert "list_search_runs" not in body, "explain must not read the global latest run — conversation links only"
    assert "list_result_links" in body


def test_auth_modal_probes_before_close():
    """§25-7/P0-14: the auth modal must POST resume (probe) and never close on click alone."""
    src = (FRONTEND / "js" / "auth-modal.js").read_text(encoding="utf-8")
    assert "/resume" in src, "auth modal must call the resume probe endpoint"
    assert re.search(r"RESOLVED[\s\S]{0,200}(root\.innerHTML|remove)", src), "modal may only close on a RESOLVED probe"


def test_pipeline_failure_converges_to_failed():
    """P0-11: the task supervisor must persist FAILED on any exception."""
    src = (APP / "agent" / "conversation_tasks.py").read_text(encoding="utf-8")
    assert 'state="FAILED"' in src, "supervisor must persist FAILED state"
    assert "except Exception" in src


def test_result_links_written_by_pipeline():
    """P0-10: the pipeline must create conversation_result_links (stable result ids)."""
    src = (APP / "agent" / "conversation_orchestrator.py").read_text(encoding="utf-8")
    assert "add_result_link" in src and "update_result_link" in src
    store = (APP / "ui" / "conversation_store.py").read_text(encoding="utf-8")
    assert 'state="READY", source_kind="artifact"' in src or ('source_kind="artifact"' in src and "READY" in src), "candidate→artifact transition must keep the same link"
