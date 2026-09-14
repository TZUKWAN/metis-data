// Metis Data — Simple Conversational UI (main entry).
import { initConversation } from './conversation.js';
import { renderResults } from './results.js';
import { showPreview } from './preview.js';
import { initSettings } from './settings.js';
import { toggleDebug } from './debug.js';
import { state, $ } from './store.js';
import { api } from './api.js';

// expose for inline onclick
window._preview = (aid) => { import('./preview.js').then(m => m.showPreview(aid)); };
window._download = (cid) => { downloadResult(cid); };

async function downloadResult(cid) {
  try {
    const runs = state.conversationId ? [] : [];
    const r = await api(`/api/search/runs`).catch(() => ({ runs: [] }));
    // find candidate data from latest run
    const cands = await api(`/api/search/runs`).then(x => {
      const last = x.runs?.[0];
      return last ? api(`/api/search/runs/${last.run_id}`).then(run => run.candidates || []) : [];
    }).catch(() => []);
    const c = cands.find(c => c.candidate_id === cid);
    if (!c) { alert("找不到该数据"); return; }
    const src = (c.sources || [])[0] || {};
    const dl = await api("/api/downloads", { method: "POST", body: {
      provider_id: c.provider_id, dataset_ref: src.source_ref || cid,
      source_url: src.source_url || "", dataset_title: c.title,
      license: c.license, access_mode: c.access_mode,
    }});
    pushStatus("正在获取数据…");
  } catch (e) {
    pushStatus("下载失败: " + e.message);
  }
}

function pushStatus(text) {
  const el = $("result-header");
  if (el) el.innerHTML = `<span class="status-running">${esc(text)}</span>`;
}

// init
initConversation(onResults);
initSettings();

function onResults(r) {
  if (r.candidates) renderResults(r.candidates);
}

// health check
async function checkHealth() {
  try {
    await api("/api/health");
    $("system-status").classList.add("ok");
    $("system-status").title = "已连接";
  } catch (e) {
    $("system-status").classList.remove("ok");
    $("system-status").title = "连接断开";
  }
}
checkHealth();
setInterval(checkHealth, 15000);

// keyboard shortcut for developer mode
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && e.key === "D") {
    import('./debug.js').then(m => m.toggleDebug());
  }
});
