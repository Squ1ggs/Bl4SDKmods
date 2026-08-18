"use strict";

const PRODUCT_ID = "squ1ggs-boosting-tools";
const BRIDGE_HOST = "127.0.0.1";
const BRIDGE_PORTS = [49775, 49776, 49777, 49778, 49779, 49780, 49781, 49782, 49783, 49784];
const CLIENT_HEADER = "squ1ggs-boosting-tools-exe";

let activePort = BRIDGE_PORTS[0];
let discoveredAt = 0;

function bridgeBase() {
  return `http://${BRIDGE_HOST}:${activePort}`;
}

function isSqbtStatus(data) {
  if (!data || typeof data !== "object") return false;
  const id = String(data.product_id || "").trim().toLowerCase();
  if (id === PRODUCT_ID) return true;
  const name = String(data.name || "").toLowerCase();
  const author = String(data.product_author || data.author || "").toLowerCase();
  return name.includes("squ1ggs") && name.includes("boosting") && author.includes("squ1ggs");
}

async function probePort(port, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`http://${BRIDGE_HOST}:${port}/status`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Sqbt-Client": CLIENT_HEADER,
      },
      signal: controller.signal,
    });
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    if (response.ok && isSqbtStatus(data)) return data;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
  return null;
}

async function ensureBridgePort(force = false) {
  const now = Date.now();
  if (!force && discoveredAt && now - discoveredAt < 4000) return activePort;
  const order = [activePort, ...BRIDGE_PORTS.filter((port) => port !== activePort)];
  const hits = await Promise.all(order.map((port) => probePort(port, 700).then((data) => ({ port, data }))));
  const match = hits.find((row) => row.data);
  if (match) {
    activePort = match.port;
    discoveredAt = now;
  }
  return activePort;
}

function getBridgeBase() {
  return bridgeBase();
}

async function fetchJson(path, options = {}) {
  await ensureBridgePort(Boolean(options.rediscover));
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 4000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${bridgeBase()}${path}`, {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        "X-Sqbt-Client": CLIENT_HEADER,
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
    if (path === "/status" && data?.ok && !isSqbtStatus(data)) {
      discoveredAt = 0;
      await ensureBridgePort(true);
      if (isSqbtStatus(data)) return { httpStatus: response.status, data };
      return {
        httpStatus: 409,
        data: {
          ok: false,
          message: "Another tool is on the live desktop port. Enable Squ1ggs Boosting Tools in Mods, then Refresh.",
        },
      };
    }
    return { httpStatus: response.status, data };
  } finally {
    clearTimeout(timer);
  }
}

const { classifyDisconnected, classifyConnected } = require("./status");

async function getBridgeStatus() {
  try {
    discoveredAt = 0;
    const { httpStatus, data } = await fetchJson("/status", { rediscover: true, timeoutMs: 2500 });
    if (httpStatus >= 400 || !data?.ok) {
      return {
        connected: false,
        ...classifyDisconnected(new Error(data?.message || `HTTP ${httpStatus}`)),
        raw: data,
      };
    }
    if (!isSqbtStatus(data)) {
      return {
        connected: false,
        ...classifyDisconnected(
          new Error("Another live-tool mod answered first. Enable Squ1ggs Boosting Tools in Mods, then Refresh."),
        ),
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
  try {
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
  } catch (error) {
    const msg = String(error?.message || error);
    if (/fetch failed|econnrefused|network|aborted|ECONNREFUSED/i.test(msg)) {
      throw new Error(
        "Borderlands 4 is not running (or still loading). Start the game, load a character, then press Refresh status.",
      );
    }
    throw error;
  }
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
  getBridgeBase,
  get BRIDGE_BASE() {
    return bridgeBase();
  },
  get BRIDGE_PORT() {
    return activePort;
  },
  fetchJson,
  fetchManifest,
  fetchCatalog,
  getBridgeStatus,
  postAction,
};
