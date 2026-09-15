// Auth Modal (P0-13/14/15, §17): real intervention flow.
// "我已完成" NEVER closes the modal directly — it POSTs resume, the backend PROBES
// the real session, and only a confirmed login resolves + auto-resumes the download.
import { esc, $ } from './utils.js';
import { api } from './api.js';

export function showAuthModal(intervention, onResolved) {
  const root = $("modal-root");
  root.innerHTML = `<div class="modal-overlay"><div class="modal auth-modal">
    <h3>需要登录 — ${esc(intervention.provider_name || "数据来源")}</h3>
    <p>${esc(intervention.message || "获取该数据需要先登录对应平台。")}</p>
    <p class="dim">为什么需要登录：该数据仅对登录用户开放。Metis 已打开官方登录页面，
    登录完成后会自动继续获取，无需其他操作。</p>
    <div id="auth-live" class="auth-live">
      <div class="auth-live-head">Live Browser <span class="dim">（登录过程仅在本地浏览器中进行，凭据只保存在本机安全存储）</span></div>
      <button id="auth-open-browser" class="primary">打开登录窗口</button>
    </div>
    <div id="auth-msg" class="auth-msg hidden"></div>
    <div class="modal-actions">
      <button id="auth-skip">跳过该来源</button>
      <button id="auth-done" class="primary">我已完成</button>
    </div>
  </div></div>`;

  const msg = root.querySelector("#auth-msg");
  const say = (text, bad) => {
    msg.classList.remove("hidden");
    msg.textContent = text;
    msg.classList.toggle("error", !!bad);
  };

  if (intervention.browser_session_id) {
    root.querySelector("#auth-open-browser").addEventListener("click", () => {
      import('./browser-monitor.js').then(m => m.showBrowserMonitor(intervention.browser_session_id));
    });
  } else {
    root.querySelector("#auth-open-browser").style.display = "none";
  }

  root.querySelector("#auth-done").addEventListener("click", async () => {
    const btn = root.querySelector("#auth-done");
    btn.disabled = true;
    btn.textContent = "正在检测登录状态…";
    try {
      const r = await api(`/api/interventions/${intervention.intervention_id}/resume`, { method: "POST" });
      if (r.state === "RESOLVED") {
        root.innerHTML = "";
        if (onResolved) onResolved();
      } else {
        // P0-14: probe FAILED → modal stays open with an honest message
        say(r.message || "仍未检测到登录成功，请在浏览器窗口完成登录后重试。", true);
        btn.disabled = false;
        btn.textContent = "我已完成";
      }
    } catch (e) {
      say("检测失败：" + e.message, true);
      btn.disabled = false;
      btn.textContent = "我已完成";
    }
  });

  root.querySelector("#auth-skip").addEventListener("click", async () => {
    try { await api(`/api/interventions/${intervention.intervention_id}/skip`, { method: "POST" }); } catch { /* already gone */ }
    root.innerHTML = "";
    if (onResolved) onResolved();
  });
}
