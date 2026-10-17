"use strict";
const path = require("path");
const fs = require("fs");
const { app, BrowserWindow, protocol } = require("electron");
const { registerNativeCardSchemes, installNativeCardProtocol } = require("../native_card_protocol");
const { toNativeCardModel } = require("../native_card_model");

registerNativeCardSchemes(protocol);

app.whenReady().then(async () => {
  const uiRoot = path.join(__dirname, "..", "native_card_ui");
  installNativeCardProtocol(protocol, uiRoot);

  const entry = {
    display_name: "Sudden Looming Truck",
    rarity: "Legendary",
    manufacturer: "Jakobs",
    item_type: "Sniper",
    level: 60,
    dps: 15896,
    damage: 22526,
    accuracy: 88,
    reload: 2.4,
    fire_rate: 0.9,
    magazine: 10,
    crit: 146,
    damage_radius: 100,
    description_lines: ["Fixer-Upper", "Torgue-Licensed Impact Magazine"],
    red_text: ["To truly be old-school: build it yourself."],
    value: 1220277,
  };
  const model = toNativeCardModel(entry);

  const htmlPath = path.join(__dirname, "_smoke_native_card.html");
  fs.writeFileSync(
    htmlPath,
    `<!doctype html>
<html><head><meta charset="utf-8"><title>smoke</title></head>
<body style="background:#111;margin:0;padding:12px">
<div id="host"></div>
<script src="../renderer/native_card_model.js"></script>
<script src="../renderer/native_item_card.js"></script>
<script>
window.__SMOKE_ENTRY__ = ${JSON.stringify(entry)};
window.__SMOKE_MODEL__ = ${JSON.stringify(model)};
const host = document.getElementById("host");
host.style.width = "546px";
window.SQBTNativeItemCard.fillNativeItemCard(host, window.__SMOKE_ENTRY__);
</script>
</body></html>`
  );

  const win = new BrowserWindow({
    width: 700,
    height: 1000,
    show: false,
    webPreferences: {
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  await win.loadFile(htmlPath);

  const deadline = Date.now() + 12000;
  let result = null;
  while (Date.now() < deadline) {
    result = await win.webContents.executeJavaScript(`(() => {
      const frame = document.querySelector("iframe");
      if (!frame) return { stage: "no-frame" };
      return {
        stage: "frame",
        src: frame.src,
        height: frame.style.height || null,
        rendered: frame.dataset.rendered || null,
        errors: frame.dataset.renderErrors || null,
      };
    })()`);
    if (result.rendered === "true" || result.errors) break;
    await new Promise((r) => setTimeout(r, 200));
  }

  const frames = win.webContents.mainFrame.frames;
  const cardFrame = frames.find((f) => String(f.url || "").startsWith("sqbt-card:"));
  let inner = { missing: true };
  if (cardFrame) {
    try {
      inner = await cardFrame.executeJavaScript(`({
        name: document.querySelector(".item_card_name")?.textContent || null,
        kids: document.getElementById("card-host")?.children?.length || 0,
        text: (document.body.innerText || "").slice(0, 240),
        bg: getComputedStyle(document.querySelector(".item_card_bkg") || document.body).backgroundImage,
        width: document.querySelector(".item_card")?.getBoundingClientRect()?.width || 0,
        height: document.querySelector(".item_card")?.getBoundingClientRect()?.height || 0,
        hasRender: typeof renderNativeCard,
      })`);
    } catch (error) {
      inner = { evalError: String(error) };
    }
  }

  const outDir = path.join(__dirname, "..", "_tmp_native_card_preview");
  fs.mkdirSync(outDir, { recursive: true });
  try {
    const png = await win.webContents.capturePage();
    fs.writeFileSync(path.join(outDir, "smoke.png"), png.toPNG());
  } catch {
    /* ignore */
  }

  console.log(JSON.stringify({ result, inner, frameCount: frames.length }, null, 2));
  win.destroy();
  app.exit(0);
}).catch((error) => {
  console.error(error);
  app.exit(1);
});
