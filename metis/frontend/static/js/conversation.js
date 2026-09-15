// Conversation pane: async pattern — POST returns 202, poll task state.
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

  // Enter sends, Shift+Enter newlines (P0-15)
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      composer.requestSubmit();
    }
  });

  composer.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    input.style.height = "auto";
    send.disabled = true;

    // show user message immediately (§71: <100ms)
    addUserMessage(text);
    const statusEl = showStatus("正在理解你的需求…");

    try {
      if (!state.conversationId) {
        const c = await api("/api/conversations", { method: "POST" });
        state.conversationId = c.conversation_id;
      }

      // POST returns 202 with task_id — poll for completion
      const resp = await fetch(`/api/conversations/${state.conversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const initial = await resp.json();
      const taskId = initial.task_id;

      if (resp.status === 202) {
        // async — poll task state
        statusEl.textContent = "正在寻找数据…";
        let result = null;
        for (let i = 0; i < 300; i++) {
          await wait(2000);
          const tr = await api(`/api/conversations/${state.conversationId}/task/${taskId}`);
          if (tr.state === "COMPLETE" || tr.state === "FAILED") {
            // get final reply from messages
            const msgs = await api(`/api/conversations/${state.conversationId}/messages`);
            const lastAssistant = [...msgs].reverse().find(m => m.role === "assistant");
            if (lastAssistant) {
              statusEl.remove();
              addAssistantMessage(lastAssistant.content, {});
            }
            searchDone = tr.state === "COMPLETE";
            break;
          }
          if (i === 30) statusEl.textContent = "正在规划数据方案…这可能需要一些时间…";
          if (i === 60) statusEl.textContent = "仍在搜索数据来源…";
        }
      } else {
        statusEl.remove();
        addAssistantMessage(initial.reply || "完成。", {});
      }

      if (onResults) onResults({ searchDone });
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

let searchDone = false;

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
