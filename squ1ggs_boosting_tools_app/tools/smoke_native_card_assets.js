"use strict";
const path = require("path");
const fs = require("fs");
const { app, BrowserWindow, protocol, net } = require("electron");
const { registerNativeCardSchemes, installNativeCardProtocol } = require("../native_card_protocol");

registerNativeCardSchemes(protocol);

app.whenReady().then(async () => {
  const uiRoot = path.join(__dirname, "..", "native_card_ui");
  installNativeCardProtocol(protocol, uiRoot);

  // Direct protocol fetch test
  const urls = [
    "coui://uiresources/item_card/assets/UI_Art_Assets/item_card_background.png",
    "coui://uiresources/_shared/assets/ui_art_manufacturer_logos/ui_art_manu_itemcard_logotype_jakobs.png",
    "coui://uiresources/_shared/assets/ico_ui_art_item_card_type/ico_art_item_card_weap_sniper.png",
  ];
  for (const url of urls) {
    try {
      const res = await net.fetch(url);
      console.log("FETCH", url, res.status, res.headers.get("content-type"), (await res.arrayBuffer()).byteLength);
    } catch (e) {
      console.log("FETCH FAIL", url, String(e));
    }
  }

  const win = new BrowserWindow({
    width: 700,
    height: 1100,
    show: false,
    webPreferences: { sandbox: true, contextIsolation: true, backgroundThrottling: false },
  });
  await win.loadFile(path.join(__dirname, "_smoke_native_card.html"));
  await new Promise((r) => setTimeout(r, 3000));

  const frames = win.webContents.mainFrame.frames;
  const cardFrame = frames.find((f) => String(f.url || "").startsWith("sqbt-card:"));
  const details = await cardFrame.executeJavaScript(`(() => {
    const bkg = document.querySelector(".item_card_bkg");
    const mfr = document.querySelector(".item_card_manufacturer_bkg");
    const card = document.querySelector(".item_card");
    const cs = (el) => el ? getComputedStyle(el) : null;
    const b = cs(bkg), m = cs(mfr), c = cs(card);
    return {
      borderImage: b && b.borderImageSource,
      bkgBg: b && b.backgroundImage,
      mfrBg: m && m.backgroundImage,
      mfrClass: mfr && mfr.className,
      cardW: card && card.getBoundingClientRect().width,
      cardH: card && card.getBoundingClientRect().height,
      htmlFs: getComputedStyle(document.documentElement).fontSize,
      imgCount: document.images.length,
      failedImgs: [...document.querySelectorAll("*")].filter(n => {
        const s = getComputedStyle(n);
        return /url\\(/.test(s.backgroundImage) || /url\\(/.test(s.borderImageSource);
      }).length,
    };
  })()`);
  console.log("DETAILS", JSON.stringify(details, null, 2));

  const outDir = path.join(__dirname, "..", "_tmp_native_card_preview");
  fs.mkdirSync(outDir, { recursive: true });
  const png = await win.webContents.capturePage();
  fs.writeFileSync(path.join(outDir, "smoke2.png"), png.toPNG());
  console.log("wrote smoke2.png", png.getSize());
  win.destroy();
  app.exit(0);
}).catch((e) => { console.error(e); app.exit(1); });
