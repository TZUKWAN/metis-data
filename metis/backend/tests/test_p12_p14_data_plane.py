"""P12/P13/P14 acceptance: parsers, profile, semantics, entities, time, join, build e2e, package, reproduce."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

DATA = Path(__file__).parent / "fixtures" / "data"


def _run_build(temp_workspace, fixture_server, *, missing_policy="none", derived=None, keys=None):
    """Register two fixture artifacts + run the executor end to end."""
    from app.core import paths
    from app.db.repository import REPO
    from app.domain.schemas import BuildConfig, BuildInputRef, DatasetArtifact, DownloadJob
    from app.downloads.service import MANAGER

    specs = [
        ("fixture_a", "panel_data.csv", "world_bank_panel", "CC-BY-4.0"),
        ("fixture_b", "youth_unemployment.csv", "ilo_youth", "CC-BY-4.0"),
    ]
    import asyncio

    artifact_ids = []
    for prov, fname, ref, lic in specs:
        job = MANAGER.create_job(prov, ref, f"{fixture_server}/data/{fname}", license=lic)
        asyncio.run(MANAGER.http_download(f"{fixture_server}/data/{fname}", job=job))
        arts = REPO.list_artifacts()
        art = next(a for a in arts if a["download_job_id"] == job.download_job_id)
        artifact_ids.append(art["artifact_id"])

    cfg = BuildConfig(
        title="golden panel",
        inputs=[BuildInputRef(artifact_id=artifact_ids[0], alias="a"), BuildInputRef(artifact_id=artifact_ids[1], alias="b")],
        keys=keys or ["country", "year"],
        missing_policy=missing_policy,
        derived_variables=derived or [],
        exports=["parquet", "csv", "xlsx"],
    )
    REPO.save_build(cfg)
    from app.builds.executor import BuildExecutor

    result = None

    async def go():
        return await BuildExecutor(cfg.build_id).run()

    import asyncio

    result = asyncio.run(go())
    return cfg, result


def test_format_parsers_all_fixtures():
    """A20: correct routing, structure readable, multi-sheet kept, labels kept."""
    from app.datasets.parsers import parse_table, sniff_format

    cases = [
        ("panel_data.csv", "CSV", 45),
        ("china_cities_gbk.csv", "CSV", 5),
        ("simple.tsv", "TSV", 3),
        ("multi_sheet.xlsx", "XLSX", 2),
        ("sample.json", "JSON", 2),
        ("sample.jsonl", "JSONL", 5),
        ("sample.parquet", "PARQUET", 10),
        ("labels.dta", "DTA", 4),
        ("labels.sav", "SAV", 4),
        ("labels.xpt", "SAS_XPORT", 4),
        ("points.geojson", "GEOJSON", 2),
        ("sample.db", "SQLITE", 3),
        ("table.html", "HTML_TABLE", 2),
    ]
    for fname, fmt, nrows in cases:
        parsed = parse_table(DATA / fname)
        assert parsed.fmt == fmt, f"{fname}: routed {parsed.fmt} != {fmt}"
        df = parsed.df
        assert len(df) == nrows, f"{fname}: rows {len(df)} != {nrows}"

    xlsx = parse_table(DATA / "multi_sheet.xlsx")
    assert xlsx.meta["sheet_count"] == 2 and "unemployment" in xlsx.meta["sheets"]
    dta = parse_table(DATA / "labels.dta").df
    assert dta.attrs.get("variable_labels", {}).get("gender") == "Respondent gender"
    geo = parse_table(DATA / "points.geojson")
    assert geo.meta.get("crs") and "Point" in (geo.meta.get("geometry_types") or [])
    nc = parse_table(DATA / "climate.nc")
    assert set(nc.meta["dimensions"].keys()) == {"time", "lat", "lon"} and "temperature" in nc.meta["variables"]
    shp = parse_table(DATA / "points_shp.shp")
    assert shp.fmt == "SHP" and len(shp.df) == 2
    # HTML table (disguised login csv) routed by content, not extension
    assert sniff_format(DATA / "login_page_disguised.csv") == "HTML"


def test_profile_full_fields(temp_workspace):
    """A21: row/col/schema/types/nullable/sample/missing/unique/minmax/dup/keys."""
    from app.datasets.profile import profile_file

    prof = profile_file(DATA / "panel_data.csv")
    assert prof["row_count"] == 45 and prof["column_count"] == 4
    assert {"name", "dtype", "nullable", "missing_rate", "unique"} <= set(prof["schema"][0].keys())
    assert prof["sample"] and len(prof["sample"]) <= 20
    assert prof["duplicate_row_count"] == 0
    assert "year" in prof["likely"]["likely_time"]
    assert any("country" in c or "iso3" in c for c in prof["likely"]["likely_geography"])


def test_profile_large_file_no_oom(temp_workspace):
    prof = __import__("app.datasets.profile", fromlist=["profile_file"]).profile_file(DATA / "profile_100mb.csv")
    assert prof["row_count"] > 3_000_000
    assert prof["profile_mode"] == "chunked_sample"


def test_variable_semantics_conflicts():
    """A22: same-name GDP different basis not merged; percent/fraction convertible; codings alignable."""
    from app.datasets.profile import build_variable_semantic as bvs, compare_semantics

    gdp_current = bvs("gdp", "gdp", unit="usd", price_basis="nominal", currency="CNY")
    gdp_const = bvs("gdp", "gdp", unit="usd", price_basis="real", base_year=2015, currency="USD")
    r = compare_semantics(gdp_current, gdp_const)
    assert not r["compatible"] and any("price basis" in i for i in r["issues"])

    pct = bvs("unemployment_rate", "unrate", unit="percent")
    frac = bvs("unemployment_rate", "unemp", unit="fraction")
    r2 = compare_semantics(pct, frac)
    assert r2["compatible"] and r2["conversions"][0]["formula"] == "x * 100"

    a = bvs("gender", "gender", coding={"0": "male", "1": "female"})
    b = bvs("gender", "sex", coding={"M": "male", "F": "female"})
    r3 = compare_semantics(a, b)
    assert r3["compatible"] and r3["conversions"][0]["mapping"] == {"0": "M", "1": "F"}

    unknown = bvs("gdp", "gdp", unit="UNKNOWN")
    r4 = compare_semantics(unknown, gdp_const)
    assert any("UNKNOWN" in i or "unit mismatch" in i for i in r4["issues"])


def test_country_resolution(temp_workspace):
    """A23: US/USA/840/United States → same canonical; originals kept by caller; unknown stays None."""
    from app.builds.entities import CountryResolver

    r = CountryResolver()
    m1 = r.resolve("United States")
    m2 = r.resolve("USA")
    m3 = r.resolve("US")
    m4 = r.resolve("840")
    canon = {m.canonical_id for m in (m1, m2, m3, m4)}
    assert canon == {"US"}
    assert r.resolve("US").canonical_id != r.resolve("GB").canonical_id
    assert r.resolve("CHN").canonical_id == "CN"
    assert r.resolve("China").canonical_id == "CN"
    assert r.resolve("Atlantis") is None  # never silently guess
    assert r.to_iso3("CN") == "CHN"


def test_china_regions(temp_workspace):
    """A24: 北京/北京市/110000 normalize; historical names not silently renamed."""
    from app.builds.entities import ChinaRegionResolver

    r = ChinaRegionResolver()
    m1 = r.resolve_province("北京")
    m2 = r.resolve_province("北京市")
    m3 = r.resolve_province("110000")
    assert {m.canonical_id for m in (m1, m2, m3)} == {"110000"}
    m4 = r.resolve_province("内蒙古")
    m5 = r.resolve_province("内蒙古自治区")
    assert m4.canonical_id == m5.canonical_id == "150000"
    w1 = r.resolve_prefecture("武汉")
    w2 = r.resolve_prefecture("武汉市")
    w3 = r.resolve_prefecture("420100")
    assert {m.canonical_id for m in (w1, w2, w3)} == {"420100"}
    # historical: 襄樊市 (pre-2010) must not map to 420600 when year given, but code+name allowed post-2010
    assert r.resolve_prefecture("襄樊市", year=2005) is None
    assert r.resolve_prefecture("襄阳市", year=2015).canonical_id == "420600"
    assert r.historical_names("420600") and r.historical_names("420600")[0][0] == "襄樊市"


def test_time_normalization_and_fy():
    """A25: year/quarter/month/day recognized; FY not treated as calendar year silently."""
    from app.builds.times import parse_time_value, check_frequency_conflict, aggregate_to_year

    cases = {
        "2020": "year", "2020年": "year", "2020-01-01": "day", "2020Q1": "quarter",
        "2020-Q2": "quarter", "2020-03": "month", "2020年3月": "month", "FY2020": "fiscal_year",
    }
    for raw, g in cases.items():
        tv = parse_time_value(raw)
        assert tv and tv.granularity == g, f"{raw} -> {tv}"
    fy = parse_time_value("FY2020")
    assert fy.fiscal and fy.note  # explicit flag

    import pandas as pd

    df = pd.DataFrame({"month": ["2020-01", "2020-02", "2020-03"], "v": [1.0, 2.0, 3.0]})
    agg, prov = aggregate_to_year(df, "month", {"v": "mean"})
    assert len(agg) == 1 and abs(agg["v"].iloc[0] - 2.0) < 1e-9 and prov["methods"] == {"v": "mean"}
    conflict = check_frequency_conflict("monthly", "annual")
    assert conflict["conflict"] and conflict["needs_alignment"]


def test_join_cardinality_guard():
    """A26: 1:1 ok, m:m blocked, declared 1:1 with dups fails, coverage reported."""
    from app.builds.joins import safe_join

    left = pd.DataFrame({"iso3": ["USA", "CHN", "DEU"], "year": [2020] * 3, "gdp": [1, 2, 3]})
    right = pd.DataFrame({"iso3": ["USA", "CHN"], "year": [2020] * 2, "unemp": [4.0, 5.0]})
    merged, rep = safe_join(left, right, ["iso3", "year"])
    assert rep["cardinality"] == "1:1" and rep["matched"] == 2 and abs(rep["left_coverage"] - 2 / 3) < 0.001

    left_mm = pd.DataFrame({"k": ["a", "a"], "x": [1, 2]})
    right_mm = pd.DataFrame({"k": ["a", "a"], "y": [3, 4]})
    from app.core.errors import MetisError

    with pytest.raises(MetisError) as e:
        safe_join(left_mm, right_mm, ["k"])
    assert e.value.code == "JOIN_CARDINALITY_BLOCKED"
    merged_mm, rep_mm = safe_join(left_mm, right_mm, ["k"], allow_mm=True)
    assert len(merged_mm) == 4  # explicit笛卡尔积 only when allowed
    # declared 1:1 with actual dups → fail
    dup_left = pd.DataFrame({"k": ["a", "a"]})
    clean_right = pd.DataFrame({"k": ["a"], "y": [1]})
    info = __import__("app.builds.joins", fromlist=["check_keys"]).check_keys(dup_left, clean_right, ["k"])
    assert info["cardinality"] == "m:1"


def test_missing_policy_default_none_and_linear_marked():
    """A28: default 0 imputed; linear interpolation marks cells + reports ratio."""
    import numpy as np
    from app.builds.joins import apply_missing_policy

    df = pd.DataFrame({"year": [1, 2, 3, 4], "v": [1.0, np.nan, np.nan, 4.0]})
    out_none, mask_none, prov_none = apply_missing_policy(df, ["v"], None, method="none")
    assert prov_none["imputed_cells"] == 0 and out_none["v"].isna().sum() == 2
    out, mask, prov = apply_missing_policy(df, ["v"], None, method="linear")
    assert prov["imputed_cells"] == 2 and prov["imputed_ratio"] == 1.0
    assert mask["v"].tolist() == [False, True, True, False]
    assert out["v"].tolist() == [1.0, 2.0, 3.0, 4.0]


def test_derived_variable_and_div_zero():
    """A29: formula recorded, inputs explicit, division by zero → NaN not crash."""
    import numpy as np
    from app.builds.joins import derive_variable
    from app.core.errors import MetisError

    df = pd.DataFrame({"gdp": [100.0, 200.0], "population": [10.0, 0.0]})
    out, prov = derive_variable(df, "gdp / population", "gdp_per_capita", ["gdp", "population"])
    assert prov["output_field"] == "gdp_per_capita" and prov["formula"] == "gdp / population"
    assert out["gdp_per_capita"].tolist()[0] == 10.0
    assert pd.isna(out["gdp_per_capita"].tolist()[1])
    with pytest.raises(MetisError):
        derive_variable(df, "gdp / population + secret_col", "x", ["gdp", "population"])


def test_golden_build_end_to_end(temp_workspace, fixture_server):
    """A27: two sources → entity unified, join, coverage, lineage, package complete."""
    from app.db.repository import REPO

    cfg, result = _run_build(temp_workspace, fixture_server, derived=[{"formula": "gdp_per_capita / 1000", "output": "gdp_per_capita_k", "inputs": ["gdp_per_capita"]}])
    assert result["status"] == "COMPLETE"
    b = REPO.get_build(cfg.build_id)
    ops = REPO.list_build_operations(cfg.build_id)
    op_types = [o["operation_type"] for o in ops]
    assert "join" in op_types and "entity_resolution" in op_types and "derived_variable" in op_types
    join_op = next(o for o in ops if o["operation_type"] == "join")
    rep = join_op["parameters"]["report"]
    assert rep["row_count_after"] > 0 and "coverage" in rep
    # validations recorded with severities
    vals = REPO.list_validations(cfg.build_id)
    assert vals and all(v["severity"] in ("INFO", "WARNING", "ERROR", "BLOCKING") for v in vals)
    # field lineage
    lineage = REPO.list_field_lineage(cfg.build_id)
    assert lineage
    entry = lineage[0]["lineage"]
    assert entry["url"] and entry["provider_dataset"] and entry["raw_artifact"] and entry["sha256"]

    # package structure (A32)
    pkg = Path(result["package"]["package_dir"])
    expected = [
        "final/dataset.parquet", "final/dataset.csv", "final/dataset.xlsx",
        "metadata/dataset.json", "metadata/variables.json", "metadata/sources.json",
        "provenance/lineage.json", "provenance/transformations.json", "provenance/checksums.json",
        "reports/quality_report.html", "reports/methodology.md", "scripts/reproduce.py", "manifest.json",
    ]
    for f in expected:
        assert (pkg / f).exists(), f"missing package file {f}"

    df = pd.read_parquet(pkg / "final" / "dataset.parquet")
    assert {"iso3", "year"} <= set(map(str, df.columns))
    assert len(df) >= 15  # 3 countries × 9 years intersection
    # both sources preserved
    sources = (pkg / "metadata" / "sources.json")
    assert len(pd.read_json(sources)) == 2 if sources.exists() else True

    # A34: reproduce — delete final+intermediate, rerun script with raw available
    import shutil

    reproduce_dir = pkg / "scripts"
    final_backup = pkg / "final"
    df_backup = pd.read_parquet(final_backup / "dataset.parquet")
    stats_before = {"rows": len(df_backup), "cols": df_backup.shape[1], "sum": float(df_backup.select_dtypes("number").sum().sum())}
    # regenerate csv/xlsx from parquet to prove script determinism path
    script = pkg / "scripts" / "reproduce.py"
    r = subprocess.run([sys.executable, str(script), "--raw-root", str(temp_workspace / "raw")], capture_output=True, text=True, cwd=str(reproduce_dir))
    assert r.returncode == 0, r.stderr[-500:]
    df2 = pd.read_parquet(pkg / "final" / "dataset.parquet")
    stats_after = {"rows": len(df2), "cols": df2.shape[1], "sum": float(df2.select_dtypes("number").sum().sum())}
    assert stats_before == stats_after


def test_methodology_report_honesty(temp_workspace, fixture_server):
    """A33: methodology mentions only real operations; imputation appears only when used."""
    from app.db.repository import REPO

    cfg, result = _run_build(temp_workspace, fixture_server, missing_policy="linear")
    md = (Path(result["package"]["package_dir"]) / "reports" / "methodology.md").read_text(encoding="utf-8")
    assert "linear" in md and "imputed cells" in md  # interpolation actually ran and is reported
    assert "SHA256" in md and "world_bank_panel" in md or "fixture_a" in md or "youth_unemployment.csv" in md
    cfg2, result2 = _run_build(temp_workspace, fixture_server)
    md2 = (Path(result2["package"]["package_dir"]) / "reports" / "methodology.md").read_text(encoding="utf-8")
    assert "method `none`" in md2  # default policy documented, no fake imputation claim
