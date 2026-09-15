// Results pane (P0-02/§14): renders ONLY projected ResultView fields.
// The frontend never touches raw internal schemas or internal ids of any kind.
import { esc, $ } from './utils.js';
import { state } from './store.js';
import { api } from './api.js';
import { openResultPreview } from './preview.js';
import { showAuthModal } from './auth-modal.js';

export async function refreshResults() {
  if (!state.conversationId) return;
  try {
    const results = await api(`/api/conversations/${state.conversationId}/results`);
    state.results = results;
    renderResults(results);
  } catch { /* transient — polling will retry */ }
}

export function renderResults(results) {
  const list = $("result-list");
  const n = results.length;
  $("result-header").innerHTML = n
    ? `<span>${n} 个数据结果</span>`
    : `<span>找到的数据会显示在这里</span>`;
  if (!n) {
    list.innerHTML = `<div class="empty-results">还没有数据结果。左侧告诉我你需要什么数据。</div>`;
    return;
  }
  list.innerHTML = results.map(resultCard).join("");
  list.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", () => handleAction(btn.dataset.action, btn.dataset.id));
  });
}

async function handleAction(action, resultId) {
  if (action === "preview") {
    openResultPreview(resultId);
  } else if (action === "download") {
    await requestResultDownload(resultId);
  } else if (action === "auth") {
    const itv = (state.interventions || []).find(i => i.result_id === resultId && i.state === "WAITING_USER");
    if (itv) showAuthModal(itv, refreshAll);
  } else if (action.startsWith("export")) {
    const fmt = action.split(":")[1];
    window.location.href = `/api/results/${resultId}/export/${fmt}`;
  }
}

// P0-04: the ONLY download entry — conversation-scoped result API.
export async function requestResultDownload(resultId) {
  const card = document.querySelector(`[data-result="${resultId}"] .rc-state`);
  if (card) card.textContent = "正在获取…";
  try {
    const r = await fetch(`/api/results/${resultId}/download`, { method: "POST" });
    if (r.ok) {
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const dispo = r.headers.get("content-disposition") || "";
      a.download = decodeURIComponent((dispo.match(/filename="?([^";]+)"?/) || [])[1] || "dataset");
      a.click();
      URL.revokeObjectURL(url);
    } else if (r.status === 202) {
      const j = await r.json();
      if (card) card.textContent = stateCopy(j.state);
    } else {
      const j = await r.json().catch(() => ({}));
      if (card) card.textContent = "获取失败";
      appendDownloadNote(`下载遇到问题：${j.detail || j.message || "HTTP " + r.status}`);
    }
  } catch (e) {
    if (card) card.textContent = "获取失败";
    appendDownloadNote("网络异常，请稍后重试。");
  }
  // state may have transitioned (READY / WAITING_USER) — sync the pane
  setTimeout(refreshResults, 800);
  setTimeout(refreshResults, 2500);
}

function appendDownloadNote(text) {
  const el = $("result-header");
  if (el) el.innerHTML += ` <span class="dim">· ${esc(text)}</span>`;
}

export function stateCopy(s) {
  return ({
    "已找到": "已找到", "正在获取": "正在获取", "需要登录": "需要登录",
    "可用": "可用", "正在整理": "正在整理", "最终数据集": "最终数据集", "获取失败": "获取失败",
  })[s] || s;
}

function resultCard(v) {
  const stateClass = {
    "已找到": "found", "正在获取": "working", "需要登录": "auth",
    "可用": "ready", "正在整理": "working", "最终数据集": "final", "获取失败": "failed",
  }[v.state] || "found";

  const actions = [];
  if (v.preview_available || v.state === "已找到") actions.push(`<button data-action="preview" data-id="${esc(v.result_id)}">预览</button>`);
  if (v.state === "需要登录") actions.push(`<button data-action="auth" data-id="${esc(v.result_id)}" class="primary">完成登录</button>`);
  if (v.download_available && (v.state === "已找到" || v.state === "可用" || v.state === "最终数据集")) {
    actions.push(`<button data-action="download" data-id="${esc(v.result_id)}" class="primary">下载</button>`);
  }
  if (v.state === "可用" || v.state === "最终数据集") {
    for (const f of (v.export_formats || []).slice(0, 2)) {
      actions.push(`<button data-action="export:${esc(f)}" data-id="${esc(v.result_id)}">${esc(f.toUpperCase())}</button>`);
    }
  }

  const meta = [v.source_name, v.publisher, v.geography, v.time_range, v.format && v.format !== "UNKNOWN" ? v.format.toUpperCase() : ""]
    .filter(Boolean).map(x => esc(x)).join(" · ");

  return `<div class="result-card state-${stateClass}" data-result="${esc(v.result_id)}">
    <div class="rc-top"><div class="rc-title">${esc(v.title || "未命名数据集")}</div>
    <span class="rc-state st-${stateClass}">${esc(v.state)}</span></div>
    ${meta ? `<div class="rc-meta">${meta}</div>` : ""}
    ${v.description ? `<div class="rc-desc">${esc(v.description)}</div>` : ""}
    ${v.recommendation ? `<div class="rc-reason">${esc(v.recommendation)}</div>` : ""}
    <div class="rc-badges">
      <span class="badge">${esc(v.trust_label)}</span>
      <span class="badge">${esc(v.license_label)}</span>
    </div>
    <div class="rc-actions">${actions.join("")}</div>
  </div>`;
}

export async function refreshAll() {
  await refreshResults();
  const { loadInterventions } = await import('./conversation.js');
  await loadInterventions();
}
