"use strict";

function classifyDisconnected(error) {
  const message = String(error?.message || error || "Game connection unavailable.");
  if (/fetch failed|econnrefused|network|aborted|ECONNREFUSED/i.test(message)) {
    return {
      state: "disconnected",
      headline: "Start Borderlands 4",
      detail:
        "Launch Borderlands 4",
    };
  }
  if (message.includes("abort")) {
    return {
      state: "disconnected",
      headline: "Game not responding",
      detail:
        "Borderlands 4 may still be loading. Wait on a character, then press Refresh status.",
    };
  }
  return {
    state: "disconnected",
    headline: "Game not connected",
    detail: `${message}  →  Start Borderlands 4, load a character, then press Refresh status.`,
  };
}

function classifyConnected(status) {
  const connection = status?.connection_state || "";
  const actionsAvailable = Boolean(status?.actions_available);
  if (connection === "ready" || actionsAvailable) {
    return {
      state: "ready",
      headline: "Connected!",
      detail: "lets mod",
      actionsAvailable: true,
    };
  }
  if (status?.has_local_pc || (status?.players && status.players.length)) {
    return {
      state: "connected",
      headline: "Connected!",
      detail: "lets mod",
      actionsAvailable: true,
    };
  }
  return {
    state: "in_menu_or_loading",
    headline: "Connected — enter a save",
    detail: "Load a character (not the main menu) to unlock Most used and the other tabs.",
    actionsAvailable: false,
  };
}

module.exports = {
  classifyDisconnected,
  classifyConnected,
};
