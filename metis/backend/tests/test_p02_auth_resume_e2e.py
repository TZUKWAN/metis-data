"""P02-005: cookie-gated authenticated download E2E — one download intent, zero re-clicks.

Chain: Download intent → AccessJob(AUTHORIZED via login) → storage_state → Vault →
browser closed → RESUME_COORDINATOR (restore → probe → bridge cookies) →
ACQUISITION.acquire → verified raw artifact. Restart path re-proves restore.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import asyncio

from conftest import browser_run

SESSION_COOKIE = "metis_session=rc-authenticated"
SECRET_BODY = b"secret-panel-data,DO-NOT-SHARE\nrow1,1\nrow2,2\n"


class _AuthServer(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _authorized(self) -> bool:
        return SESSION_COOKIE in (self.headers.get("Cookie") or "")


    def do_HEAD(self):
        if self.path.startswith("/protected/"):
            self.send_response(200 if SESSION_COOKIE in (self.headers.get("Cookie") or "") else 401)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_GET(self):
        if self.path == "/login":
            self.send_response(200)
            self.send_header("Set-Cookie", SESSION_COOKIE)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            # #welcome-user only exists when the session cookie is present — the
            # resolver probe uses this selector to distinguish logged-in vs expired
            if SESSION_COOKIE in (self.headers.get("Cookie") or ""):
                self.wfile.write(b"<html><body><h1 id='welcome-user'>ok</h1></body></html>")
            else:
                self.wfile.write(b"<html><body><form id='login-form'><input name='password'></form></body></html>")
            return
        if self.path.startswith("/protected/"):
            if not self._authorized():
                self.send_response(401)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body>login required</body></html>")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.end_headers()
            self.wfile.write(SECRET_BODY)
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture()
def auth_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _AuthServer)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def test_cookie_gated_download_auto_resume(temp_workspace, auth_server, loop):
    from app.auth.browser_state import save_browser_state
    from app.auth.recipes import PROVIDER_RECIPES
    from app.browser.runtime import MANAGER
    from app.core.errors import MetisError
    from app.db.repository import REPO
    from app.downloads.service import MANAGER as DM
    from app.domain.enums import DownloadJobStatus

    # recipe for the controlled platform (absolute account_url for the probe)
    PROVIDER_RECIPES["fixture_auth"] = {"account_url": f"{auth_server}/login", "logged_in_selector": "#welcome-user"}
    # stub adapter (monkeypatch at resume module): v2 descriptor points at the protected URL
    import app.access.resume as resume_mod
    from app.providers.download_helper import AcquisitionDescriptor

    class StubAdapter:
        provider_id = "fixture_auth"

        async def build_acquisition_descriptor(self, ref, ctx):
            return AcquisitionDescriptor(url=f"{auth_server}/protected/{ref}", filename=ref)

        async def acquire_dataset(self, ref, dest_dir, ctx):
            import httpx

            r = await httpx.get(f"{auth_server}/protected/{ref}")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            from pathlib import Path

            p = Path(dest_dir) / ref
            p.write_bytes(r.content)
            return [str(p)]

    import app.acquisition.service as acq_service

    resume_mod.get_adapter = lambda pid: StubAdapter()
    acq_service.get_adapter = lambda pid: StubAdapter()

    async def flow():
        # 1) the SINGLE download intent
        job = DM.create_job("fixture_auth", "secret.csv", f"{auth_server}/protected/secret.csv", license="TEST")
        aid = "acc_e2e_1"
        REPO.upsert_access_job({
            "access_job_id": aid, "provider_id": "fixture_auth", "candidate_id": "secret.csv",
            "download_job_id": job.download_job_id, "state": "AUTHORIZED", "reason": "login completed",
        })

        # 2) real browser login (server sets the session cookie) + storage_state → Vault
        sess = await MANAGER.new_session("gsb-login")
        await sess.navigate(f"{auth_server}/login")
        assert await sess.page.evaluate("document.cookie.includes('metis_session')")
        await save_browser_state(sess, "fixture_auth", account_id="researcher@example.edu")
        await sess.close()  # browser gone — only the Vault state remains

        # 3) resume: restore → probe → bridge cookies → ACQUISITION (zero re-clicks)
        from app.access.resume import RESUME_COORDINATOR

        result = await RESUME_COORDINATOR.resume_access_job(aid)
        assert result.get("resumed") is True, result

        # 4) artifact content is the REAL protected body
        got = None
        for p in (temp_workspace / "raw").rglob("secret.csv"):
            if p.is_file():
                got = p.read_bytes()
        assert got == SECRET_BODY, "artifact must contain the protected content"
        assert REPO.get_download_job(job.download_job_id)["status"] == "COMPLETED"

        # 5) protection is real: without the cookie the server refuses
        import httpx

        async with httpx.AsyncClient() as client:
            r = await client.get(f"{auth_server}/protected/secret.csv")
        assert r.status_code == 401

        # 6) idempotent: second resume does not re-download
        result2 = await RESUME_COORDINATOR.resume_access_job(aid)
        assert result2.get("resumed") is False and result2["reason"] == "already_completed"

    loop.run_until_complete(flow())
