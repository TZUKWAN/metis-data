/* Metis Data UI — talks ONLY to the REST/WS API (never provider internals). */
const $ = (id) => document.getElementById(id);
const api = async (path, opts) => {
  const r = await fetch(path, opts && { headers: { "Content-Type": "application/json" }, ...opts, body: opts?.body ? JSON.stringify(opts.body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok && j.error_code) throw new Error(`${j.error_code}: ${j.message}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return j;
};
const esc = (s) => String(s ?? "").replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
const ts = (iso) => (iso || "").replace("T", " ").slice(11, 19);

let STATE = { requirement: null, runId: null, sessionId: null, builds: [], artifacts: [] };

/* ---------- status / events ---------- */
function pushEvent(kind, sev, payload) {
  const div = document.createElement("div");
  div.className = `event ${sev === "WARNING" ? "warn" : sev === "ERROR" ? "err" : ""}`;
  div.innerHTML = `<span class="ts">${new Date().toLocaleTimeString()}</span><b>${esc(kind)}</b> ${esc(payload?.message || payload?.reason || "")}`;
  $("agent-events").prepend(div);
  while ($("agent-events").children.length > 200) $("agent-events").lastChild.remove();
}
function connectWS() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/events`);
  ws.onopen = () => { $("conn-status").textContent = "已连接"; $("conn-status").className = "conn ok"; };
  ws.onclose = () => { $("conn-status").textContent = "已断开"; $("conn-status").className = "conn bad"; setTimeout(connectWS, 3000); };
  ws.onmessage = (m) => { const e = JSON.parse(m.data); pushEvent(e.kind, e.severity, e.payload); };
}

/* ---------- requirement (A1) ---------- */
$("btn-parse").onclick = async () => {
  const text = $("req-text").value.trim();
  if (!text) return alert("请输入自然语言数据需求");
  const r = await api("/api/requirements", { method: "POST", body: { text } });
  STATE.requirement = r;
  renderRequirement(r);
};
function renderRequirement(r) {
  const v = r.variables || {};
  $("req-card").className = "";
  $("req-card").innerHTML = `
    <p style="color:var(--dim);margin:4px 0">原始请求已保存</p>
    <div class="meta">研究单位：<b>${esc(r.unit_of_analysis)}</b> · 频率：<b>${esc(r.frequency)}</b> · 时间：<b>${r.time_range ? r.time_range.join("—") : "未识别"}</b></div>
    <div class="meta">变量：${[].concat(v.outcomes, v.exposures, v.controls, v.optional).filter(Boolean).map(esc).join(", ") || "未识别"}</div>
    <div class="meta">偏好来源：${esc((r.preferred_sources || []).join(", ") || "无")} · 假设：${(r.assumptions || []).map(esc).join("；") || "无"}</div>
    <div class="row" style="margin-top:6px">
      <input id="edit-start" style="width:80px" placeholder="${r.time_range?.[0] || ""}"> —
      <input id="edit-end" style="width:80px" placeholder="${r.time_range?.[1] || ""}">
      <button id="btn-edit-time">修改时间范围</button>
    </div>`;
  $("btn-edit-time").onclick = async () => {
    const s = +$("edit-start").value, e = +$("edit-end").value;
    if (!s || !e) return;
    const out = await api(`/api/requirements/${r.requirement_id}`, { method: "PUT", body: { time_range: [s, e] } });
    STATE.requirement = out.requirement; renderRequirement(out.requirement);
    pushEvent("requirement.updated", "INFO", { message: "Requirement 已修改，Provider 选择与查询计划将重新计算" });
  };
}

/* ---------- search (A3) ---------- */
$("btn-search").onclick = async () => {
  if (!STATE.requirement) return alert("先解析需求");
  const r = await api("/api/search/runs", { method: "POST", body: { requirement_id: STATE.requirement.requirement_id } });
  STATE.runId = r.run_id;
  pushEvent("search.started", "INFO", { message: `并行搜索 ${r.providers.length} 个 Provider：${r.providers.join(", ")}` });
  pollSearch();
};
$("btn-cancel-search").onclick = async () => { if (STATE.runId) await api(`/api/search/runs/${STATE.runId}/cancel`, { method: "POST" }); };

let polling = null;
function pollSearch() {
  clearInterval(polling);
  polling = setInterval(async () => {
    if (!STATE.runId) return clearInterval(polling);
    const run = await api(`/api/search/runs/${STATE.runId}`);
    $("provider-progress").innerHTML = run.provider_tasks.map((t) =>
      `<span class="badge ${t.status === "done" ? "ok" : t.status === "running" || t.status === "queued" ? "running" : "err"}" title="${esc(t.error_message || "")}">${esc(t.provider_id)}: ${t.status}${t.result_count ? ` (${t.result_count})` : ""}</span>`
    ).join("");
    if (["COMPLETED", "FAILED", "CANCELLED"].includes(run.status)) {
      clearInterval(polling);
      renderCandidates(run.candidates);
    }
  }, 1500);
}

/* ---------- candidates (A5) ---------- */
function renderCandidates(cands) {
  $("candidates").innerHTML = (cands || []).slice(0, 20).map((c) => {
    const rec = c.recommendation || {};
    return `<div class="candidate">
      <span class="score">${(c.score * 100).toFixed(0)}</span>
      <div class="title">${esc(c.title)}</div>
      <div class="meta">${esc(c.provider_id)} · ${esc(c.publisher)} ${c.doi ? `· <a href="${esc(c.doi)}" target="_blank">DOI</a>` : ""} · License: ${esc(c.license)}</div>
      <div class="meta">${esc(c.time_coverage?.start || "?")}—${esc(c.time_coverage?.end || "?")} · ${esc(c.unit_of_analysis)}</div>
      <details><summary>推荐理由 / 限制 / 未知</summary>
        <div class="reasons">${(c.reasons || []).map((x) => `<span class="pill">✓ ${esc(x)}</span>`).join("")}</div>
        <div class="limits">${(c.limitations || []).map((x) => `<span class="pill">⚠ ${esc(x)}</span>`).join("")}</div>
        <div class="unknowns">${(c.unknowns || []).map((x) => `<span class="pill">? ${esc(x)}</span>`).join("")}</div>
        <div class="meta">维度分：${Object.entries(rec).map(([k, v]) => `${k} ${(v * 100).toFixed(0)}`).join(" · ")}</div>
      </details>
      <button onclick="downloadCandidate('${esc(c.candidate_id)}')">下载该数据集</button>
      <button onclick="selectCandidate('${esc(c.candidate_id)}', this)">加入 Build</button>
    </div>`;
  }).join("") || "<p style='color:var(--dim)'>暂无候选</p>";
}
window.selectCandidate = async (cid, btn) => {
  await api(`/api/candidates/${cid}/select?selected=true`, { method: "POST" });
  btn.textContent = "已加入 ✓"; btn.disabled = true;
};
window.downloadCandidate = async (cid) => {
  const run = STATE.runId ? await api(`/api/search/runs/${STATE.runId}`) : { candidates: [] };
  const c = run.candidates.find((x) => x.candidate_id === cid) || (await api(`/api/search/runs/${STATE.runId}`)).candidates[0];
  if (!c) return;
  const src = (c.sources || [])[0] || {};
  const job = await api("/api/downloads", { method: "POST", body: { provider_id: c.provider_id, dataset_ref: src.source_ref || c.source_ref || cid, source_url: src.source_url || "", dataset_title: c.title, license: c.license, access_mode: c.access_mode, version: c.version } });
  pushEvent("download.job_created", "INFO", { message: `下载任务 ${job.download_job_id} 已创建（DownloadJob 门禁）` });
  refreshDownloads();
};

/* ---------- downloads ---------- */
async function refreshDownloads() {
  const jobs = await api("/api/downloads");
  $("downloads").innerHTML = (jobs || []).slice(0, 12).map((j) =>
    `<div class="event"><b>${esc(j.status)}</b> ${esc(j.dataset_ref)} <span class="ts">${esc(j.provider_id)}</span>${j.error_code ? ` <span class="err">${esc(j.error_code)}</span>` : ""}</div>`
  ).join("") || "<p style='color:var(--dim)'>暂无下载</p>";
  const arts = await api("/api/artifacts");
  STATE.artifacts = arts;
  $("artifact-list").innerHTML = arts.map((a) => `<button onclick="showArtifact('${esc(a.artifact_id)}')">${esc(a.dataset_title || a.dataset_ref)} (${esc(a.file_format)})</button>`).join(" ");
}
$("btn-refresh-downloads").onclick = refreshDownloads;

window.showArtifact = async (aid) => {
  const a = await api(`/api/artifacts/${aid}`);
  const prev = await api(`/api/artifacts/${aid}/preview?rows=25`);
  $("preview").innerHTML = `<p>SHA256 <code>${esc(a.checksum_sha256.slice(0, 24))}…</code> · ${(a.size_bytes / 1e6).toFixed(2)} MB · ${esc(a.license)}</p>
    <table class="preview"><tr>${prev.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>
    ${prev.rows.map((row) => `<tr>${prev.columns.map((c) => `<td>${esc(row[c])}</td>`).join("")}</tr>`).join("")}</table>`;
};

/* ---------- builds (A26-A34) ---------- */
$("btn-build-create").onclick = async () => {
  const selected = STATE.artifacts.slice(0, 2);
  if (selected.length < 1) return alert("先下载并注册至少一个 artifact");
  const cfg = await api("/api/builds", { method: "POST", body: {
    title: `panel-${new Date().toISOString().slice(0, 10)}`,
    inputs: selected.map((a) => ({ artifact_id: a.artifact_id })),
    keys: ["country", "year"],
    missing_policy: "none",
    derived_variables: [],
  }});
  pushEvent("build.created", "INFO", { message: `Build ${cfg.build_id} 已创建，计划 ${cfg.plan.length} 步（m:m 默认阻止）` });
  await api(`/api/builds/${cfg.build_id}/run`, { method: "POST" });
  pollBuild(cfg.build_id);
};
function pollBuild(bid) {
  const t = setInterval(async () => {
    const b = await api(`/api/builds/${bid}`);
    $("builds").innerHTML = `<div class="event"><b>${esc(b.status)}</b> ${esc(b.title || bid)}</div>
      ${(b.operations || []).slice(-6).map((o) => `<div class="event"><span class="ts">#${o.seq}</span> ${esc(o.operation_type)} <span class="ts">${o.row_count_after ?? ""}</span></div>`).join("")}`;
    if (["COMPLETE", "FAILED", "CANCELLED", "NEEDS_REVIEW"].includes(b.status)) {
      clearInterval(t);
      if (b.status === "COMPLETE") showPackage(bid);
      if (["FAILED", "NEEDS_REVIEW"].includes(b.status)) pushEvent("build." + b.status.toLowerCase(), "ERROR", { message: `Build ${bid} ${b.status}（真实状态，无假 COMPLETE）` });
    }
  }, 2000);
}
async function showPackage(bid) {
  const b = await api(`/api/builds/${bid}`);
  const pkg = (b.stage_checkpoints?.COMPLETE?.package) || {};
  const vals = b.validations || [];
  $("provenance").innerHTML = `
    <p>交付包已生成（所有 manifest 引用文件已校验存在）：</p>
    <div class="meta">${pkg.files?.map((f) => `<span class="pill">${esc(f)}</span>`).join("")}</div>
    <p>质量检查：${vals.map((v) => `<span class="pill ${v.severity === "ERROR" ? "err" : ""}">${esc(v.severity)} ${esc(v.code)}</span>`).join("")}</p>
    <p><a href="/api/builds/${esc(bid)}/package/reports/methodology.md" target="_blank">Methodology</a> ·
       <a href="/api/builds/${esc(bid)}/package/reports/quality_report.html" target="_blank">Quality Report</a> ·
       <a href="/api/builds/${esc(bid)}/package/final/dataset.csv">dataset.csv</a> ·
       <a href="/api/builds/${esc(bid)}/package/scripts/reproduce.py">reproduce.py</a></p>
    <details><summary>字段级 Lineage（前 5 条）</summary>${(b.field_lineage || []).slice(0, 5).map((l) => `<div class="event">${esc(l.final_field)} → ${esc(l.lineage.provider_dataset)} → ${esc(l.lineage.url)}</div>`).join("")}</details>`;
}

/* ---------- live browser (A6-A9) ---------- */
const bapi = (action, extra = {}) => api(`/api/browser/${action}`, { method: "POST", body: { session_id: STATE.sessionId, ...extra } });
$("bs-new").onclick = async () => {
  const s = await bapi("sessions", { url: undefined, task_label: "ui" }).catch(() => null);
  const r = await api("/api/browser/sessions", { method: "POST", body: { task_label: "ui" } });
  STATE.sessionId = r.session_id;
  refreshBrowser();
};
$("bs-navigate").onclick = () => STATE.sessionId && bapi("navigate", { url: $("bs-url").value }).then(refreshBrowser);
$("bs-pause").onclick = () => bapi("pause").then(refreshBrowser);
$("bs-takeover").onclick = () => bapi("takeover").then(refreshBrowser);
$("bs-return").onclick = () => bapi("return").then(refreshBrowser);
async function refreshBrowser() {
  if (!STATE.sessionId) return;
  const sessions = await api("/api/browser/sessions");
  const s = sessions.find((x) => x.session_id === STATE.sessionId);
  if (!s) return;
  $("browser-status").innerHTML = `<span class="badge ${s.state === "RUNNING" ? "running" : s.state === "WAITING_USER" ? "warn" : "ok"}">state=${esc(s.state)}</span>
    <span class="badge ${s.owner === "agent" ? "ok" : "warn"}">owner=${esc(s.owner)}</span>
    <span class="badge">${esc(s.url || "")}</span>`;
  if (s.intervention) {
    $("browser-intervention").className = "intervention";
    $("browser-intervention").innerHTML = `⛔ ${esc(s.intervention.kind)}：${esc(s.intervention.message)}<br><small>Agent 已停止输入。请手动完成该步骤后点击“交还 Agent”。</small>`;
  } else $("browser-intervention").className = "hidden";
  const shot = await bapi("screenshot");
  $("browser-shot").src = shot.image;
  const evs = await api(`/api/browser/sessions/${STATE.sessionId}/events`);
  $("browser-events").innerHTML = evs.slice(-12).reverse().map((e) =>
    `<div class="event ${e.status === "error" ? "err" : ""}"><span class="ts">${ts(e.ts)}</span><b>${esc(e.action)}</b> ${esc(e.target || "")} ${e.strategy ? `<span class="pill">${esc(e.strategy)}</span>` : ""} ${esc(e.status)}</div>`).join("");
}
setInterval(refreshBrowser, 2500);

/* ---------- init ---------- */
connectWS();
refreshDownloads();
$("req-text").value = "构建 2015—2023 年国家层面的青年失业率、人均 GDP、教育水平面板，优先使用官方或国际组织数据。";
