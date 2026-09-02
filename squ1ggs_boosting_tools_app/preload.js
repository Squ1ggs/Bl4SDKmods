"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("sqbt", {
  getStatus: () => ipcRenderer.invoke("sqbt:get-status"),
  checkForUpdates: (force = false, currentModVersion = "") =>
    ipcRenderer.invoke("sqbt:check-for-updates", force, currentModVersion || ""),
  postAction: (action, payload, timeout) => ipcRenderer.invoke("sqbt:post-action", action, payload, timeout),
  getManifest: () => ipcRenderer.invoke("sqbt:get-manifest"),
  getCatalog: (name, payload) => ipcRenderer.invoke("sqbt:get-catalog", name, payload),
  getListFavorites: () => ipcRenderer.invoke("sqbt:get-list-favorites"),
  toggleListFavorite: (bucket, id) => ipcRenderer.invoke("sqbt:toggle-list-favorite", bucket, id),
  getSetup: () => ipcRenderer.invoke("sqbt:get-setup"),
  dismissSetup: () => ipcRenderer.invoke("sqbt:dismiss-setup"),
  setTheme: (theme) => ipcRenderer.invoke("sqbt:set-theme", theme),
  setLocale: (locale) => ipcRenderer.invoke("sqbt:set-locale", locale),
  unlockHiddenShapes: () => ipcRenderer.invoke("sqbt:unlock-hidden-shapes"),
  readSerialSource: (filePath) => ipcRenderer.invoke("sqbt:read-serial-source", filePath),
  pickSerialFile: () => ipcRenderer.invoke("sqbt:pick-serial-file"),
  pickGameFolder: () => ipcRenderer.invoke("sqbt:pick-game-folder"),
  installSdkmod: (options = {}) => ipcRenderer.invoke("sqbt:install-sdkmod", options || {}),
  applyGithubUpdate: (currentModVersion = "") =>
    ipcRenderer.invoke("sqbt:apply-github-update", currentModVersion || ""),
  onUpdateProgress: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("sqbt:update-progress", listener);
    return () => ipcRenderer.removeListener("sqbt:update-progress", listener);
  },
  onModSync: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("sqbt:mod-sync", listener);
    return () => ipcRenderer.removeListener("sqbt:mod-sync", listener);
  },
  openExternal: (url) => ipcRenderer.invoke("sqbt:open-external", url),
  openPath: (targetPath) => ipcRenderer.invoke("sqbt:open-path", targetPath),
  snapWindow: (edge = "right") => ipcRenderer.invoke("sqbt:snap-window", edge),
  onStatus: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("bridge-status", listener);
    return () => ipcRenderer.removeListener("bridge-status", listener);
  },
});
