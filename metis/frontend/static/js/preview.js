// Preview (P0-03/§15): openResultPreview(result_id) — ONE entry, dispatched by the
// result API (FOUND → metadata; READY → real data; FINAL → final dataset).
// The preview REPLACES the result list, never appends a new panel below.
import { esc, $ } from './utils.js';
import { api } from './api.js';

export async function openResultPreview(resultId) {
  const list = $("result-list");
  const el = $("result-preview");
  list.classList.add("hidden");
  el.classList.remove("hidden");
  el.innerHTML = `<div class="preview-loading">加载预览…</div>`;
  try {
    const data = await api(`/api/results/${resultId}/preview?rows=30`);
    if (data.preview_kind === "metadata") {
      el.innerHTML = `${backBtn()}
        <div class="preview-title">${esc(data.title || "数据集")}</div>
        <p class="preview-note">该数据尚未获取，以下是来源提供的信息。点击「下载」获取真实数据后即可预览具体内容。</p>
        ${data.description ? `<p class="preview-desc">${esc(data.description)}</p>` : ""}
        <div class="preview-meta">
          ${data.publisher ? `<div><b>发布方</b>${esc(data.publisher)}</div>` : ""}
          ${data.geography && data.geography.length ? `<div><b>地域</b>${esc(data.geography.join("、"))}</div>` : ""}
          ${data.time_coverage && data.time_coverage.start ? `<div><b>时间</b>${esc(data.time_coverage.start)}–${esc(data.time_coverage.end)}</div>` : ""}
          ${data.license ? `<div><b>许可</b>${esc(data.license)}</div>` : ""}
          ${data.source_url ? `<div><b>来源</b><a href="${esc(data.source_url)}" target="_blank" rel="noopener">${esc(data.source_url)}</a></div>` : ""}
        </div>
        ${(data.variable_hints || []).length ? `<div class="rc-badges">${data.variable_hints.map(h => `<span class="badge">${esc(h)}</span>`).join("")}</div>` : ""}`;
    } else {
      const cols = data.columns || [];
      let html = `${backBtn()}<div class="preview-title">${esc(data.title || "数据预览")}</div>
        <div class="preview-note">${data.total_rows} 行 × ${cols.length} 列 ${data.preview_kind === "final" ? "· 最终数据集" : ""}</div>
        <div class="table-wrap"><table><thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>`;
      for (const row of data.rows || []) {
        html += `<tr>${cols.map(c => `<td>${esc(row[c])}</td>`).join("")}</tr>`;
      }
      html += `</tbody></table></div>`;
      el.innerHTML = html;
    }
  } catch (e) {
    el.innerHTML = `${backBtn()}<p class="error">预览失败：${esc(e.message)}</p>`;
  }
  el.querySelectorAll("[data-back]").forEach(b => b.addEventListener("click", closePreview));
}

function backBtn() {
  return `<div class="preview-header"><button data-back="1">← 返回结果列表</button></div>`;
}

export function closePreview() {
  $("result-preview").classList.add("hidden");
  $("result-preview").innerHTML = "";
  $("result-list").classList.remove("hidden");
}
