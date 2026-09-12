"""Architecture invariants (P00-004/P01-005/P29-003). CI red on any regression."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / "metis" / "backend" / "app"
FRONTEND = ROOT / "metis" / "frontend" / "static"


def test_default_search_requires_planning():
    """前端默认搜索必须传 planning_id；不得只传 requirement_id。"""
    js = (FRONTEND / "app.js").read_text(encoding="utf-8")
    m = re.search(r'btn-search"\)\.onclick = async \(\) => \{(.*?)\n\};', js, re.S)
    assert m, "btn-search handler not found"
    body = m.group(1)
    assert "planning_id" in body, "default search must send planning_id"
    assert re.search(r'planning_id:\s*STATE\.planningId', body), "planning_id must come from STATE"


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
