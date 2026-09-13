/**
Metis Data — Electron desktop shell (main process).

Responsibilities:
1. Launch/attach the FastAPI backend (uvicorn) as a child process.
2. Open the BrowserWindow immediately with a start screen.
3. Navigate to the local UI once the backend health endpoint responds.
4. Shut the backend down (process tree) when the window closes.

Security: contextIsolation on, nodeIntegration off, no remote content.
*/
const { app, BrowserWindow, dialog, shell } = require('electron');
const { spawn, exec } = require('child_process');
const http = require('http');
const path = require('path');

const PORT = Number(process.env.METIS_PORT || 8300);
const HOST = '127.0.0.1';
const BASE_URL = `http://${HOST}:${PORT}`;
const REPO_ROOT = path.resolve(__dirname, '..', '..');
const BACKEND_DIR = path.join(REPO_ROOT, 'metis', 'backend');

let mainWindow = null;
let backendProc = null;
let shuttingDown = false;

const START_HTML = `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
<html><head><meta charset="utf-8"><style>
  body{margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:#0b0d12;color:rgba(255,255,255,.9);font-family:system-ui;font-size:18px;flex-direction:column;gap:12px}
  .dot{width:10px;height:10px;border-radius:50%;background:#4f8cff;animation:pulse 1.2s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.15)}}
  small{color:rgba(255,255,255,.45)}
</style></head><body>
<div class="dot"></div><div>Metis Data 正在启动…</div><small>starting backend</small>
</body></html>`)}`;

function findPython() {
  return process.env.METIS_PYTHON || 'python';
}

function startBackend() {
  const python = findPython();
  backendProc = spawn(python, ['-u', '-m', 'uvicorn', 'app.api.main:app', '--host', HOST, '--port', String(PORT)], {
    cwd: BACKEND_DIR,
    env: { ...process.env, PYTHONUNBUFFERED: '1', METIS_DESKTOP: '1' },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const forward = (line) => console.log(`[backend] ${line}`);
  require('readline').createInterface({ input: backendProc.stdout }).on('line', forward);
  require('readline').createInterface({ input: backendProc.stderr }).on('line', (l) => console.error(`[backend] ${l}`));

  backendProc.on('exit', (code) => {
    backendProc = null;
    if (!shuttingDown && mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox('Metis Data 后端已退出', `后端进程异常退出（code=${code ?? 'null'}）。\n请重启 Metis Data。`);
      if (mainWindow) mainWindow.close();
    }
  });
}

function waitForBackend(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const rq = http.get(`${BASE_URL}/api/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      });
      rq.on('error', retry);
      rq.setTimeout(2000, () => { rq.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() > deadline) return reject(new Error('backend health timeout'));
      setTimeout(tryOnce, 400);
    };
    tryOnce();
  });
}

function killBackendTree() {
  if (!backendProc) return;
  const proc = backendProc;
  backendProc = null;
  if (process.platform === 'win32') {
    exec(`taskkill /pid ${proc.pid} /T /F`);
  } else {
    try { proc.kill('SIGTERM'); } catch (e) { /* already gone */ }
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1280,
    minHeight: 760,
    backgroundColor: '#0b0d12',
    title: 'Metis Data',
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http') && !url.startsWith(BASE_URL)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // start screen first — instant feedback while backend boots
  mainWindow.loadURL(START_HTML);
}

function backendHealthy() {
  return new Promise((resolve) => {
    const rq = http.get(`${BASE_URL}/api/health`, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    rq.on('error', () => resolve(false));
    rq.setTimeout(1500, () => { rq.destroy(); resolve(false); });
  });
}

app.whenReady().then(async () => {
  createWindow();
  // reuse an already-running backend if present (e.g. dev workflow); else spawn one
  const alreadyUp = await backendHealthy();
  if (!alreadyUp) startBackend();
  try {
    await waitForBackend();
  } catch (e) {
    if (mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox('Metis Data 启动失败', '后端服务未能在 60 秒内就绪。\n请检查 Python 环境与端口占用后重启应用。');
      app.quit();
      return;
    }
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    await mainWindow.loadURL(`${BASE_URL}/`);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  shuttingDown = true;
  killBackendTree();
  app.quit();
});

app.on('before-quit', () => {
  shuttingDown = true;
  killBackendTree();
});

process.on('exit', () => {
  if (backendProc && process.platform === 'win32') {
    try { exec(`taskkill /pid ${backendProc.pid} /T /F`); } catch (e) { /* exiting */ }
  }
});
