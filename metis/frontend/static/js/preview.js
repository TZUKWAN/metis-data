import { esc, $ } from './utils.js';
import { api } from './api.js';

export function showPreview(artifactId) {
  const el = $("result-preview");
  el.classList.remove("hidden");
  el.innerHTML = `<div class="preview-loading">加载预览…</div>`;
  fetch(`/api/artifacts/${artifactId}/preview?rows=30`)
    .then(r => r.json())
    .then(data => {
      if (!data.columns) { el.innerHTML = "<p>无法预览</p>"; return; }
      let html = `<div class="preview-header"><button onclick="this.closest('#result-preview').classList.add('hidden')">← 返回</button><b>${esc(data.total_rows)} 行</b></div><div class="table-wrap"><table><tr>${data.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr>`;
      for (const row of data.rows) {
        html += `<tr>${data.columns.map(c => `<td>${esc(row[c])}</td>`).join("")}</tr>`;
      }
      html += "</table></div>";
      el.innerHTML = html;
    })
    .catch(e => { el.innerHTML = `<p class="error">预览失败: ${esc(e.message)}</p>`; });
}
