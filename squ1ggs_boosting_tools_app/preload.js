"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("sqbt", {
  getStatus: () => ipcRenderer.invoke("sqbt:get-status"),
  analyzeItem: (serial, hints = {}) =>
    ipcRenderer.invoke("sqbt:analyze-item", serial || "", hints || {}),
  nexusCardStats: (props) => ipcRenderer.invoke("sqbt:nexus-card-stats", props || {}),
  inlineCardAssets: (model) => ipcRenderer.invoke("sqbt:inline-card-assets", model || {}),
  checkForUpdates: (force = false, currentModVersion = "") =>
    ipcRenderer.invoke("sqbt:check-for-updates", force, currentModVersion || ""),
  postAction: (action, payload, timeout) => ipcRenderer.invoke("sqbt:post-action", action, payload, timeout),
  getManifest: () => ipcRenderer.invoke("sqbt:get-manifest"),
  getOfflineManifest: () => ipcRenderer.invoke("sqbt:get-offline-manifest"),
  getCatalog: (name, payload) => ipcRenderer.invoke("sqbt:get-catalog", name, payload),
  getListFavorites: () => ipcRenderer.invoke("sqbt:get-list-favorites"),
  toggleListFavorite: (bucket, id) => ipcRenderer.invoke("sqbt:toggle-list-favorite", bucket, id),
  getSetup: () => ipcRenderer.invoke("sqbt:get-setup"),
  dismissSetup: () => ipcRenderer.invoke("sqbt:dismiss-setup"),
  setTheme: (theme) => ipcRenderer.invoke("sqbt:set-theme", theme),
  setGhostOpacity: (opacity) => ipcRenderer.invoke("sqbt:set-ghost-opacity", opacity),
  getGhostOpacity: () => ipcRenderer.invoke("sqbt:get-ghost-opacity"),
  packBayScan: (payload) => ipcRenderer.invoke("sqbt:pack-bay-scan", payload || {}),
  packBayListSaves: () => ipcRenderer.invoke("sqbt:pack-bay-list-saves"),
  setLocale: (locale) => ipcRenderer.invoke("sqbt:set-locale", locale),
  unlockHiddenShapes: () => ipcRenderer.invoke("sqbt:unlock-hidden-shapes"),
  readSerialSource: (filePath) => ipcRenderer.invoke("sqbt:read-serial-source", filePath),
  pickSerialFile: () => ipcRenderer.invoke("sqbt:pick-serial-file"),
  pickItemImage: () => ipcRenderer.invoke("sqbt:pick-item-image"),
  identifyItemImage: (payload = {}) =>
    ipcRenderer.invoke("sqbt:identify-item-image", payload || {}),
  rankItemImage: (extracted = {}, rows = []) =>
    ipcRenderer.invoke("sqbt:rank-item-image", extracted || {}, rows || []),
  pickGameFolder: () => ipcRenderer.invoke("sqbt:pick-game-folder"),
  promptMissingGameFolder: () => ipcRenderer.invoke("sqbt:prompt-missing-game-folder"),
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
