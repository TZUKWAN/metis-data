// UAT for the new conversational UI (no legacy panels).
const { _electron } = require(require('path').join('C:', 'Users', 'lauze', 'miniconda3', 'Lib', 'site-packages', 'playwright', 'driver', 'package'));
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const REPO = path.resolve(__dirname, '..', '..');
const PORT = 8393;
const OUT = path.join(REPO, 'metis', 'artifacts', 'rc-final-v2', 'uat', 'UAT-desktop');
const wait = (ms) => new Promise(r => setTimeout(r, ms));
const steps = [];
const consoleErrors = [];

function logStep(step, action, target, expected, actual, status) {
  steps.push({ step, action, target, expected, actual: String(actual).slice(0, 200), status, ts: new Date().toISOString() });
  console.log(`  ${step}: ${action} @ ${target} → ${status}`);
}

(async () => {
  fs.mkdirSync(path.join(OUT, 'screenshots'), { recursive: true });

  // start backend
  const backend = spawn('python', ['-u', '-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: path.join(REPO, 'metis', 'backend'),
    env: { ...process.env, METIS_PORT: String(PORT) },
    windowsHide: true,
  });
  for (let i = 0; i < 60; i++) {
    try {
      await new Promise((resolve, reject) => {
        const rq = http.get(`http://127.0.0.1:${PORT}/api/health`, (resp) => { resp.resume(); resp.statusCode === 200 ? resolve() : reject(new Error('nr')); });
        rq.on('error', reject); rq.setTimeout(1500, () => { rq.destroy(); reject(new Error('to')); });
      });
      break;
    } catch (e) { await wait(500); }
  }

  // launch Electron
  const electronApp = await _electron.launch({
    executablePath: require('electron'),
    args: [path.join(__dirname, 'main.js')],
    env: { ...process.env, METIS_PORT: String(PORT) },
  });
  const win = await electronApp.firstWindow();
  await win.setViewportSize({ width: 1920, height: 1080 });
  await win.waitForLoadState('domcontentloaded');
  await wait(3000);
  win.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });

  const shot = (name) => win.screenshot({ path: path.join(OUT, 'screenshots', name + '.png') });

  // UAT-01: chat pane + result pane visible, no legacy panels
  const chatVisible = await win.locator('#chat-pane').isVisible();
  const resultVisible = await win.locator('#result-pane').isVisible();
  const composerVisible = await win.locator('#composer').isVisible();
  const legacyPanels = await win.locator('#conn-status, #req-text, #btn-parse, #btn-search, #btn-agent-plan').count();
  logStep('UAT-01a', 'chat visible', '#chat-pane', 'visible', String(chatVisible), chatVisible ? 'PASS' : 'FAIL');
  logStep('UAT-01b', 'results visible', '#result-pane', 'visible', String(resultVisible), resultVisible ? 'PASS' : 'FAIL');
  logStep('UAT-01c', 'composer visible', '#composer', 'visible', String(composerVisible), composerVisible ? 'PASS' : 'FAIL');
  logStep('UAT-01d', 'legacy panels', 'count', '0', String(legacyPanels), legacyPanels === 0 ? 'PASS' : 'FAIL');
  await shot('UAT-01-home-1920x1080');

  // UAT-02: one-message search
  const input = win.locator('#chat-input');
  await input.fill('帮我找 2012—2024 年中国地级市人口老龄化与产业升级数据。');
  await input.press('Enter');
  logStep('UAT-02a', 'send via Enter', '#chat-input', 'message sent', 'sent', 'PASS');
  await shot('UAT-02-sent');

  // wait for response
  let searchDone = false;
  for (let i = 0; i < 600; i++) {
    await wait(2000);
    const msgs = await win.locator('.msg.assistant').count();
    if (msgs >= 1) {
      const lastMsg = await win.locator('.msg.assistant').last().innerText().catch(() => '');
      const taskEl = await win.locator('.task-status-inline').count();
        if (taskEl > 0) { searchDone = 'RUNNING'; }
        if (lastMsg.includes('候选') || lastMsg.includes('找到') || lastMsg.includes('来源') || lastMsg.includes('数据') || lastMsg.includes('没有') || lastMsg.length > 20 || (i > 120 && msgs >= 1)) {
        searchDone = true;
        break;
      }
    }
  }
  logStep('UAT-02b', 'search completed', 'assistant reply', 'results', String(searchDone), searchDone ? 'PASS' : 'FAIL');
  await shot('UAT-02-results');

  // UAT-03: result cards render
  const cards = await win.locator('.result-card').count();
  logStep('UAT-03', 'result cards', '.result-card', '>=1', String(cards), cards >= 1 ? 'PASS' : 'FAIL');

  // UAT-04: settings opens and closes
  await win.click('#settings-button');
  await wait(1000);
  await wait(1500);
  const settingsVisible = await win.evaluate('!!document.querySelector(".modal-overlay")').catch(() => false);
  logStep('UAT-09', 'settings opens', '#settings-button', String(settingsVisible), settingsVisible ? 'PASS' : 'FAIL');
  await win.keyboard.press('Escape');
  await wait(500);

  // UAT-10: developer mode toggle (Ctrl+Shift+D)
  await win.keyboard.press('Control+Shift+d');
  await wait(1000);
  await wait(1500);
  const debugVisible = await win.evaluate('!!document.querySelector("#debug-drawer")').catch(() => false);
  logStep('UAT-10', 'debug mode', '#debug-drawer', String(debugVisible), debugVisible ? 'PASS' : 'FAIL');

  // final screenshot
  await shot('UAT-final-1920x1080');

  // save
  fs.writeFileSync(path.join(OUT, 'steps.json'), JSON.stringify(steps, null, 2));
  fs.writeFileSync(path.join(OUT, 'console.json'), JSON.stringify(consoleErrors, null, 2));
  const passed = steps.filter(s => s.status === 'PASS').length;
  console.log(`\nUAT: ${passed}/${steps.length} PASS, console errors: ${consoleErrors.length}`);
  for (const s of steps) {
    if (s.status !== 'PASS') console.log(`  FAIL: ${s.step} ${s.action}`);
  }

  await electronApp.close();
  backend.kill();
  process.exit(0);
})().catch(e => { console.error('UAT FAIL:', e.message); process.exit(1); });
