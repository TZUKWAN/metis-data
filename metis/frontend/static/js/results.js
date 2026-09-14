// Results pane: renders found/acquired/final datasets as clean cards.
import { esc, $ } from './utils.js';

export function renderResults(candidates) {
  const list = $("result-list");
  $("result-header").innerHTML = `<span>找到 ${candidates.length} 个数据源</span>`;
  if (!candidates.length) {
    list.innerHTML = `<div class="empty-results">没有找到匹配的数据。试着放宽时间范围或地域限制。</div>`;
    return;
  }
  list.innerHTML = candidates.map(c => resultCard(c)).join("");
}

function resultCard(c) {
  const trust = c.trust_label || labelTrust(c.provider_id);
  const cov = c.time_coverage?.start ? `${c.time_coverage.start}—${c.time_coverage.end}` : "";
  const lic = licenseLabel(c.license);
  return `<div class="result-card" data-id="${esc(c.candidate_id)}">
    <div class="rc-title">${esc(c.title)}</div>
    <div class="rc-meta">${esc(c.provider_id)} · ${esc(c.publisher || "")} ${cov ? "· " + esc(cov) : ""} · ${esc(lic)}</div>
    <div class="rc-reason">${esc(c.reason)}</div>
    <div class="rc-actions">
      <button onclick="window._preview('${esc(c.candidate_id)}')">预览</button>
      <button onclick="window._download('${esc(c.candidate_id)}')">下载</button>
    </div>
  </div>`;
}

function labelTrust(pid) {
  const official = ["world_bank","eurostat","ilostat","oecd","un_comtrade","us_census","usgs","un_databases","nbs_china"];
  const academic = ["zenodo","harvard_dataverse","dryad","osf","figshare"];
  if (official.includes(pid)) return "官方/国际组织";
  if (academic.includes(pid)) return "学术仓储";
  return "社区数据";
}

function licenseLabel(lic) {
  if (!lic || lic === "UNKNOWN") return "使用条件未知";
  if (/CC0|public domain|usgov/i.test(lic)) return "可公开使用";
  if (/CC-BY|attribution|ogl/i.test(lic)) return "需署名";
  if (/restricted|commercial/i.test(lic)) return "受限";
  return lic;
}
