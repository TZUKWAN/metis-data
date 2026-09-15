// Browser Monitor (UAT-18): modal overlay with the live browser stream.
// Opens on demand (查看过程 / auth modal); closing it never stops the task.
import { esc, $ } from './utils.js';

export function showBrowserMonitor(sessionId) {
  const root = $("modal-root");
  if (root.querySelector(".browser-monitor")) return;
  const wrap = document.createElement("div");
  wrap.className = "modal-overlay browser-monitor";
  wrap.innerHTML = `<div class="modal monitor-modal">
    <div class="monitor-head"><b>浏览器实时画面</b><span class="dim">任务在后台继续运行</span>
    <button id="monitor-close">收起</button></div>
    <div id="monitor-frame" class="monitor-frame"><span class="dim">连接中…</span></div>
  </div>`;
  root.appendChild(wrap);
  wrap.querySelector("#monitor-close").addEventListener("click", () => { ws.close(); wrap.remove(); });

  const frame = wrap.querySelector("#monitor-frame");
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/browser/${sessionId}`);
  ws.onmessage = (ev) => {
    try {
      const m = JSON.parse(ev.data);
      if (m.t === "frame" && m.img) {
        frame.innerHTML = `<img class="monitor-img" src="data:image/jpeg;base64,${m.img}" alt="浏览器画面">
          ${m.cursor ? `<div class="monitor-cursor" style="left:${(Number(m.cursor.x) || 0)}px;top:${(Number(m.cursor.y) || 0)}px">▸</div>` : ""}
          <div class="monitor-url">${esc(m.url || "")}</div>`;
      } else if (m.t === "crashed") {
        frame.innerHTML = `<span class="error">浏览器会话已结束。</span>`;
      }
    } catch { /* skip malformed frame */ }
  };
  ws.onerror = () => { frame.innerHTML = `<span class="dim">无法连接浏览器画面。</span>`; };
}
