// Metis Data — Simple Conversational UI.
import { state, reset } from './store.js';
import { api } from './api.js';
import { esc, $ } from './utils.js';
import { initConversation, clearConversation } from './conversation.js';
import { renderResults } from './results.js';

// init
initConversation(onResults);
initSettings();
checkHealth();
setInterval(checkHealth, 15000);

// expose for inline handlers
window._preview = (aid) => { import('./preview.js').then(m => m.showPreview(aid)); };

async function checkHealth() {
  try {
    await api("/api/health");
    $("system-status").className = "status-dot ok";
    $("system-status").title = "已连接";
  } catch (e) {
    $("system-status").className = "status-dot bad";
    $("system-status").title = "连接断开";
  }
}

// wire conversation → results
function onResults(r) {
  if (r.candidates) renderResults(r.candidates);
  if (r.reply) appendAssistantMsg(r.reply);
}

// conversation.js calls this when a new assistant message arrives
function appendAssistantMsg(text) {
  const div = document.createElement("div");
  div.className = "msg assistant";
  div.innerHTML = `<div class="msg-body">${esc(text).replace(/\n/g, "<br>")}</div>`;
  $("conversation").appendChild(div);
  $("conversation").parentElement.scrollTop = 1e6;
}

// dev mode
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && e.key === "D") {
    import('./debug.js').then(m => m.toggleDebug());
  }
});

// settings
function initSettings() {
  $("settings-button").addEventListener("click", async () => {
    const root = $("modal-root");
    root.innerHTML = `<div class="modal-overlay"><div class="modal"><h3>设置</h3><section><h4>已保存登录</h4><div id="settings-accounts">加载中…</div></section><button onclick="this.closest('.modal-overlay').remove()">关闭</button></div></div>`;
    const el = root.querySelector("#settings-accounts");
    try {
      const accounts = await api("/api/accounts");
      el.innerHTML = accounts.length ? accounts.map(a => `<div class="event">${esc(a.provider_id)}: ${esc(a.status)}</div>`).join("") : "<p class='dim'>暂无</p>";
    } catch (e) { el.innerHTML = "<p class='dim'>加载失败</p>"; }
  });
}
