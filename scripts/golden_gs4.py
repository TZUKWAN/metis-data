"""GS-4 登录平台 Golden：login → persist storage_state → restart → restore → acquire.

受控真实流程：fixture_site（本地自建测试站，需要账号登录）走完产品链：
绑定凭据 → 真实浏览器登录 → storage_state 入 Vault → 关闭浏览器 →
恢复 session → probe 仍登录 → 用恢复的 session 真实下载数据 → DownloadJob 校验。
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metis" / "backend"))
sys.path.insert(0, str(ROOT / "metis" / "backend" / "tests"))


async def main() -> int:
    from conftest import _free_port

    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=str(ROOT / "metis" / "backend" / "tests" / "fixtures"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base}/pages/index.html", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    ws = Path(tempfile.mkdtemp())
    import os

    os.environ["METIS_WORKSPACE_DIR"] = str(ws)
    os.environ["METIS_DB_URL"] = "sqlite:///" + ws.as_posix() + "/metis.db"
    from app.core.config import get_settings, reset_settings

    reset_settings()
    get_settings().ensure_dirs()
    from app.db.session import init_db

    init_db()

    report: dict = {"scenario": "GS-4 login persistence", "steps": {}, "started": time.time()}
    from app.auth.accounts import ACCOUNTS, LoginExecutor
    from app.auth.browser_state import ensure_valid_session, save_browser_state
    from app.auth.recipes import PROVIDER_RECIPES, resolve_url
    from app.auth.vault import get_vault
    from app.browser.runtime import MANAGER, LocatorTarget
    from app.db.repository import REPO
    from app.domain.enums import AccountStatusKind
    from app.domain.schemas import DownloadJob, new_id

    try:
        # 1) bind account (credentials → vault)
        aid = ACCOUNTS.account_for("fixture_site", create=True)
        get_vault().set_secret("fixture_site.credentials", "Corr3ct-Passw0rd!")
        REPO.add_credential(new_id("cred"), "fixture_site", "password", "researcher@example.edu", "fixture_site.credentials")
        report["steps"]["bind"] = "OK"

        # 2) real browser login
        sess1 = await MANAGER.new_session("gs4-login")

        class Driver:
            browser_session = sess1

            async def open(self, url):
                await sess1.navigate(url)

            async def fill(self, selector, value):
                await sess1.type_text(LocatorTarget(css=selector), value, secret=("password" in selector))

            async def click(self, selector):
                await sess1.click(LocatorTarget(css=selector))

            async def current_url(self):
                return sess1.page.url

            async def body_text(self):
                return await sess1.page.inner_text("body")

        recipe = PROVIDER_RECIPES["fixture_site"]
        form = {"email": recipe["login"]["email"], "password": recipe["login"]["password"], "_submit": recipe["login"]["submit"]}
        result = await LoginExecutor("fixture_site", Driver()).login(resolve_url(base, recipe["login_url"]), form)
        assert result["result"] == "SUCCESS" and result["storage_state_saved"] is True
        report["steps"]["login"] = "OK (storage_state persisted)"
        await sess1.close()

        # 3) restart → restore → probe
        sess2 = await MANAGER.new_session("gs4-restore")
        from app.auth.browser_state import restore_browser_storage, probe_session_valid

        assert await restore_browser_storage(sess2.context, "fixture_site")
        ok, reason = await probe_session_valid(sess2, "fixture_site", account_url=resolve_url(base, recipe["account_url"]))
        assert ok, reason
        report["steps"]["restore_probe"] = f"OK ({reason})"

        # 4) acquire with the restored session (real browser download + DownloadJob verify)
        from app.downloads.service import MANAGER

        job = MANAGER.create_job("fixture_site", "panel_data", f"{base}/data/panel_data.csv", license="CC0-1.0")
        MANAGER.attach_to_browser_session(job, sess2)
        await sess2.navigate(resolve_url(base, "/pages/downloads.html"))
        await sess2.click(LocatorTarget(role="link", name="Download"))
        await asyncio.sleep(1.5)
        results = await MANAGER.collect_browser_downloads(job, sess2)
        assert results and results[0]["sha256"]
        report["steps"]["acquire"] = f"OK ({results[0]['size']} bytes, sha256 verified)"
        REPO.upsert_account(aid, "fixture_site", status=AccountStatusKind.SESSION_VALID)

        report["result"] = "PASS"
    except Exception as e:  # noqa: BLE001
        report["result"] = "FAIL"
        report["error"] = f"{type(e).__name__}: {e}"[:400]
    finally:
        proc.terminate()

    report["duration_s"] = round(time.time() - report["started"], 1)
    out = ROOT / "metis" / "artifacts" / "golden_gs4_login.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GS-4: {report['result']} in {report['duration_s']}s")
    for k, v in report["steps"].items():
        print(f"  {k}: {v}")
    if "error" in report:
        print(f"  error: {report['error']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
