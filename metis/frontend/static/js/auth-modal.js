import { esc, $ } from './utils.js';

export function showAuthModal(providerName, onDone) {
  const root = $("modal-root");
  root.innerHTML = `<div class="modal-overlay">
    <div class="modal auth-modal">
      <h3>需要登录</h3>
      <p>${esc(providerName)} 需要登录后才能继续获取这份数据。</p>
      <p>Metis 已打开登录页面。请完成登录，完成后任务会自动继续。</p>
      <div class="modal-actions">
        <button onclick="this.closest('.modal-overlay').remove()">取消此来源</button>
        <button class="primary" id="auth-done">我已完成</button>
      </div>
    </div>
  </div>`;
  root.querySelector("#auth-done").onclick = () => { root.innerHTML = ""; if (onDone) onDone(); };
}
