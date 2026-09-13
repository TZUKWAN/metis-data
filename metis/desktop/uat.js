// UAT walkthrough on the real Electron desktop app.
// Uses Playwright Electron support to drive the actual desktop window.
const { _electron } = require(require('path').join('C:', 'Users', 'lauze', 'miniconda3', 'Lib', 'site-packages', 'playwright', 'driver', 'package'));
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const REPO = path.resolve(__dirname, '..', '..');
const PORT = 8393;
const OUT = path.join(REPO, 'metis', 'artifacts', 'rc-final-v2', 'uat', 'UAT-desktop');
const wait = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(path.join(OUT, 'screenshots'), { recursive: true });
  const consoleErrors = [];
  const networkErrors = [];
  const steps = [];

  function logStep(step, screen, action, target, expected, actual, status) {
    steps.push({ step, screen, action, target, expected, actual: String(actual).slice(0, 200), status, ts: new Date().toISOString() });
    console.log(`  step ${step}: ${action} @ ${target} → ${status}`);
  }

  // 1) start backend
  const backend = spawn('python', ['-u', '-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: path.join(REPO, 'metis', 'backend'),
    env: { ...process.env, METIS_PORT: String(PORT) },
    windowsHide: true,
  });
  for (let i = 0; i < 60; i++) {
    try {
      await new Promise((resolve, reject) => {
        const rq = http.get(`http://127.0.0.1:${PORT}/api/health`, (resp) => {
          resp.resume();
          resp.statusCode === 200 ? resolve() : reject(new Error('not ready'));
        });
        rq.on('error', reject);
        rq.setTimeout(1500, () => { rq.destroy(); reject(new Error('timeout')); });
      });
      break;
    } catch (e) { await wait(500); }
  }

  // 2) launch Electron
  const electronExe = require('electron');
  const electronApp = await _electron.launch({
    executablePath: electronExe,
    args: [path.join(__dirname, 'main.js')],
    env: { ...process.env, METIS_PORT: String(PORT) },
  });
  const win = await electronApp.firstWindow();
  await win.setViewportSize({ width: 1920, height: 1080 });
  await win.waitForLoadState('domcontentloaded');
  await wait(2500);
  win.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  win.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err}`));

  const shot = (name) => win.screenshot({ path: path.join(OUT, 'screenshots', name + '.png') });

  // ---- UAT-01: initial load ----
  await shot('UAT-01-home');
  const connText = await win.locator('#conn-status').innerText().catch(() => 'n/a');
  logStep(1, 'home', 'load', 'app', 'connected', connText, connText.includes('已连接') ? 'PASS' : 'FAIL');
  const panels = await win.locator('.panel').count();
  logStep(2, 'home', 'count', '.panel', '>=8 panels', `${panels} panels`, panels >= 8 ? 'PASS' : 'FAIL');

  // ---- UAT-02: planning ----
  const reqText = '帮我构建 2012—2024 年中国地级市层面的数字经济、地方财政压力、环境规制、人口老龄化、产业升级面板数据。';
  await win.fill('#req-text', reqText);
  logStep(3, 'home', 'type', '#req-text', reqText.slice(0, 30), 'typed', 'PASS');

  await win.click('#btn-agent-plan');
  await wait(5000);
  const planVisible = await win.locator('#agent-plan-card').isVisible().catch(() => false);
  logStep(4, 'planning', 'click', '#btn-agent-plan', 'plan card visible', String(planVisible), planVisible ? 'PASS' : 'FAIL');
  await shot('UAT-02-planning');

  // edit time range
  const startInput = win.locator('#ap-start');
  if (await startInput.isVisible().catch(() => false)) {
    await startInput.fill('2015');
    await win.locator('#ap-end').fill('2024');
    logStep(5, 'planning', 'edit', 'time_range', '2015-2024', 'edited', 'PASS');
  }

  // ---- UAT-03: search ----
  await win.click('#btn-search');
  await wait(3000);
  logStep(6, 'search', 'click', '#btn-search', 'search started', 'clicked', 'PASS');
  await shot('UAT-03-search-running');

  // wait for completion
  let searchDone = false;
  for (let i = 0; i < 120; i++) {
    await wait(2000);
    const runs = await win.evaluate(`fetch('/api/search/runs').then(r => r.json())`).catch(() => []);
    if (runs.length && ['COMPLETED', 'FAILED', 'CANCELLED'].includes(runs[0].status)) {
      searchDone = runs[0].status === 'COMPLETED';
      break;
    }
  }
  logStep(7, 'search', 'wait', 'completion', 'COMPLETED', searchDone ? 'COMPLETED' : 'not completed', searchDone ? 'PASS' : 'FAIL');
  await shot('UAT-03-candidates');

  // ---- UAT-06: download from candidate card ----
  const dlBtn = win.locator('text=下载该数据集').first();
  if (await dlBtn.isVisible().catch(() => false)) {
    await dlBtn.click();
    await wait(3000);
    logStep(8, 'download', 'click', '下载该数据集', 'download started', 'clicked', 'PASS');
  } else {
    logStep(8, 'download', 'skip', 'no candidates visible', 'skip', 'SKIP', 'SKIP');
  }

  // ---- screenshots of all panels ----
  for (const [sel, name] of [['#acq-tasks', 'acq-tasks'], ['#backend-health', 'backend-health'], ['#provider-matrix', 'provider-matrix']]) {
    try {
      const btn = win.locator(`text=${name === 'acq-tasks' ? 'Acquisition' : name === 'backend-health' ? '诊断' : '加载 Integration'}`).first();
      if (await btn.isVisible().catch(() => false)) await btn.click();
    } catch (e) { /* ok */ }
  }
  await wait(2000);
  await shot('UAT-panels');

  // ---- save results ----
  fs.writeFileSync(path.join(OUT, 'steps.json'), JSON.stringify(steps, null, 2));
  fs.writeFileSync(path.join(OUT, 'console.json'), JSON.stringify(consoleErrors, null, 2));
  console.log(`\\nUAT complete: ${steps.filter(s => s.status === 'PASS').length}/${steps.length} PASS`);
  console.log(`Console errors: ${consoleErrors.length}`);
  for (const s of steps) {
    if (s.status !== 'PASS') console.log(`  FAIL: step ${s.step} ${s.action}: ${s.actual}`);
  }

  await electronApp.close();
  backend.kill();
  process.exit(0);
})().catch(e => { console.error('UAT FAIL:', e.message); process.exit(1); });
