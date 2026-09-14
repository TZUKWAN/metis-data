import { esc, $ } from './utils.js';

export function initSettings() {
  $("settings-button").addEventListener("click", () => {
    const root = $("modal-root");
    root.innerHTML = `<div class="modal-overlay"><div class="modal settings-modal">
      <h3>设置</h3>
      <section><h4>已保存登录</h4><div id="settings-accounts">加载中…</div></section>
      <section><h4>隐私</h4><p class="dim">所有凭据存储在系统安全存储中。</p></section>
      <button onclick="this.closest('.modal-overlay').remove()">关闭</button>
    </div></div>`;
    fetch("/api/accounts").then(r => r.json()).then(accounts => {
      const el = root.querySelector("#settings-accounts");
      el.innerHTML = accounts.length
        ? accounts.map(a => `<div class="event">${esc(a.provider_id)}: ${esc(a.status)}</div>`).join("")
        : "<p class='dim'>暂无保存的登录</p>";
    }).catch(() => { el.innerHTML = "<p>加载失败</p>"; });
  });
}
