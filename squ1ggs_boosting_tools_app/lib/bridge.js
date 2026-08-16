"use strict";

const BRIDGE_HOST = "127.0.0.1";
const BRIDGE_PORT = 49775;
const BRIDGE_BASE = `http://${BRIDGE_HOST}:${BRIDGE_PORT}`;

async function fetchJson(path, options = {}) {
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 4000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BRIDGE_BASE}${path}`, {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { ok: false, message: text || "Invalid response from the game." };
    }
    return { httpStatus: response.status, data };
  } finally {
    clearTimeout(timer);
  }
}

const { classifyDisconnected, classifyConnected } = require("./status");

async function getBridgeStatus() {
  try {
    const { httpStatus, data } = await fetchJson("/status");
    if (httpStatus >= 400 || !data?.ok) {
      return {
        connected: false,
        ...classifyDisconnected(new Error(data?.message || `HTTP ${httpStatus}`)),
        raw: data,
      };
    }
    const ui = classifyConnected(data);
    return {
      connected: true,
      ...ui,
      raw: data,
    };
  } catch (error) {
    return {
      connected: false,
      ...classifyDisconnected(error),
      raw: null,
    };
  }
}

async function postAction(action, payload = {}, timeout = 12) {
  let httpStatus;
  let data;
  try {
    ({ httpStatus, data } = await fetchJson("/action", {
      method: "POST",
      timeoutMs: (timeout + 4) * 1000,
      body: { action, payload, timeout },
    }));
  } catch (error) {
    const text = String(error?.message || error);
    if (error?.name === "AbortError" || /aborted/i.test(text)) {
      return {
        httpStatus: 0,
        data: {
          ok: false,
          message:
            "The game took too long to respond. Stay in-game unpaused and retry, or pick a narrower pool filter.",
        },
      };
    }
    return {
      httpStatus: 0,
      data: {
        ok: false,
        message:
          "Could not connect to Borderlands 4. If the game crashed, restart it and refresh status.",
      },
    };
  }
  if (httpStatus === 404) {
    return {
      httpStatus,
      data: {
        ok: false,
        message: `This action needs the latest mod version. Restart Borderlands 4, then retry.`,
      },
    };
  }
  if (httpStatus === 202 && data?.queued) {
    return {
      httpStatus,
      data: {
        ok: false,
        message:
          (data.message || "Action queued.") +
          " Be in-game, unpaused, then click Refresh and retry.",
      },
    };
  }
  return { httpStatus, data };
}

async function fetchManifest() {
  const { httpStatus, data } = await fetchJson("/manifest");
  if (httpStatus === 404) {
    throw new Error(
      "Manifest not found (HTTP 404). Fully restart Borderlands 4 so mod v3.6.19+ loads, then refresh.",
    );
  }
  if (httpStatus >= 400 || !data?.ok) {
    throw new Error(data?.message || `Manifest HTTP ${httpStatus}`);
  }
  return data.manifest || data;
}

async function fetchCatalog(name, payload = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(payload || {})) {
    if (value !== undefined && value !== null && String(value) !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  const path = qs ? `/catalog/${encodeURIComponent(name)}?${qs}` : `/catalog/${encodeURIComponent(name)}`;
  const { httpStatus, data } = await fetchJson(path, { method: "GET" });
  if (httpStatus >= 400 || !data?.ok) {
    throw new Error(data?.message || `Catalog HTTP ${httpStatus}`);
  }
  return data;
}

module.exports = {
  BRIDGE_BASE,
  BRIDGE_PORT,
  fetchJson,
  fetchManifest,
  fetchCatalog,
  getBridgeStatus,
  postAction,
};
