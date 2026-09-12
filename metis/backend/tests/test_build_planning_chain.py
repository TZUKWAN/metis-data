"""Phase H acceptance: the agent BuildPlan drives BuildExecutor (plan → config → COMPLETE).

Chain under test: plan_build_sync (deterministic, no LLM) → BuildExecutor.from_build_plan
→ executor.run(); plus target_unit-specific canonicalization (city-year) and the
NEEDS_REVIEW bookkeeping for aggregation method "none".
"""
from __future__ import annotations

import asyncio

import pandas as pd


def _register_fixture_artifacts(fixture_server) -> list[str]:
    """Register panel_data.csv + youth_unemployment.csv via MANAGER.http_download."""
    from app.db.repository import REPO
    from app.downloads.service import MANAGER

    specs = [
        ("fixture_a", "panel_data.csv", "world_bank_panel", "CC-BY-4.0"),
        ("fixture_b", "youth_unemployment.csv", "ilo_youth", "CC-BY-4.0"),
    ]
    artifact_ids = []
    for prov, fname, ref, lic in specs:
        job = MANAGER.create_job(prov, ref, f"{fixture_server}/data/{fname}", license=lic)
        asyncio.run(MANAGER.http_download(f"{fixture_server}/data/{fname}", job=job))
        art = next(a for a in REPO.list_artifacts() if a["download_job_id"] == job.download_job_id)
        artifact_ids.append(art["artifact_id"])
    return artifact_ids


def _country_assets(artifact_ids: list[str]) -> list[dict]:
    return [
        {
            "artifact_id": artifact_ids[0],
            "profile": {"columns": ["country_name", "iso3", "year", "gdp_per_capita"]},
            "variables": [{"canonical_name": "gdp_per_capita"}],
        },
        {
            "artifact_id": artifact_ids[1],
            "profile": {"columns": ["country", "country_code", "year", "youth_unemployment"]},
            "variables": [{"canonical_name": "youth_unemployment_rate"}],
        },
    ]


def test_plan_sync_then_from_build_plan_completes(temp_workspace, fixture_server):
    """requirement + assets → plan_build_sync → from_build_plan → run() → COMPLETE."""
    from app.agent.build_planner import plan_build_sync
    from app.builds.executor import BuildExecutor
    from app.db.repository import REPO

    artifact_ids = _register_fixture_artifacts(fixture_server)
    requirement = {"variables": {"outcomes": ["youth_unemployment_rate"]}}
    plan = plan_build_sync(requirement, _country_assets(artifact_ids))
    assert plan.entity_strategy == "country" and plan.time_strategy == "annual"
    assert plan.joins and plan.joins[0].keys == ["iso3", "year"]

    executor = BuildExecutor.from_build_plan(plan.model_dump(), title="planned youth panel", requirement_id="req_ph_h")
    cfg = REPO.get_build(executor.build_id)
    assert cfg is not None
    assert cfg["target_unit"] == "country"  # entity_strategy → target_unit
    assert cfg["keys"] == ["iso3", "year"]  # keys derived from plan joins
    assert [i["artifact_id"] for i in cfg["inputs"]] == artifact_ids
    assert cfg["plan_snapshot"]["entity_strategy"] == "country"  # plan stored verbatim
    assert cfg["plan_snapshot"]["joins"][0]["keys"] == ["iso3", "year"]

    result = asyncio.run(executor.run())
    assert result["status"] == "COMPLETE"
    after = REPO.get_build(executor.build_id)
    assert after["plan_snapshot"]  # snapshot survives the whole run
    ops = [o["operation_type"] for o in REPO.list_build_operations(executor.build_id)]
    assert "join" in ops and "entity_resolution" in ops


def test_from_build_plan_without_joins_derives_keys_and_completes(temp_workspace, fixture_server):
    """Single input, no join plan → keys derived from entity/time strategy."""
    from app.agent.build_planner import plan_build_sync
    from app.builds.executor import BuildExecutor
    from app.db.repository import REPO

    artifact_ids = _register_fixture_artifacts(fixture_server)
    plan = plan_build_sync({}, [{"artifact_id": artifact_ids[0], "profile": {"columns": ["country_name", "iso3", "year", "gdp_per_capita"]}, "variables": [{"canonical_name": "gdp_per_capita"}]}])
    assert not plan.joins  # single input → planner emits no join
    executor = BuildExecutor.from_build_plan(plan.model_dump(), title="single country panel")
    cfg = REPO.get_build(executor.build_id)
    assert cfg["keys"] == ["iso3", "year"]  # country+annual → iso3+year
    result = asyncio.run(executor.run())
    assert result["status"] == "COMPLETE"


def test_from_build_plan_aggregation_none_records_needs_review(temp_workspace):
    """method=none fields are skipped from execution and flagged NEEDS_REVIEW in plan_snapshot."""
    from app.builds.executor import BuildExecutor
    from app.db.repository import REPO

    plan = {
        "inputs": [],
        "entity_strategy": "country",
        "time_strategy": "annual",
        "joins": [],
        "aggregations": [{"field": "x", "method": "none"}],
        "missing_policy": [{"method": "linear"}],
    }
    executor = BuildExecutor.from_build_plan(plan, title="review probe")
    cfg = REPO.get_build(executor.build_id)
    assert cfg["aggregations"] == []  # method=none never becomes an executed aggregation
    assert cfg["missing_policy"] == "linear"  # missing_policy from plan[0].method
    flagged = [p for p in cfg["plan_snapshot"]["review_points"] if p.get("flag") == "NEEDS_REVIEW"]
    assert any(p.get("field") == "x" for p in flagged)


def test_from_build_plan_individual_strategy_keyless_append(temp_workspace):
    """entity_strategy=individual → no keys (append-only) + entity_resolution review point."""
    from app.builds.executor import BuildExecutor
    from app.db.repository import REPO

    plan = {"inputs": ["art_x", "art_y"], "entity_strategy": "individual", "time_strategy": "annual", "joins": [], "aggregations": []}
    executor = BuildExecutor.from_build_plan(plan, title="individual probe")
    cfg = REPO.get_build(executor.build_id)
    assert cfg["keys"] == []
    assert any(p.get("flag") == "NEEDS_REVIEW" and p.get("topic") == "entity_resolution" for p in cfg["plan_snapshot"]["review_points"])


def _city_probe_executor():
    from app.db.repository import REPO
    from app.domain.schemas import BuildConfig

    cfg = BuildConfig(title="city probe", inputs=[], target_unit="city", keys=["city_code", "year"])
    REPO.save_build(cfg)
    from app.builds.executor import BuildExecutor

    return BuildExecutor(cfg.build_id), cfg


def test_city_year_canon_key(temp_workspace):
    """city-year: _canon_key resolves 武汉→420100 / 成都→510100 (GB/T 2260) + integer year."""
    from app.builds.executor import BuildExecutor

    executor, cfg = _city_probe_executor()
    df = pd.DataFrame({"city": ["武汉", "武汉", "成都"], "year": ["2020", "2021-06", "2020Q3"], "value": [1.0, 2.0, 3.0]})
    out = BuildExecutor._canon_key(executor, df, cfg)
    assert out["city_code"].tolist() == ["420100", "420100", "510100"]
    assert out["year"].tolist() == [2020, 2021, 2020]  # YYYY / YYYY-MM / YYYYQ1 → int year
    assert "city_original" in out.columns  # originals preserved


def test_with_time_generalized_time_columns(temp_workspace):
    """_with_time recognizes period/date/quarter/month columns, not just 'year'."""
    from app.builds.executor import BuildExecutor

    executor, cfg = _city_probe_executor()
    df = pd.DataFrame({"city": ["武汉", "武汉"], "period": ["2020-03", "2021"], "value": [1.0, 2.0]})
    out = BuildExecutor._with_time(executor, df, cfg)
    assert "year" in out.columns and out["year"].tolist() == [2020, 2021]
    # idempotent
    out2 = BuildExecutor._with_time(executor, out, cfg)
    assert out2["year"].tolist() == [2020, 2021]
