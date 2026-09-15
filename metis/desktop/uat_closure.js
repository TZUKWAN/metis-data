// Electron closure UAT (§30-52): real desktop shell + real UI interaction.
// Covers: empty shell, composer send, async responsiveness, real search→results,
// preview, public download→READY, export, refresh-restore, cancel, new conversation,
// console/network cleanliness, multi-resolution screenshots.
const { _electron } = require(require('path').join('C:', 'Users', 'lauze', 'miniconda3', 'Lib', 'site-packages', 'playwright', 'driver', 'package'));
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const http = require('http');

const REPO = path.resolve(__dirname, '..', '..');
const PORT = 8395;
const OUT = path.join(REPO, 'metis', 'artifacts', 'final-closure', 'electron-uat');
const wait = (ms) => new Promise(r => setTimeout(r, ms));
const steps = [];
const consoleErrors = [];
const failedResponses = [];

function logStep(step, action, expected, actual, status) {
  steps.push({ step, action, expected, actual: String(actual).slice(0, 160), status, ts: new Date().toISOString() });
  console.log(`  ${step} ${action} → ${status} (${String(actual).slice(0, 80)})`);
}

async function taskState(win, cid, tid) {
  return await win.evaluate(async ([cid, tid]) => {
    const r = await fetch(`/api/conversations/${cid}/task/${tid}`);
    return await r.json();
  }, [cid, tid]);
}

(async () => {
  fs.mkdirSync(path.join(OUT, 'screenshots'), { recursive: true });
  const backend = spawn('python', ['-u', '-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: path.join(REPO, 'metis', 'backend'),
    env: { ...process.env, METIS_PORT: String(PORT), METIS_LLM_BASE_URL: '', METIS_LLM_API_KEY: '', METIS_LLM_MODEL: '' },
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
  console.log('backend ready on', PORT);

  const electronApp = await _electron.launch({
    executablePath: require('electron'),
    args: [path.join(__dirname, 'main.js')],
    env: { ...process.env, METIS_PORT: String(PORT) },
  });
  const win = await electronApp.firstWindow();
  await win.setViewportSize({ width: 1920, height: 1080 });
  await win.waitForLoadState('domcontentloaded');
  await wait(2500);
  win.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200)); });
  win.on('response', (resp) => {
    const u = resp.url();
    if (resp.status() >= 500 || resp.status() === 404) failedResponses.push(`${resp.status()} ${u.replace(`http://127.0.0.1:${PORT}`, '')}`);
  });
  const shot = (name) => win.screenshot({ path: path.join(OUT, 'screenshots', name + '.png') });

  // UAT-01: empty shell
  {
    const chat = await win.locator('#chat-pane').isVisible();
    const results = await win.locator('#result-pane').isVisible();
    const composer = await win.locator('#composer').isVisible();
    const legacy = await win.locator('#conn-status, #req-text, #btn-parse, #btn-search, #btn-agent-plan').count();
    const ok = chat && results && composer && legacy === 0;
    logStep('UAT-01', 'empty shell (chat+results+composer, legacy=0)', 'all visible, 0 legacy', `chat=${chat} results=${results} composer=${composer} legacy=${legacy}`, ok ? 'PASS' : 'FAIL');
    await shot('01-empty');
  }

  // UAT-02/03: composer + async responsiveness
  let cid = null, tid = null;
  {
    const input = win.locator('#chat-input');
    await input.fill('找青年失业率数据');
    const t0 = Date.now();
    await input.press('Enter');
    await wait(700);
    const cleared = (await input.inputValue()) === '';
    const userMsg = await win.locator('.msg.user').count();
    const statusShown = await win.locator('.task-status-inline').count();
    const ms = Date.now() - t0;
    cid = await win.evaluate(() => localStorage.getItem('metis.conversation_id'));
    const tasks = await win.evaluate(async (cid) => await (await fetch(`/api/conversations/${cid}/tasks`)).json(), cid);
    tid = tasks[0] && tasks[0].task_id;
    const ok = cleared && userMsg >= 1 && statusShown >= 1 && !!tid && ms < 2000;
    logStep('UAT-02', 'Enter sends, input clears, task created', 'cleared+user msg+status+task', `cleared=${cleared} user=${userMsg} status=${statusShown} task=${tid}`, ok ? 'PASS' : 'FAIL');
    logStep('UAT-03', 'async responsiveness', 'status < 2s', `${ms}ms`, ms < 2000 ? 'PASS' : 'FAIL');
    await shot('02-working');
  }

  // UAT-04: real search → COMPLETE + results ≥ 1 (task-state based, §34)
  {
    let t = null, cards = 0;
    for (let i = 0; i < 100; i++) {
      await wait(3000);
      t = await taskState(win, cid, tid);
      cards = await win.locator('.result-card').count();
      if (t.state === 'COMPLETE' || t.state === 'FAILED') break;
    }
    const ok = t && t.state === 'COMPLETE' && cards >= 1;
    logStep('UAT-04', 'real search completes with results', 'COMPLETE + ≥1 card', `state=${t && t.state} cards=${cards}`, ok ? 'PASS' : 'FAIL');
    await shot('03-results');
  }

  // UAT-05: preview (first card metadata or READY data)
  {
    await win.locator('.result-card [data-action="preview"]').first().click();
    await wait(2000);
    const visible = await win.locator('#result-preview').isVisible();
    const listHidden = await win.evaluate(() => document.querySelector('#result-list').classList.contains('hidden'));
    logStep('UAT-05', 'preview replaces list', 'preview visible, list hidden', `visible=${visible} listHidden=${listHidden}`, visible && listHidden ? 'PASS' : 'FAIL');
    await shot('04-preview');
    await win.evaluate(() => document.querySelector('#result-preview [data-back]').click());
    await wait(400);
  }

  // UAT-06: public download on a world_bank card → READY
  {
    const rid = await win.evaluate(() => {
      const cards = [...document.querySelectorAll('.result-card')];
      const wb = cards.find(c => c.textContent.includes('world_bank'));
      if (!wb) return null;
      wb.querySelector('[data-action="download"]').click();
      return wb.getAttribute('data-result');
    });
    let state = null;
    for (let i = 0; i < 30; i++) {
      await wait(4000);
      state = await win.evaluate(async (rid) => (await (await fetch(`/api/results/${rid}`)).json()).state, rid);
      if (state === '可用' || state === '获取失败' || state === '需要登录') break;
    }
    logStep('UAT-06', 'public download → READY', '可用', `state=${state}`, state === '可用' ? 'PASS' : 'FAIL');
    await shot('05-ready');
  }

  // UAT-13: export CSV (real click → Electron will-download saves to Downloads)
  {
    const downloadsDir = path.join(process.env.USERPROFILE || process.env.HOME, 'Downloads');
    const t0 = Date.now() - 5000;
    await win.evaluate(() => {
      const cards = [...document.querySelectorAll('.result-card')];
      const ready = cards.find(c => c.querySelector('.rc-state').textContent === '可用');
      if (ready) ready.querySelector('[data-action="export:csv"]').click();
    });
    let saved = null, size = 0;
    for (let i = 0; i < 20; i++) {
      await wait(1500);
      const hits = fs.readdirSync(downloadsDir)
        .filter(f => f.endsWith('.csv') || f.endsWith('.xlsx'))
        .map(f => path.join(downloadsDir, f))
        .filter(p => { try { return fs.statSync(p).mtimeMs > t0; } catch { return false; } });
      if (hits.length) {
        saved = hits[0];
        size = fs.statSync(saved).size;
        break;
      }
    }
    logStep('UAT-13', 'CSV export downloads file', 'file >100B in Downloads', `file=${saved ? path.basename(saved) : 'none'} size=${size}`, size > 100 ? 'PASS' : 'FAIL');
  }

  // UAT-14: refresh restore
  {
    await win.reload();
    await wait(3000);
    const msgs = await win.locator('.msg').count();
    const cards = await win.locator('.result-card').count();
    const ok = msgs >= 2 && cards >= 1;
    logStep('UAT-14', 'refresh restores messages+results', '≥2 msgs, ≥1 card', `msgs=${msgs} cards=${cards}`, ok ? 'PASS' : 'FAIL');
  }

  // UAT-17: cancel a running task
  {
    const input = win.locator('#chat-input');
    await input.fill('找GDP数据');
    await input.press('Enter');
    await wait(1500);
    const stopBtn = win.locator('.task-stop').first();
    let state = null;
    if (await stopBtn.isVisible().catch(() => false)) {
      await stopBtn.click();
      await wait(2500);
      cid = await win.evaluate(() => localStorage.getItem('metis.conversation_id'));
      const tasks = await win.evaluate(async (cid) => await (await fetch(`/api/conversations/${cid}/tasks`)).json(), cid);
      state = tasks[0] && tasks[0].state;
    }
    logStep('UAT-17', 'stop button cancels task', 'CANCELLED', `state=${state}`, state === 'CANCELLED' ? 'PASS' : 'FAIL');
  }

  // UAT-15: new conversation resets to empty state
  {
    await win.locator('#new-conversation').click();
    await wait(3500);
    const msgs = await win.locator('.msg').count();
    const cid2 = await win.evaluate(() => localStorage.getItem('metis.conversation_id'));
    const ok = msgs === 0 && cid2 !== cid;
    logStep('UAT-15', 'new conversation isolates', 'fresh empty state', `msgs=${msgs} cidChanged=${cid2 !== cid}`, ok ? 'PASS' : 'FAIL');
  }

  // §52: multi-resolution visual pass
  for (const [w, h] of [[1366, 768], [1600, 900], [2560, 1440]]) {
    await win.setViewportSize({ width: w, height: h });
    await wait(1200);
    await shot(`06-res-${w}x${h}`);
    logStep('VIS', `screenshot ${w}x${h}`, 'captured', 'ok', 'PASS');
  }

  // UAT-19: console/network cleanliness
  {
    const unexpectedErrors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('ERR_ABORTED'));
    const unexpectedFails = failedResponses.filter(u => !u.includes('favicon'));
    logStep('UAT-19', 'console errors = 0', '0', String(unexpectedErrors.length) + (unexpectedErrors[0] ? ` :: ${unexpectedErrors[0]}` : ''), unexpectedErrors.length === 0 ? 'PASS' : 'FAIL');
    logStep('UAT-19', 'unexpected 4xx/5xx = 0', '0', String(unexpectedFails.length) + (unexpectedFails[0] || ''), unexpectedFails.length === 0 ? 'PASS' : 'FAIL');
  }

  fs.writeFileSync(path.join(OUT, 'uat_steps.json'), JSON.stringify(steps, null, 2));
  const pass = steps.filter(s => s.status === 'PASS').length;
  const fail = steps.filter(s => s.status === 'FAIL').length;
  console.log(`\nRESULT: ${pass} PASS / ${fail} FAIL of ${steps.length}`);
  await electronApp.close();
  backend.kill();
  process.exit(fail > 0 ? 1 : 0);
})().catch(e => { console.error('UAT crashed:', e); process.exit(2); });
