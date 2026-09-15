// Conversation pane (§12/§20/UAT-17): async 202 flow with real task stage labels,
// refresh-restore, cancel, and intervention surfacing.
import { api } from './api.js';
import { state, saveConversationId, loadSavedConversationId } from './store.js';
import { esc, $ } from './utils.js';
import { refreshResults } from './results.js';

const POLL_MS = 1500;

export function initConversation() {
  const composer = $("composer");
  const input = $("chat-input");
  const send = $("btn-send");

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
    send.disabled = !input.value.trim();
  });

  // Enter sends, Shift+Enter newlines, IME-safe (UAT-02/P0-15)
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      composer.requestSubmit();
    }
  });

  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || state.sending) return;
    state.sending = true;
    input.value = "";
    input.style.height = "auto";
    send.disabled = true;
    sendMessage(text).finally(() => { state.sending = false; send.disabled = !!input.value.trim() === false; });
  });

  document.querySelectorAll(".suggestion").forEach(btn => {
    btn.addEventListener("click", () => {
      input.value = btn.dataset.q;
      input.dispatchEvent(new Event("input"));
      composer.requestSubmit();
    });
  });
}

async function sendMessage(text) {
  hideEmptyState();
  addUserMessage(text);
  const statusEl = showTaskStatus("正在理解你的需求…", true);

  try {
    if (!state.conversationId) {
      const c = await api("/api/conversations", { method: "POST" });
      saveConversationId(c.conversation_id);
      connectConversationWS();
    }
    // async accept (§12): POST returns 202 immediately, work happens in background
    const r = await fetch(`/api/conversations/${state.conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (r.status !== 202) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.detail || `HTTP ${r.status}`);
    }
    const { task_id: taskId } = await r.json();
    statusEl.dataset.taskId = taskId;
    await pollTask(taskId, statusEl);
  } catch (e) {
    statusEl.remove();
    addAssistantMessage("发送失败：" + e.message + "\n\n请检查连接后重试。", true);
  }
}

async function pollTask(taskId, statusEl) {
  let ticks = 0;
  while (true) {
    let t;
    try {
      t = await api(`/api/conversations/${state.conversationId}/task/${taskId}`);
    } catch {
      await wait(POLL_MS);
      continue;
    }
    state.activeTask = t;
    if (statusEl.isConnected) {
      statusEl.querySelector(".task-label").textContent = t.stage_label || labelFor(t.state);
      statusEl.querySelector(".task-progress").style.width = `${Math.round((t.progress || 0) * 100)}%`;
      const stopBtn = statusEl.querySelector(".task-stop");
      if (stopBtn) stopBtn.style.display = ["COMPLETE", "FAILED", "CANCELLED"].includes(t.state) ? "none" : "";
    }
    await refreshResults();
    await loadInterventions();

    if (t.state === "COMPLETE" || t.state === "FAILED" || t.state === "CANCELLED") {
      if (statusEl.isConnected) statusEl.remove();
      await renderTaskReply(taskId);
      await refreshResults();
      state.activeTask = null;
      return;
    }
    ticks++;
    if (ticks === 8) setStatusNote(statusEl, "仍在进行中，大型搜索可能需要一分钟…");
    await wait(POLL_MS);
  }
}

function labelFor(s) {
  return ({
    UNDERSTANDING: "正在理解你的需求…", PLANNING: "正在规划数据方案…", SEARCHING: "正在寻找数据…",
    COLLECTING: "正在获取数据…", WAITING_USER: "需要你的操作", PROCESSING: "正在整理数据…",
    BUILDING: "正在合成数据集…", COMPLETE: "已完成", FAILED: "遇到问题", CANCELLED: "已取消",
  })[s] || s;
}

function setStatusNote(statusEl, note) {
  const n = statusEl.querySelector(".task-note");
  if (n) n.textContent = note;
}

export async function cancelTask(taskId) {
  try {
    await api(`/api/conversations/${state.conversationId}/task/${taskId}/cancel`, { method: "POST" });
  } catch { /* poll will reflect */ }
}

export async function loadInterventions() {
  if (!state.conversationId) return;
  try {
    const itvs = await api(`/api/conversations/${state.conversationId}/interventions?state=WAITING_USER`);
    state.interventions = itvs;
    if (itvs.length && !$("modal-root").querySelector(".auth-modal")) {
      const { showAuthModal } = await import('./auth-modal.js');
      showAuthModal(itvs[0], async () => { await refreshResults(); await loadInterventions(); });
    }
  } catch { /* transient */ }
}

// ---------- restore after refresh (§20) ----------
export async function restoreSession() {
  const cid = loadSavedConversationId();
  if (!cid) return false;
  try {
    const msgs = await api(`/api/conversations/${cid}/messages`);
    if (!msgs.length) return false;
    saveConversationId(cid);
    hideEmptyState();
    for (const m of msgs) {
      if (m.role === "user") addUserMessage(m.content);
      else if (m.role === "assistant") {
        if (m.task_id) renderedMsgIds.add(m.task_id);
        addAssistantMessage(m.content, (m.data || {}).error_code);
      }
    }
    await refreshResults();
    await loadInterventions();
    // resume polling if the latest task is still running
    const tasks = await api(`/api/conversations/${cid}/tasks`);
    const active = tasks.find(t => !["COMPLETE", "FAILED", "CANCELLED"].includes(t.state));
    if (active) {
      const statusEl = showTaskStatus(active.stage_label || labelFor(active.state), true);
      statusEl.dataset.taskId = active.task_id;
      pollTask(active.task_id, statusEl);
    }
    return true;
  } catch {
    return false;
  }
}

// ---------- new conversation (multi-conversation isolation, UAT-15) ----------
export async function startNewConversation() {
  const { reset } = await import('./store.js');
  reset();
  if (state.ws) { state.ws.close(); state.ws = null; }
  renderedMsgIds.clear();
  $("conversation").innerHTML = "";
  const { closePreview } = await import('./preview.js');
  closePreview();
  location.reload();
}

// ---------- rendering ----------
function hideEmptyState() {
  const es = document.querySelector(".empty-state");
  if (es) es.remove();
}

function addUserMessage(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.textContent = text;
  $("conversation").appendChild(div);
  scrollBottom();
}

export function addAssistantMessage(text, isError) {
  const div = document.createElement("div");
  div.className = "msg assistant" + (isError ? " error" : "");
  div.innerHTML = `<div class="msg-body">${esc(text).replace(/\n/g, "<br>")}</div>`;
  $("conversation").appendChild(div);
  scrollBottom();
}

const renderedMsgIds = new Set();

// fetch + append only the assistant reply for ONE task (idempotent across WS + poll)
export async function renderTaskReply(taskId) {
  if (!taskId || renderedMsgIds.has(taskId) || !state.conversationId) return;
  try {
    const msgs = await api(`/api/conversations/${state.conversationId}/messages`);
    const m = [...msgs].reverse().find(x => x.role === "assistant" && x.task_id === taskId);
    if (m) {
      renderedMsgIds.add(taskId);
      addAssistantMessage(m.content, (m.data || {}).error_code);
    }
  } catch { /* poll retries */ }
}

function showTaskStatus(label, cancellable) {
  const el = document.createElement("div");
  el.className = "task-status-inline";
  el.innerHTML = `<span class="spinner"></span><span class="task-label">${esc(label)}</span>
    <span class="task-note dim"></span>
    <div class="task-bar"><div class="task-progress" style="width:4%"></div></div>
    ${cancellable ? `<button class="task-stop" title="停止任务">停止</button>` : ""}`;
  $("conversation").appendChild(el);
  scrollBottom();
  const stop = el.querySelector(".task-stop");
  if (stop) stop.addEventListener("click", () => cancelTask(el.dataset.taskId));
  return el;
}

function scrollBottom() {
  const c = $("conversation");
  c.scrollTop = c.scrollHeight;
}

const wait = (ms) => new Promise(r => setTimeout(r, ms));

// ---------- realtime WS (§11) with polling fallback ----------
export function connectConversationWS() {
  if (!state.conversationId || state.ws) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/conversations/${state.conversationId}`);
  state.ws = ws;
  ws.onmessage = (ev) => {
    try {
      const e = JSON.parse(ev.data);
      const k = e.kind || "";
      if (k.includes("result.")) refreshResults();
      else if (k === "conversation.intervention.required") loadInterventions();
      else if (k === "conversation.task.failed" || k === "conversation.task.completed") {
        await renderTaskReply(e.payload && e.payload.task_id);
        refreshResults();
      }
    } catch { /* ignore malformed */ }
  };
  ws.onclose = () => { state.ws = null; setTimeout(connectConversationWS, 5000); };
}
