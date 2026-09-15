/**
Electron preload — secure bridge between the desktop shell and the UI.

No Node APIs are exposed to the renderer; only a minimal, version-only surface.
*/
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('metisDesktop', {
  platform: process.platform,
  isDesktop: true,
  getAppInfo: () => ipcRenderer.invoke('metis:get-app-info'),
  onDownloadFinished: (cb) => {
    const handler = (_e, payload) => cb(payload);
    ipcRenderer.on('download-finished', handler);
    return () => ipcRenderer.removeListener('download-finished', handler);
  },
});
