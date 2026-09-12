"""Browser Runtime (P08): real headed Chromium via Playwright.

- Locator strategy chain (A7): a11y role/name → semantic DOM → text → stable
  CSS/data attribute → vision (template match) → coordinate fallback. Every
  action logs which strategy was used.
- Cooperative Pause / Take Over / Return (A8): a dispatcher gate refuses agent
  input when paused/not agent-owned; the user drives the same real window.
- Intervention detection (A9/A12): CAPTCHA/MFA/OTP/agreement/payment patterns
  flip the session to WAITING_USER with a reason; no bypass code exists.
- Download capture (A16): real Playwright download events bound to DownloadJob.
"""
from __future__ import annotations

import asyncio
import base64
import io
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import MetisError
from app.core.logging import get_logger
from app.domain.enums import BrowserOwner, BrowserSessionState, InterventionKind

log = get_logger("browser")

_SENSITIVE_QUERY = re.compile(r"([?&](?:token|key|otp|password|secret|code|signature)=)([^&]+)", re.I)


def sanitize_url(url: str | None) -> str | None:
    """P02-014: mask sensitive query values before URLs reach events/UI."""
    if not url:
        return url
    return _SENSITIVE_QUERY.sub(lambda m: m.group(1) + "***", url)


INTERVENTION_PATTERNS: list[tuple[InterventionKind, list[str]]] = [
    (InterventionKind.CAPTCHA, ["recaptcha", "g-recaptcha", "hcaptcha", "geetest", "are you a robot", "human verification", "captcha challenge", "prove you are not a robot"]),
    (InterventionKind.MFA, ["two-factor", "two factor", "2fa", "multi-factor", "mfa", "authenticator"]),
    (InterventionKind.PHONE_OTP, ["one-time code", "otp", "verification code", "sms code", "验证码", "短信"]),
    (InterventionKind.INSTITUTION_VERIFICATION, ["institutional login", "shibboleth", "sso login", "机构认证", "your organization"]),
    (InterventionKind.IDENTITY_VERIFICATION, ["identity verification", "upload your id", "身份证", "实名认证"]),
    (InterventionKind.RESTRICTED_DATA_AGREEMENT, ["data use agreement", "restricted data", "data agreement", "terms of use must", "license agreement"]),
    (InterventionKind.PAYMENT, ["payment required", "complete your purchase", "checkout", "add payment", "付款"]),
    (InterventionKind.HIGH_RISK_TERMS, ["legally binding", "you agree to be bound"]),
]


class DispatcherBlocked(MetisError):
    def __init__(self, reason: str, session_state: str) -> None:
        super().__init__("STATE_INVALID", f"agent input refused: {reason}", details={"session_state": session_state, "reason": reason})


@dataclass
class LocatorTarget:
    """Declarative target; resolved through the strategy chain at action time."""
    role: str | None = None  # button | link | textbox | checkbox | combobox | heading ...
    name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    text: str | None = None
    css: str | None = None  # stable CSS or [data-testid=...]
    alt: str | None = None
    template_png: bytes | None = None  # vision: reference crop
    coordinate: tuple[int, int] | None = None  # absolute last resort (explicit)
    nth: int = 0

    def describe(self) -> str:
        for k in ("role", "label", "placeholder", "text", "css", "alt"):
            v = getattr(self, k)
            if v:
                return f"{k}={v}"
        if self.template_png:
            return "vision-template"
        if self.coordinate:
            return f"coordinate={self.coordinate}"
        return "unspecified"


@dataclass
class BrowserActionEvent:
    seq: int
    ts: float
    action: str
    target: str
    status: str  # ok | error | skipped
    strategy: str | None = None
    url: str | None = None
    detail: dict = field(default_factory=dict)

    def public(self, redact_fn) -> dict:
        d = dict(self.detail)
        for k in ("typed_value",):
            if k in d:
                d[k] = "***MASKED***" if d.pop("secret", False) else redact_fn(str(d[k]))
        return {
            "seq": self.seq, "ts": self.ts, "action": self.action, "target": self.target,
            "status": self.status, "strategy": self.strategy, "url": self.url, "detail": d,
        }


class BrowserSession:
    """One real browser window the user can watch and take over at any time."""

    def __init__(self, browser, context, page: Any, session_id: str, task_label: str = "") -> None:
        self.browser = browser
        self.context = context
        self.session_id = session_id
        self.task_label = task_label
        self._pages: list[Any] = [page]
        self._current = 0
        self.owner: BrowserOwner = BrowserOwner.AGENT
        self.state: BrowserSessionState = BrowserSessionState.IDLE
        self.intervention: dict | None = None
        self.download_job_id: str | None = None
        self.task_binding: dict = {"provider_id": None, "task_id": None, "access_job_id": None, "download_job_id": None}
        # P02-004/006: visible cursor + click feedback state (streamed to UI)
        self.cursor: dict = {"x": 0, "y": 0}
        self.last_click: dict | None = None
        self.last_typing_at: float = 0.0
        self._frame_lock = asyncio.Lock()
        self.download_dir: Path | None = None
        self.downloads: list[dict] = []
        self.events: list[BrowserActionEvent] = []
        self._event_seq = 0
        self._subscribers: list[asyncio.Queue] = []
        self._last_element_ref: dict | None = None  # invalidated on Return
        self._install_page_listeners(page)
        page.on("download", lambda dl: asyncio.ensure_future(self._on_download(dl)))

    def bind_task(self, *, provider_id: str | None = None, task_id: str | None = None,
                  access_job_id: str | None = None, download_job_id: str | None = None) -> None:
        """P02-009: trace which task/access/download this browser is working for."""
        self.task_binding = {
            "provider_id": provider_id, "task_id": task_id,
            "access_job_id": access_job_id, "download_job_id": download_job_id,
        }
        if download_job_id:
            self.download_job_id = download_job_id
        self._emit("task.bound", dict(self.task_binding))

    # ---------- pages / tabs ----------
    @property
    def page(self) -> Any:
        return self._pages[self._current]

    def _install_page_listeners(self, page: Any) -> None:
        def on_popup(p: Any) -> None:
            self._track_page(p)
            self._emit("tab.opened", {"url": p.url, "total_tabs": len(self._pages)})

        page.context.on("page", on_popup)

    def _track_page(self, page: Any) -> int:
        """Idempotent page registration (context popup event + manual new_tab can race)."""
        if page not in self._pages:
            self._pages.append(page)
            page.on("download", lambda dl: asyncio.ensure_future(self._on_download(dl)))
        return self._pages.index(page)

    # ---------- events ----------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.append(q)
        return q

    def _emit(self, action: str, detail: dict | None = None, status: str = "ok", strategy: str | None = None, target: str = "") -> BrowserActionEvent:
        from app.core.logging import redact

        self._event_seq += 1
        ev = BrowserActionEvent(
            seq=self._event_seq, ts=time.time(), action=action, target=target or "",
            status=status, strategy=strategy, url=self._safe_url(), detail=detail or {},
        )
        self.events.append(ev)
        if len(self.events) > 500:
            self.events = self.events[-300:]
        from app.db.repository import REPO

        try:
            REPO.add_browser_event(self.session_id, ev.seq, action, ev.public(redact))
        except Exception:  # noqa: BLE001
            pass
        for q in self._subscribers:
            try:
                q.put_nowait(ev.public(redact))
            except asyncio.QueueFull:
                pass
        return ev

    def _safe_url(self) -> str:
        try:
            return sanitize_url(self.page.url)
        except Exception:  # noqa: BLE001
            return None  # type: ignore[return-value]

    # ---------- dispatcher gate (Pause / TakeOver / WAITING_USER) ----------
    def assert_can_dispatch(self) -> None:
        if self.owner is not BrowserOwner.AGENT:
            raise DispatcherBlocked("owner is human (take over active)", self.state)
        if self.state is BrowserSessionState.PAUSED:
            raise DispatcherBlocked("session paused", self.state)
        if self.state is BrowserSessionState.WAITING_USER:
            raise DispatcherBlocked(f"waiting for user: {self.intervention.get('kind') if self.intervention else 'intervention'}", self.state)
        if self.state is BrowserSessionState.CLOSED:
            raise DispatcherBlocked("session closed", self.state)

    # ---------- locator strategy chain (A7) ----------
    async def resolve(self, t: LocatorTarget):
        """Try strategies in fixed order; return (locator, strategy_name)."""
        page = self.page
        # 1. accessibility role/name
        if t.role:
            loc = page.get_by_role(t.role, name=t.name, exact=False) if t.name else page.get_by_role(t.role)
            if t.nth:
                loc = loc.nth(t.nth)
            if await loc.count() > 0:
                return loc.first, "a11y_role"
        # 2. semantic DOM: label / placeholder / alt
        if t.label:
            loc = page.get_by_label(t.label)
            if await loc.count() > 0:
                return loc.first, "semantic_label"
        if t.placeholder:
            loc = page.get_by_placeholder(t.placeholder)
            if await loc.count() > 0:
                return loc.first, "semantic_placeholder"
        if t.alt:
            loc = page.get_by_alt_text(t.alt)
            if await loc.count() > 0:
                return loc.first, "semantic_alt"
        # 3. text
        if t.text:
            loc = page.get_by_text(t.text)
            if await loc.count() > 0:
                return loc.first, "text"
        # 4. stable CSS / data attribute
        if t.css:
            loc = page.locator(t.css)
            if await loc.count() > 0:
                return loc.first, "css_stable"
        # 5. vision (template match on screenshot) — only when DOM strategies fail
        if t.template_png:
            box = await self._vision_locate(t.template_png)
            if box:
                return box, "vision_template"
        # 6. coordinate — explicit final fallback
        if t.coordinate:
            return t.coordinate, "coordinate_fallback"
        raise MetisError("STATE_INVALID", f"cannot locate target ({t.describe()})", details={"target": t.describe()})

    async def _vision_locate(self, template_png: bytes) -> tuple[int, int, int, int] | None:
        """Normalized template match via Pillow; returns (x,y,w,h) of best match."""
        import numpy as np
        from PIL import Image

        shot = await self.page.screenshot()
        scene = np.asarray(Image.open(io.BytesIO(shot)).convert("L"), dtype=np.float32)
        tpl_img = Image.open(io.BytesIO(template_png)).convert("L")
        tpl = np.asarray(tpl_img, dtype=np.float32)
        th, tw = tpl.shape
        if scene.shape[0] < th or scene.shape[1] < tw:
            return None
        tpl_mean = tpl - tpl.mean()
        tpl_norm = np.sqrt((tpl_mean**2).sum()) or 1.0
        best, best_val = None, -2.0
        step = 8
        for y in range(0, scene.shape[0] - th, step):
            for x in range(0, scene.shape[1] - tw, step):
                win = scene[y: y + th, x: x + tw]
                wm = win - win.mean()
                denom = np.sqrt((wm**2).sum()) * tpl_norm
                if denom == 0:
                    continue
                val = float((wm * tpl_mean).sum() / denom)
                if val > best_val:
                    best_val, best = val, (x, y, tw, th)
        if best and best_val > 0.75:
            return best
        return None

    # ---------- actions ----------
    async def navigate(self, url: str) -> dict:
        self.assert_can_dispatch()
        self.state = BrowserSessionState.RUNNING
        self._emit("navigate", {"url": url}, target=url)
        try:
            resp = await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await self._post_action_intervention_check()
            return {"url": self.page.url, "status": resp.status if resp else None}
        finally:
            if self.state is BrowserSessionState.RUNNING:
                self.state = BrowserSessionState.IDLE

    async def back(self) -> dict:
        self.assert_can_dispatch()
        await self.page.go_back()
        await self._post_action_intervention_check()
        return {"url": self.page.url}

    async def forward(self) -> dict:
        self.assert_can_dispatch()
        await self.page.go_forward()
        await self._post_action_intervention_check()
        return {"url": self.page.url}

    async def _human_move(self, x: float, y: float) -> None:
        """P02-005: interpolate cursor movement so the UI shows a visible trajectory."""
        steps = max(6, min(30, int(abs(x - self.cursor["x"]) + abs(y - self.cursor["y"])) // 18 or 6))
        await self.page.mouse.move(x, y, steps=steps)
        self.cursor = {"x": int(x), "y": int(y)}

    async def click(self, t: LocatorTarget) -> dict:
        self.assert_can_dispatch()
        target, strategy = await self.resolve(t)
        self.state = BrowserSessionState.RUNNING
        try:
            self._emit("click", {"target": t.describe()}, strategy=strategy, target=t.describe())
            box = None
            if strategy not in ("coordinate_fallback", "vision_template"):
                try:
                    box = await target.bounding_box()
                except Exception:  # noqa: BLE001
                    box = None
            if strategy in ("coordinate_fallback", "vision_template"):
                if len(target) == 2:
                    cx, cy = target[0], target[1]
                else:
                    x, y, w, h = target  # type: ignore[misc]
                    cx, cy = x + w // 2, y + h // 2
                await self._human_move(cx, cy)
                await self.page.mouse.down()
                await self.page.mouse.up()
            elif box:
                # P02-005/006: semantic locate → element box → visible move → click
                cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                await self._human_move(cx, cy)
                await self.page.mouse.down()
                await self.page.mouse.up()
            else:
                await target.click(timeout=15000)
            self.cursor = {"x": int(self.cursor["x"]), "y": int(self.cursor["y"])}
            self.last_click = {"x": self.cursor["x"], "y": self.cursor["y"], "ts": time.time()}
            self._last_element_ref = {"target": t.describe(), "strategy": strategy}
            await asyncio.sleep(0.3)
            await self._post_action_intervention_check()
            return {"url": self.page.url, "strategy": strategy, "cursor": self.cursor}
        finally:
            if self.state is BrowserSessionState.RUNNING:
                self.state = BrowserSessionState.IDLE

    async def double_click(self, t: LocatorTarget) -> dict:
        self.assert_can_dispatch()
        target, strategy = await self.resolve(t)
        if strategy in ("coordinate_fallback", "vision_template"):
            if len(target) == 2:
                await self.page.mouse.dblclick(target[0], target[1])  # type: ignore[index]
            else:
                x, y, w, h = target  # type: ignore[misc]
                await self.page.mouse.dblclick(x + w // 2, y + h // 2)
        else:
            await target.dblclick(timeout=15000)
        await self._post_action_intervention_check()
        return {"strategy": strategy}

    async def type_text(self, t: LocatorTarget, text: str, *, secret: bool = False) -> dict:
        self.assert_can_dispatch()
        target, strategy = await self.resolve(t)
        self.state = BrowserSessionState.RUNNING
        try:
            self._emit("type", {"target": t.describe(), "typed_value": text if not secret else "***", "secret": secret}, strategy=strategy, target=t.describe())
            if strategy in ("coordinate_fallback", "vision_template"):
                raise MetisError("STATE_INVALID", "cannot type via coordinate; DOM target required")
            if secret:
                await target.fill(text, timeout=15000)  # secrets type fast, never displayed
            else:
                # P02-007: real keyboard typing with delay — visible char-by-char in live view
                try:
                    await target.focus(timeout=5000)
                    await self.page.keyboard.type(text, delay=30)
                except Exception:  # noqa: BLE001
                    await target.fill(text, timeout=15000)  # P02-008: fill only as fallback
            self.last_typing_at = time.time()
            return {"strategy": strategy, "secret": secret, "typed_by": "fill" if secret else "keyboard"}
        finally:
            if self.state is BrowserSessionState.RUNNING:
                self.state = BrowserSessionState.IDLE

    async def press_key(self, key: str) -> dict:
        self.assert_can_dispatch()
        await self.page.keyboard.press(key)
        await asyncio.sleep(0.2)
        await self._post_action_intervention_check()
        return {"key": key}

    async def scroll(self, dx: int, dy: int) -> dict:
        self.assert_can_dispatch()
        await self.page.mouse.wheel(dx, dy)
        await asyncio.sleep(0.2)
        return {"dx": dx, "dy": dy}

    async def select_option(self, t: LocatorTarget, value: str) -> dict:
        self.assert_can_dispatch()
        target, strategy = await self.resolve(t)
        await target.select_option(value)
        return {"strategy": strategy, "selected": value}

    async def upload_file(self, t: LocatorTarget, file_path: str) -> dict:
        self.assert_can_dispatch()
        target, strategy = await self.resolve(t)
        await target.set_input_files(file_path)
        return {"strategy": strategy, "file": file_path}

    async def new_tab(self, url: str | None = None) -> dict:
        self.assert_can_dispatch()
        page = await self.context.new_page()
        await asyncio.sleep(0)  # let the context popup event settle, then idempotent-track
        self._current = self._track_page(page)
        if url:
            await page.goto(url, wait_until="domcontentloaded")
        self._emit("tab.new", {"total_tabs": len(self._pages)})
        return {"tabs": len(self._pages), "url": self.page.url}

    async def close_tab(self) -> dict:
        self.assert_can_dispatch()
        if len(self._pages) <= 1:
            raise MetisError("STATE_INVALID", "cannot close the last tab")
        page = self._pages.pop(self._current)
        try:
            await page.close()
        except Exception:  # noqa: BLE001
            pass
        self._current = max(0, min(self._current, len(self._pages) - 1))
        return {"tabs": len(self._pages)}

    async def switch_tab(self, index: int) -> dict:
        self.assert_can_dispatch()
        if not (0 <= index < len(self._pages)):
            raise MetisError("STATE_INVALID", f"tab index {index} out of range")
        self._current = index
        return {"url": self.page.url, "tabs": len(self._pages)}

    async def read_dom(self) -> dict:
        html = await self.page.content()
        return {"url": self.page.url, "title": await self.page.title(), "html_length": len(html), "html": html[:50000]}

    async def read_accessibility(self) -> list[dict]:
        """A11y tree via Playwright aria snapshot (new API) with DOM-outline fallback."""
        out: list[dict] = []
        try:
            snap = await self.page.locator("body").aria_snapshot()
            for depth, line in enumerate(snap.splitlines()):
                line = line.strip()
                if not line:
                    continue
                out.append({"role": line.split(":")[0].strip("-[]"), "name": line, "depth": min(depth, 12)})
        except Exception:  # noqa: BLE001 — fall back to a DOM outline
            try:
                outline = await self.page.evaluate(
                    """() => Array.from(document.querySelectorAll('a,button,input,select,textarea,h1,h2,h3,[role]')).slice(0,300).map(el => ({role: el.getAttribute('role') || el.tagName.toLowerCase(), name: (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || '').trim().slice(0,120)}))"""
                )
                out = [dict(o, depth=1) for o in outline]
            except Exception:  # noqa: BLE001
                out = []
        return out[:500]

    async def screenshot(self, full_page: bool = False) -> str:
        shot = await self.page.screenshot(full_page=full_page)
        return "data:image/png;base64," + base64.b64encode(shot).decode()

    # ---------- intervention detection (A9) ----------
    async def _post_action_intervention_check(self) -> None:
        try:
            url = (self.page.url or "").lower()
            content = (await self.page.content())[:20000].lower()
        except Exception:  # noqa: BLE001
            return
        for kind, patterns in INTERVENTION_PATTERNS:
            hit = next((p for p in patterns if p in url or p in content), None)
            if hit:
                self.intervention = {
                    "kind": kind.value,
                    "trigger": hit,
                    "url": self.page.url,
                    "title": await self.page.title(),
                    "message": f"agent stopped: {kind.value} detected ('{hit}'). Complete the step manually, then return control to the agent.",
                }
                self.state = BrowserSessionState.WAITING_USER
                self._emit("intervention", self.intervention, target=self.page.url)
                from app.db.repository import REPO

                REPO.add_ui_event("browser.intervention", "WARNING", task_id=self.download_job_id, payload=dict(self.intervention))
                return

    # ---------- live frame stream (P02-002/003) ----------
    async def get_frame(self) -> dict:
        """One JPEG frame (base64) + cursor/click/typing meta for the WS stream."""
        async with self._frame_lock:
            if not await self.is_alive():
                return {"alive": False}
            shot = await self.page.screenshot(type="jpeg", quality=55)
        return {
            "alive": True,
            "img": base64.b64encode(shot).decode(),
            "cursor": self.cursor,
            "click": self.last_click,
            "typing_recently": (time.time() - self.last_typing_at) < 1.5,
            "url": self._safe_url(),
            "owner": self.owner.value,
            "state": self.state.value,
        }

    async def is_alive(self) -> bool:
        try:
            return bool(self.browser.is_connected()) and self.page is not None and not self.page.is_closed()
        except Exception:  # noqa: BLE001
            return False

    # ---------- crash detection (P02-013) ----------
    async def check_crashed(self) -> bool:
        """Marks the session CRASHED if the browser/page died. Never pretends IDLE."""
        if self.state in (BrowserSessionState.CLOSED, BrowserSessionState.CRASHED):
            return self.state is BrowserSessionState.CRASHED
        if not await self.is_alive():
            self.state = BrowserSessionState.CRASHED
            self._emit("crash", {"note": "browser/page died; session marked CRASHED"}, status="error")
            return True
        return False

    # ---------- downloads (A16) ----------
    async def _on_download(self, download: Any) -> None:
        try:
            suggested = download.suggested_filename
            dest_dir = self.download_dir or Path(get_settings().browser_download_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{uuid.uuid4().hex[:8]}_{suggested}"
            await download.save_as(str(dest))
            self.downloads.append(
                {
                    "suggested_filename": suggested,
                    "path": str(dest),
                    "size": dest.stat().st_size,
                    "source_url": self.page.url,
                    "download_job_id": self.download_job_id,
                }
            )
            self._emit("download", {"suggested_filename": suggested, "path": str(dest), "size": dest.stat().st_size, "download_job_id": self.download_job_id}, target=suggested)
        except Exception as e:  # noqa: BLE001
            log.error_ctx("download capture failed", error=str(e))
            self._emit("download", {"error": str(e)}, status="error")

    # ---------- Pause / Take Over / Return (A8) ----------
    def pause(self) -> None:
        if self.state is BrowserSessionState.WAITING_USER:
            return
        self.state = BrowserSessionState.PAUSED
        self._emit("pause", {"note": "no new agent actions will be dispatched; the current atomic action was allowed to finish"})

    def resume(self) -> None:
        if self.state is BrowserSessionState.PAUSED:
            self.state = BrowserSessionState.IDLE
            self._emit("resume", {})

    def take_over(self) -> None:
        self.owner = BrowserOwner.HUMAN
        self.state = BrowserSessionState.TAKEN_OVER
        self._emit("take_over", {"note": "owner=human; agent input dispatcher disabled; same window/session"})

    async def return_to_agent(self) -> dict:
        """Re-observe the current page: fresh URL + DOM + a11y; old refs discarded."""
        self.owner = BrowserOwner.AGENT
        self.state = BrowserSessionState.IDLE
        self.intervention = None
        self._last_element_ref = None  # 废弃旧引用
        url = self.page.url
        title = await self.page.title()
        a11y = await self.read_accessibility()
        self._emit("return", {"url": url, "title": title, "a11y_nodes": len(a11y), "note": "re-read current page; stale element references dropped"})
        return {"url": url, "title": title, "a11y_nodes": len(a11y)}

    # ---------- lifecycle ----------
    async def close(self) -> None:
        self.state = BrowserSessionState.CLOSED
        try:
            await self.context.close()
        except Exception:  # noqa: BLE001
            pass


class BrowserManager:
    """Singleton managing the real headed Chromium."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._loop = None  # Playwright connections are event-loop bound
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        import asyncio as _asyncio

        async with self._lock:
            current = _asyncio.get_running_loop()
            connected = False
            try:
                connected = self._browser is not None and self._browser.is_connected() and self._loop is current
            except Exception:  # noqa: BLE001
                connected = False
            if connected:
                return self._browser
            # stale browser from a dead/different loop: detach WITHOUT awaiting on
            # this loop (cross-loop await on a playwright connection deadlocks) and
            # close it from a throwaway thread with its own loop.
            if self._browser is not None:
                stale_browser, stale_pw = self._browser, self._pw
                self._browser = None
                self._pw = None
                self._sessions.clear()
                import threading

                def _close_stale() -> None:
                    async def _c() -> None:
                        for closer in (stale_browser.close, stale_pw.stop):
                            try:
                                await closer()
                            except Exception:  # noqa: BLE001
                                pass

                    try:
                        asyncio.run(_c())
                    except Exception:  # noqa: BLE001
                        pass

                threading.Thread(target=_close_stale, daemon=True).start()
            from playwright.async_api import async_playwright

            cfg = get_settings()
            self._pw = await async_playwright().start()
            # container/CI-safe flags: --no-sandbox + --disable-dev-shm-usage prevent
            # silent hangs where chromium can't create its sandbox or /dev/shm is tiny
            self._browser = await self._pw.chromium.launch(
                headless=cfg.browser_headless,
                args=["--start-maximized", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._loop = current
            return self._browser

    async def new_session(self, task_label: str = "") -> BrowserSession:
        browser = await self._ensure_browser()
        context = await browser.new_context(no_viewport=True, accept_downloads=True)
        page = await context.new_page()
        sid = f"bs_{uuid.uuid4().hex[:16]}"
        sess = BrowserSession(browser, context, page, sid, task_label)
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> BrowserSession:
        sess = self._sessions.get(session_id)
        if sess is None:
            raise MetisError("NOT_FOUND", f"browser session {session_id} not found")
        return sess

    def sessions(self) -> list[dict]:
        return [
            {
                "session_id": s.session_id,
                "task_label": s.task_label,
                "owner": s.owner.value,
                "state": s.state.value,
                "url": s._safe_url(),
                "intervention": s.intervention,
                "task_binding": s.task_binding,
                "downloads": len(s.downloads),
            }
            for s in self._sessions.values()
        ]

    async def restart_crashed(self, session_id: str) -> BrowserSession:
        """P08-016: after browser crash, create a fresh session; agent must re-read pages (no stale refs)."""
        old = self._sessions.get(session_id)
        label = old.task_label if old else ""
        if old:
            old.state = BrowserSessionState.CRASHED
        return await self.new_session(task_label=f"{label} (recovered)")


MANAGER = BrowserManager()
