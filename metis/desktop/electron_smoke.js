// Electron smoke: launch the app, wait for UI, report window state.
const { _electron } = require(require('path').join('C:', 'Users', 'lauze', 'miniconda3', 'Lib', 'site-packages', 'playwright', 'driver', 'package'));
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const REPO = path.resolve(__dirname, '..', '..');
const PORT = 8391;

(async () => {
  // start backend on a scratch port
  const backend = spawn('python', ['-u', '-m', 'uvicorn', 'app.api.main:app', '--host', '127.0.0.1', '--port', String(PORT)], {
    cwd: path.join(REPO, 'metis', 'backend'),
    env: { ...process.env, METIS_PORT: String(PORT), METIS_WORKSPACE_DIR: path.join(REPO, 'metis', 'workspace') },
    windowsHide: true,
  });
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
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
    } catch (e) {
      await wait(500);
    }
  }
  if (!ready) {
    console.error('backend not ready');
    backend.kill();
    process.exit(1);
  }

  const electronExe = require('electron');
  const electronApp = await _electron.launch({
    executablePath: electronExe,
    args: [path.join(__dirname, 'main.js')],
    env: { ...process.env, METIS_PORT: String(PORT) },
  });
  electronApp.process().stdout.on('data', d => process.stdout.write('[el] ' + d));
  electronApp.process().stderr.on('data', d => process.stderr.write('[el-err] ' + d));
  await wait(3000);
  console.log('electron pid:', electronApp.process().pid);
  const win = await electronApp.firstWindow();
  await win.setViewportSize({ width: 1600, height: 1000 });
  await win.waitForFunction('document.readyState === "complete" && location.href.includes("8391")', { timeout: 90000 }).catch(() => {});
  await win.waitForLoadState('domcontentloaded').catch(() => {});
  await wait(2500);
  const title = await win.title();
  const connText = await win.locator('#conn-status').innerText().catch(() => 'n/a');
  console.log('TITLE:', title);
  console.log('CONN:', connText);
  const shotDir = path.join(REPO, 'metis', 'artifacts', 'rc-final-v2', 'screenshots');
  require('fs').mkdirSync(shotDir, { recursive: true });
  await win.screenshot({ path: path.join(shotDir, 'electron-home-1600x1000.png') });
  console.log('SCREENSHOT OK');
  await electronApp.close();
  backend.kill();
  process.exit(0);
})().catch(e => { console.error('SMOKE FAIL:', e.message); process.exit(1); });
