// Conversation pane: user/assistant messages, task status, composer.
import { api } from './api.js';
import { state, reset } from './store.js';
import { esc, $ } from './utils.js';

export function initConversation(onResults) {
  const composer = $("composer");
  const input = $("chat-input");
  const send = $("btn-send");

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
    send.disabled = !input.value.trim();
  });

  composer.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    input.style.height = "auto";
    send.disabled = true;

    addUserMessage(text);
    const statusEl = showStatus("正在理解你的需求…");

    try {
      if (!state.conversationId) {
        const c = await api("/api/conversations", { method: "POST" });
        state.conversationId = c.conversation_id;
      }
      const r = await api(`/api/conversations/${state.conversationId}/messages`, {
        method: "POST",
        body: { text },
      });
      statusEl.remove();
      addAssistantMessage(r.reply || "完成。", r);
      if (onResults) onResults(r);
    } catch (err) {
      statusEl.remove();
      addAssistantMessage("遇到了问题：" + err.message + "\n\n你可以稍后重试或换个说法。", { error: true });
    }
    send.disabled = false;
  });

  // suggestions
  document.querySelectorAll(".suggestion").forEach(btn => {
    btn.addEventListener("click", () => {
      input.value = btn.dataset.q;
      input.dispatchEvent(new Event("input"));
      composer.dispatchEvent(new Event("submit"));
    });
  });
}

function addUserMessage(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.textContent = text;
  $("conversation").appendChild(div);
  $("conversation").parentElement.scrollTop = 1e6;
}

function addAssistantMessage(text, data = {}) {
  const div = document.createElement("div");
  div.className = "msg assistant" + (data.error ? " error" : "");
  div.innerHTML = `<div class="msg-body">${esc(text).replace(/\n/g, "<br>")}</div>`;
  $("conversation").appendChild(div);
  $("conversation").parentElement.scrollTop = 1e6;
}

function showStatus(text) {
  const el = document.createElement("div");
  el.className = "task-status-inline";
  el.textContent = text;
  $("conversation").appendChild(el);
  $("conversation").parentElement.scrollTop = 1e6;
  return el;
}

export function clearConversation() {
  reset();
  $("conversation").innerHTML = "";
}
