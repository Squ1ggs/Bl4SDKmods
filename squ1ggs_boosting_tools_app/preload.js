"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("sqbt", {
  getStatus: () => ipcRenderer.invoke("sqbt:get-status"),
  checkForUpdates: (force = false, currentModVersion = "") =>
    ipcRenderer.invoke("sqbt:check-for-updates", force, currentModVersion || ""),
  postAction: (action, payload, timeout) => ipcRenderer.invoke("sqbt:post-action", action, payload, timeout),
  getManifest: () => ipcRenderer.invoke("sqbt:get-manifest"),
  getCatalog: (name, payload) => ipcRenderer.invoke("sqbt:get-catalog", name, payload),
  getSetup: () => ipcRenderer.invoke("sqbt:get-setup"),
  dismissSetup: () => ipcRenderer.invoke("sqbt:dismiss-setup"),
  pickGameFolder: () => ipcRenderer.invoke("sqbt:pick-game-folder"),
  installSdkmod: () => ipcRenderer.invoke("sqbt:install-sdkmod"),
  openExternal: (url) => ipcRenderer.invoke("sqbt:open-external", url),
  snapWindow: (edge = "right") => ipcRenderer.invoke("sqbt:snap-window", edge),
  onStatus: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("bridge-status", listener);
    return () => ipcRenderer.removeListener("bridge-status", listener);
  },
});
