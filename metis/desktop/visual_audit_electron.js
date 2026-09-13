const { _electron } = require(require('path').join('C:', 'Users', 'lauze', 'miniconda3', 'Lib', 'site-packages', 'playwright', 'driver', 'package'));
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const REPO = path.resolve(__dirname, '..', '..');
const PORT = 8392;
const VIEWPORTS = [[1366, 768], [1920, 1080], [2560, 1440]];
const OUT = path.join(REPO, 'metis', 'artifacts', 'rc-final-v2');
const wait = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(path.join(OUT, 'screenshots'), { recursive: true });
  fs.mkdirSync(path.join(OUT, 'visual-audit'), { recursive: true });

  const backend = spawn('python', ['-u', '-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: path.join(REPO, 'metis', 'backend'),
    env: { ...process.env, METIS_PORT: String(PORT) },
    windowsHide: true,
  });
  let ready = false;
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
      ready = true;
      break;
    } catch (e) { await wait(500); }
  }
  if (!ready) { console.error('backend not ready'); process.exit(1); }

  const electronExe = require('electron');
  const electronApp = await _electron.launch({
    executablePath: electronExe,
    args: [path.join(__dirname, 'main.js')],
    env: { ...process.env, METIS_PORT: String(PORT) },
  });
  const win = await electronApp.firstWindow();
  await win.waitForLoadState('domcontentloaded');
  await wait(2000);

  // console / network collectors
  const consoleErrors = [];
  win.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });

  const AUDIT_JS = `(() => {
    const issues = { overlaps: [], clipped: [], out_of_viewport: [], tiny_click_targets: [] };
    const els = [...document.querySelectorAll('button, input, select, textarea, .panel, .event, .candidate, .badge')];
    const vis = els.filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    for (const e of vis) {
      const r = e.getBoundingClientRect();
      if (r.right > window.innerWidth + 2 && !e.closest('.col')) issues.out_of_viewport.push({tag: e.tagName, cls: e.className, right: r.right});
      if ((e.tagName === 'BUTTON' || e.tagName === 'INPUT') && r.width < 24 && r.height < 16) issues.tiny_click_targets.push({cls: e.className});
      const st = getComputedStyle(e);
      if (st.overflowX === 'hidden' && e.scrollWidth > e.clientWidth + 4 && e.tagName !== 'TEXTAREA') issues.clipped.push({cls: e.className, scrollW: e.scrollWidth, clientW: e.clientWidth});
    }
    issues.horizontal_scroll = document.documentElement.scrollWidth > document.documentElement.clientWidth + 2;
    return issues;
  })()`;

  const summary = { viewports: [] };
  for (const [w, h] of VIEWPORTS) {
    await win.setViewportSize({ width: w, height: h });
    await wait(900);
    const tag = `${w}x${h}`;
    const shot = path.join(OUT, 'screenshots', `desktop-${tag}.png`);
    await win.screenshot({ path: shot });
    const audit = await win.evaluate(AUDIT_JS.replace(/^\(\(\) => \{/, '(() => {').replace(/\}\)\(\)$/, '') + '()', undefined).catch(e => ({ error: String(e) }));
    let auditRes = audit;
    try { auditRes = await win.evaluate(`(() => { ${AUDIT_JS.match(/\\(\\(\\) => \\{([\\s\\S]*)\\}\\)\\(\\)/)[1]} })()`); } catch (e) { /* fallthrough */ }
    // simpler: re-run the IIFE text
    let res2;
    try {
      res2 = await win.evaluate("(() => { const issues = { overlaps: [], clipped: [], out_of_viewport: [], tiny_click_targets: [], horizontal_scroll: false }; const els = [...document.querySelectorAll('button, input, select, textarea, .panel, .event, .candidate, .badge')]; const vis = els.filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }); for (const e of vis) { const r = e.getBoundingClientRect(); if (r.right > window.innerWidth + 2 && !e.closest('.col')) issues.out_of_viewport.push({tag: e.tagName, cls: e.className, right: r.right}); if ((e.tagName === 'BUTTON' || e.tagName === 'INPUT') && r.width < 24 && r.height < 16) issues.tiny_click_targets.push({cls: e.className}); } issues.horizontal_scroll = document.documentElement.scrollWidth > document.documentElement.clientWidth + 2; return issues; })()");
    } catch (e) { res2 = { error: String(e) }; }
    summary.viewports.push({ viewport: [w, h], screenshot: shot, audit: res2 });
    console.log(`${tag}: screenshot + audit done`);
  }

  // state walkthrough at default viewport: planning + search
  await win.setViewportSize({ width: 1920, height: 1080 });
  await wait(600);
  await win.fill('#req-text', '帮我构建 2012—2024 年中国地级市层面的数字经济、地方财政压力、环境规制、人口老龄化、产业升级面板数据。');
  await win.click('#btn-agent-plan');
  await wait(4000);
  const planVisible = await win.locator('#agent-plan-card').isVisible().catch(() => false);
  await win.screenshot({ path: path.join(OUT, 'screenshots', 'desktop-planning-1920x1080.png') });
  console.log('PLANNING VISIBLE:', planVisible);

  fs.writeFileSync(path.join(OUT, 'visual-audit', 'desktop-audit.json'), JSON.stringify({ summary, consoleErrors }, null, 2));
  console.log('CONSOLE_ERRORS:', consoleErrors.length);
  await electronApp.close();
  backend.kill();
  process.exit(0);
})().catch(e => { console.error('VISUAL FAIL:', e.message); process.exit(1); });
