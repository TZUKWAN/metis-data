"""P10 acceptance: parser, selector, query plan, dedup, recommendation, orchestrator."""
from __future__ import annotations

import asyncio

import pytest


TEXT = "构建 2015—2023 年国家层面的青年失业率、人均 GDP、教育水平面板，优先使用官方或国际组织数据。"


def test_parse_golden_requirement():
    from app.search.parser import parse_requirement

    req = parse_requirement(TEXT)
    assert req.raw_request == TEXT  # original preserved
    assert req.unit_of_analysis == "country"
    assert req.time_range == (2015, 2023)
    assert req.frequency == "annual"
    assert any("annual" in a for a in req.assumptions)  # inference shown
    names = req.variables.all_named()
    assert "youth_unemployment_rate" in names
    assert "gdp_per_capita" in names
    assert "education_level" in names
    assert any(s in ("official", "international_org") for s in req.preferred_sources)
    # editable: mutation works and creates a different updated object
    req.time_range = (2016, 2022)
    assert req.time_range == (2016, 2022)


@pytest.mark.parametrize(
    "text,unit",
    [
        ("2018—2025 年大学生生成式 AI 使用情况，GPA 与学习投入", "individual"),
        ("中国省级面板 2010-2020 教育经费", "province"),
        ("firm-level productivity panel Europe", "firm"),
    ],
)
def test_parse_variants(text, unit):
    from app.search.parser import parse_requirement

    req = parse_requirement(text)
    assert req.unit_of_analysis == unit


def test_parse_time_since_and_conflicts():
    from app.search.parser import parse_requirement, validate_requirement
    from app.domain.schemas import DataRequirement

    r = parse_requirement("monthly unemployment since 2018")
    assert r.time_range[0] == 2018 and r.frequency == "monthly"
    bad = DataRequirement(raw_request="x", time_range=(2020, 2010), frequency="weekly")
    problems = validate_requirement(bad)
    assert any(p["code"] == "REQUIREMENT_CONFLICT" for p in problems)


def test_provider_selector_official_first(temp_workspace):
    from app.search.parser import parse_requirement
    from app.search.selector import select_providers

    req = parse_requirement(TEXT)
    picked = select_providers(req, max_providers=8)
    ids = [p.provider_id for p in picked]
    # official/international sources come before kaggle (community) — or kaggle absent
    if "kaggle" in ids:
        official_first = [i for i in ids if i in ("world_bank", "ilostat", "eurostat", "oecd", "us_census")]
        assert official_first and ids.index(official_first[0]) < ids.index("kaggle")
    assert picked[0].trust_class in ("international", "official", "academic")
    # excluded_sources hard-drop
    req.excluded_sources = ["world_bank"]
    assert "world_bank" not in [p.provider_id for p in select_providers(req, max_providers=12)]


def test_query_plan_per_provider(temp_workspace):
    from app.search.parser import parse_requirement
    from app.search.selector import plan_queries, select_providers

    req = parse_requirement(TEXT)
    providers = select_providers(req, max_providers=8)
    plan = plan_queries(req, providers)
    assert set(plan.keys()) == {p.provider_id for p in providers}
    joined = " | ".join(sum(plan.values(), []))
    assert "youth unemployment" in joined or "青年失业率" in joined


def test_dedup_doi_mirror_and_versions():
    from app.search.dedup import deduplicate, fuzzy_merge_review

    mk = lambda **kw: {  # noqa: E731
        "candidate_id": kw.get("id", "c"), "title": kw.get("t", ""), "doi": kw.get("doi"),
        "provider_id": kw.get("p", "x"), "version": kw.get("v"),
        "time_coverage": {"start": kw.get("y"), "end": kw.get("y"), "note": ""},
        "sources": kw.get("sources") or [{"provider_id": kw.get("p", "x"), "source_url": kw.get("u", "")}],
        "score": kw.get("s", 0), "reasons": [], "limitations": [], "unknowns": [],
    }
    c1 = mk(id="1", t="Panel A", doi="10.5281/zenodo.123", p="zenodo", u="https://zenodo.org/records/123")
    c2 = mk(id="2", t="Panel A", doi="https://doi.org/10.5281/ZENODO.123", p="harvard_dataverse", u="https://dataverse.harvard.edu/dvn/dv/xyz")
    c3 = mk(id="3", t="Panel A (v2, 2019)", p="zenodo", u="https://zenodo.org/records/999", v="v2", y="2019")
    c4 = mk(id="4", t="Panel A (v1, 2015)", p="zenodo", u="https://zenodo.org/records/888", v="v1", y="2015")
    groups = deduplicate([c1, c2, c3, c4])
    doi_group = next(g for g in groups if any(c["candidate_id"] == "1" for c in g))
    assert len(doi_group) == 2
    primary = next(c for c in doi_group if c.get("is_primary"))
    urls = {s["source_url"] for s in primary["sources"]}
    assert "https://dataverse.harvard.edu/dvn/dv/xyz" in urls  # mirror preserved, provenance kept
    # versions NOT merged by similar title
    assert not any({"3", "4"} <= {c["candidate_id"] for c in g} for g in groups)
    flags = fuzzy_merge_review(groups)
    assert flags and flags[0]["auto_merged"] is False


def test_recommend_honesty(temp_workspace):
    from app.search.recommend import evaluate_candidates

    requirement = {
        "variables": {"outcomes": ["youth_unemployment_rate"], "controls": ["gdp_per_capita"], "optional": []},
        "geography": ["global"], "time_range": (2015, 2023), "unit_of_analysis": "country",
        "trust_requirement": "official_first",
    }
    official_no_vars = {
        "candidate_id": "a", "title": "Population statistics", "provider_id": "world_bank",
        "license": "CC-BY-4.0", "access_mode": "PUBLIC_ANONYMOUS_API", "unit_of_analysis": "country",
        "geography": ["world"], "variable_hints": ["population"], "source_ref": "SP.POP",
        "time_coverage": {"start": "2015", "end": "2023", "note": ""}, "sources": [], "reasons": [], "limitations": [], "unknowns": [],
    }
    community_hit = {
        "candidate_id": "b", "title": "Youth unemployment rate dataset", "provider_id": "kaggle",
        "license": "UNKNOWN", "access_mode": "EXISTING_ACCOUNT", "requires_login": True,
        "unit_of_analysis": "country", "geography": ["world"], "variable_hints": ["youth unemployment rate"],
        "source_ref": "abc/xyz", "time_coverage": {"start": "2015", "end": "2023", "note": ""},
        "sources": [], "reasons": [], "limitations": [], "unknowns": [],
    }
    evaluated = evaluate_candidates([official_no_vars, community_hit], requirement)
    a = next(c for c in evaluated if c["candidate_id"] == "a")
    b = next(c for c in evaluated if c["candidate_id"] == "b")
    # official source missing core variables is penalized, not masked
    assert any("no required variable evidence" in l or "no evidence" in u for l in a["limitations"] for u in a["unknowns"])
    # UNKNOWN license treated as not open
    assert any("NOT open" in u or "UNKNOWN" in u for u in b["unknowns"])
    assert any("not an official" in l for l in b["limitations"])


def test_orchestrator_isolation(temp_workspace, monkeypatch):
    """A3: one provider 500/timeout doesn't fail the run; statuses visible; history persisted."""
    from app.db.repository import REPO
    from app.domain.enums import SearchRunStatus
    from app.search.orchestrator import ORCHESTRATOR

    class Boom:
        provider_id = "world_bank"

        async def search_datasets(self, q, filters=None, limit=10):
            raise RuntimeError("simulated 500")

    class Slow:
        provider_id = "data_gov_uk"

        async def search_datasets(self, q, filters=None, limit=10):
            await asyncio.sleep(120)
            return []

    class Good:
        provider_id = "opendata_swiss"

        async def search_datasets(self, q, filters=None, limit=10):
            from app.providers.adapters.common import mk_candidate

            return [mk_candidate(provider_id="opendata_swiss", title="Arbeitslose", source_url="https://opendata.swiss/x", source_ref="xyz")]

    import app.search.orchestrator as orch

    monkeypatch.setattr(orch, "get_adapter", lambda pid: {"world_bank": Boom(), "data_gov_uk": Slow(), "opendata_swiss": Good()}[pid])

    requirement = {"requirement_id": "req_iso", "raw_request": TEXT}
    run_id = asyncio.run(
        ORCHESTRATOR.run_search(requirement, ["world_bank", "data_gov_uk", "opendata_swiss"], {"world_bank": ["unemployment"], "data_gov_uk": ["unemployment"], "opendata_swiss": ["arbeitslose"]}, run_id="run_iso1")
    )
    tasks = {t["provider_id"]: t for t in REPO.list_provider_tasks(run_id)}
    assert tasks["world_bank"]["status"] == "error"
    assert tasks["data_gov_uk"]["status"] == "timeout"
    assert tasks["opendata_swiss"]["status"] == "done" and tasks["opendata_swiss"]["result_count"] >= 1
    assert REPO.get_search_run(run_id)["status"] == SearchRunStatus.COMPLETED
    cands = REPO.list_candidates(run_id)
    assert cands and cands[0]["provider_id"] == "opendata_swiss"  # real provider preserved
    # cancel path
    run2 = asyncio.run(ORCHESTRATOR.run_search(requirement, ["world_bank"], {"world_bank": ["x"]}, run_id="run_iso2"))
    assert run2 == "run_iso2"
    history = REPO.list_search_runs()
    assert any(r["run_id"] == run_id for r in history)
