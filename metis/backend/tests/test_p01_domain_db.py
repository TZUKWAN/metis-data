"""P01 acceptance: domain schemas, state machines, repository, recovery."""
from __future__ import annotations

import json

import pytest


def test_data_requirement_schema(temp_workspace):
    from app.domain.schemas import DataRequirement

    r = DataRequirement(
        raw_request="构建2015—2023年国家面板",
        unit_of_analysis="country",
        time_range=(2015, 2023),
        assumptions=["frequency=annual inferred by default"],
    )
    assert r.raw_request == "构建2015—2023年国家面板"  # original preserved
    assert json.loads(r.model_dump_json())["time_range"] == [2015, 2023]


def test_state_machines_transitions(temp_workspace):
    from app.core.errors import MetisError
    from app.domain.enums import ACCESS_FLOW, BUILD_FLOW, SEARCH_RUN_FLOW, assert_transition

    assert_transition(SEARCH_RUN_FLOW, "CREATED", "REQUIREMENT_PARSED", "search")
    with pytest.raises(MetisError):
        assert_transition(SEARCH_RUN_FLOW, "CREATED", "COMPLETED", "search")
    assert_transition(ACCESS_FLOW, "ACCESS_CHECK", "PUBLIC_DOWNLOAD", "access")
    with pytest.raises(MetisError):
        assert_transition(ACCESS_FLOW, "ACCESS_CHECK", "ACQUIRED", "access")
    assert_transition(BUILD_FLOW, "BUILD_CREATED", "INPUTS_READY", "build")
    with pytest.raises(MetisError):
        assert_transition(BUILD_FLOW, "BUILD_CREATED", "COMPLETE", "build")


def test_repository_roundtrip(temp_workspace):
    from app.db.repository import REPO
    from app.domain.schemas import (
        BuildConfig,
        DataRequirement,
        DatasetCandidate,
        DownloadJob,
        VariableSemantic,
    )

    rid = REPO.save_requirement(DataRequirement(raw_request="demo", unit_of_analysis="country"))
    got = REPO.get_requirement(rid)
    assert got["raw_request"] == "demo"

    run_id = "run_rt1"
    REPO.save_search_run(run_id, rid, "CREATED")
    REPO.transition_search_run(run_id, "REQUIREMENT_PARSED")
    assert REPO.get_search_run(run_id)["status"] == "REQUIREMENT_PARSED"
    with pytest.raises(Exception):
        REPO.transition_search_run(run_id, "COMPLETED")

    cand = DatasetCandidate(provider_id="world_bank", title="WDI")
    REPO.save_candidate(run_id, cand)
    REPO.upsert_provider_task("t1", run_id, "world_bank", "queued")
    REPO.finish_provider_task("t1", "done", result_count=3)
    tasks = REPO.list_provider_tasks(run_id)
    assert tasks[0]["status"] == "done" and tasks[0]["result_count"] == 3

    job = DownloadJob(provider_id="zenodo", dataset_ref="123", status="CREATED")
    jid = REPO.save_download_job(job)
    assert REPO.get_download_job(jid)["status"] == "CREATED"

    REPO.save_build(BuildConfig(title="panel", status="INPUTS_READY"))
    assert REPO.list_builds()[0]["title"] == "panel"

    REPO.save_variable_semantic(VariableSemantic(canonical_name="gdp_per_capita", unit="usd"))
    assert REPO.list_variable_semantics()[0]["canonical_name"] == "gdp_per_capita"


def test_build_transitions_persist(temp_workspace):
    from app.db.repository import REPO
    from app.domain.schemas import BuildConfig

    cfg = BuildConfig(title="t")
    REPO.save_build(cfg)
    REPO.transition_build(cfg.build_id, "INPUTS_READY")
    REPO.transition_build(cfg.build_id, "SCHEMA_ANALYSIS")
    assert REPO.get_build(cfg.build_id)["status"] == "SCHEMA_ANALYSIS"
    REPO.set_build_checkpoint(cfg.build_id, "SCHEMA_ANALYSIS", {"done": True})
    assert REPO.get_build(cfg.build_id)["stage_checkpoints"]["SCHEMA_ANALYSIS"]["done"] is True


def test_recovery_no_fake_complete(temp_workspace):
    """A35 core invariant: interrupted work never becomes COMPLETE; states stay truthful."""
    from app.db.recovery import reconcile_on_startup
    from app.db.repository import REPO
    from app.domain.schemas import BuildConfig, DownloadJob

    # a stuck search run
    REPO.save_search_run("run_s1", "req1", "SEARCHING")
    REPO.upsert_provider_task("pt1", "run_s1", "world_bank", "running")
    # a stuck download
    REPO.save_download_job(DownloadJob(provider_id="zenodo", dataset_ref="1", status="RUNNING"))
    # an in-flight build
    REPO.save_build(BuildConfig(title="b", status="JOIN"))

    report = reconcile_on_startup()

    assert report["search_runs_rescheduled"] == 1
    assert REPO.get_search_run("run_s1")["status"] == "PROVIDERS_SELECTED"
    tasks = REPO.list_provider_tasks("run_s1")
    assert tasks[0]["status"] == "cancelled"
    job = REPO.list_download_jobs()[0]
    assert job["status"] == "FAILED" and job["error_code"] == "DOWNLOAD_FAILED"
    b = REPO.get_build([b["build_id"] for b in REPO.list_builds()][0])
    assert b["status"] == "JOIN"  # stays at real stage, no fake COMPLETE
    assert b["stage_checkpoints"]["recovery"]["resumable"] is True
