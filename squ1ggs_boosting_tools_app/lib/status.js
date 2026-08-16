"use strict";

function classifyDisconnected(error) {
  const message = String(error?.message || error || "Game connection unavailable.");
  if (message.includes("abort")) {
    return {
      state: "disconnected",
      headline: "Game not responding",
      detail:
        "Start Borderlands 4, load a character, then Refresh status. First use: Setup → Install SDK + Squ1ggs mod, then fully restart the game.",
    };
  }
  return {
    state: "disconnected",
    headline: "Game not connected",
    detail: `${message}  →  First use: Setup → Install SDK + Squ1ggs mod, fully restart Borderlands 4, load a character, then Refresh status.`,
  };
}

function classifyConnected(status) {
  const connection = status?.connection_state || "";
  const actionsAvailable = Boolean(status?.actions_available);
  const detailBase = `${status.session || "In session"} · mod ${status.mod_version || "?"}`;
  if (connection === "ready" || actionsAvailable) {
    return {
      state: "ready",
      headline: "Connected — ready for actions",
      detail: detailBase,
      actionsAvailable: true,
    };
  }
  if (status?.has_local_pc || (status?.players && status.players.length)) {
    return {
      state: "connected",
      headline: "Connected — session detected",
      detail: `${detailBase} · actions enabled`,
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
