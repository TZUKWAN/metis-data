// Metis Data — Simple Conversational UI (entry).
import { state } from './store.js';
import { api } from './api.js';
import { $ } from './utils.js';
import { initConversation, restoreSession, connectConversationWS, startNewConversation } from './conversation.js';
import { refreshResults } from './results.js';
import { initSettings } from './settings.js';

initSettings();
initConversation();
$("new-conversation").addEventListener("click", startNewConversation);
checkHealth();
setInterval(checkHealth, 15000);

// refresh-restore (§20): previous conversation comes back with messages/results/task
restoreSession().then((restored) => {
  if (restored) connectConversationWS();
});

async function checkHealth() {
  try {
    await api("/api/health");
    $("system-status").className = "status-dot ok";
    $("system-status").title = "已连接";
  } catch {
    $("system-status").className = "status-dot bad";
    $("system-status").title = "连接断开";
  }
}

// Developer Mode (Ctrl+Shift+D) — internal detail stays out of the default UI (§22)
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "d") {
    import('./debug.js').then(m => m.toggleDebug());
  }
});
