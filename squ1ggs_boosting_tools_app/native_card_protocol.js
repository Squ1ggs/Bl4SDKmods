"use strict";
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto");
const schemes = ["coui", "common", "sqbt-card", "sqbt-asset"];
const DEFAULT_ASSET_ROOT = path.join(__dirname, "renderer", "editor");
const _assetDataCache = new Map();
const _dlcPngIndex = new Map();

function findPngUnder(root, baseName) {
  const key = String(root || "").toLowerCase();
  let index = _dlcPngIndex.get(key);
  if (!index) {
    index = new Map();
    const walk = (dir, depth = 0) => {
      if (!dir || depth > 10 || !fs.existsSync(dir)) return;
      let entries;
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch {
        return;
      }
      for (const ent of entries) {
        const full = path.join(dir, ent.name);
        if (ent.isDirectory()) walk(full, depth + 1);
        else if (ent.isFile() && /\.png$/i.test(ent.name)) {
          index.set(ent.name.toLowerCase(), full);
        }
      }
    };
    walk(root);
    _dlcPngIndex.set(key, index);
  }
  return index.get(String(baseName || "").toLowerCase()) || null;
}

function registerNativeCardSchemes(protocol) {
  protocol.registerSchemesAsPrivileged(
    schemes.map((scheme) => ({
      scheme,
      privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true },
    }))
  );
}

function resolveSqbtAssetPath(urlStr, assetRoot = DEFAULT_ASSET_ROOT) {
  try {
    const url = new URL(String(urlStr || ""));
    if (url.protocol !== "sqbt-asset:") return null;
    const host = String(url.hostname || "").replace(/\\/g, "/");
    const pathPart = decodeURIComponent(url.pathname || "")
      .replace(/^\/+/, "")
      .replace(/\\/g, "/");
    const rel = [host, pathPart].filter(Boolean).join("/");
    if (!rel || rel.includes("..")) return null;
    const base = path.resolve(assetRoot);
    const file = path.resolve(base, rel);
    if (!file.toLowerCase().startsWith((base + path.sep).toLowerCase())) return null;
    if (fs.existsSync(file) && fs.statSync(file).isFile()) return file;
    // Classmod passive ↔ perks folder fallback (same stem, different pack).
    const alt = rel.replace(/\/classmod-passive\//i, "/classmod-perks/")
      .replace(/\/classmod-perks\//i, "/classmod-passive/");
    if (alt !== rel) {
      const altFile = path.resolve(base, alt);
      if (
        altFile.toLowerCase().startsWith((base + path.sep).toLowerCase()) &&
        fs.existsSync(altFile) &&
        fs.statSync(altFile).isFile()
      ) {
        return altFile;
      }
    }
    // Editor also ships assets/img/... mirrors of img/...
    if (/^img\//i.test(rel)) {
      const underAssets = path.resolve(base, `assets/${rel}`);
      if (
        underAssets.toLowerCase().startsWith((base + path.sep).toLowerCase()) &&
        fs.existsSync(underAssets) &&
        fs.statSync(underAssets).isFile()
      ) {
        return underAssets;
      }
      const underAssetsAlt = path.resolve(
        base,
        `assets/${alt !== rel ? alt : rel.replace(/\/classmod-passive\//i, "/classmod-perks/").replace(/\/classmod-perks\//i, "/classmod-passive/")}`
      );
      if (
        underAssetsAlt.toLowerCase().startsWith((base + path.sep).toLowerCase()) &&
        fs.existsSync(underAssetsAlt) &&
        fs.statSync(underAssetsAlt).isFile()
      ) {
        return underAssetsAlt;
      }
    }
    // DLC skill glyphs shipped under native_card_ui (extraResource) when editor
    // img is missing a stem — same basename under **/Passives|Trait|Action_Skills.
    const baseName = path.basename(rel);
    if (/\.png$/i.test(baseName)) {
      const dlcRoots = [
        path.join(__dirname, "native_card_ui", "DLC"),
        path.join(process.resourcesPath || "", "native_card_ui", "DLC"),
      ];
      for (const dlcRoot of dlcRoots) {
        if (!dlcRoot || !fs.existsSync(dlcRoot)) continue;
        const hit = findPngUnder(dlcRoot, baseName);
        if (hit) return hit;
      }
    }
    return null;
  } catch {
    return null;
  }
}

function sqbtAssetToDataUrl(urlStr, assetRoot = DEFAULT_ASSET_ROOT) {
  const key = String(urlStr || "");
  if (!key || !/^sqbt-asset:/i.test(key)) return key;
  if (_assetDataCache.has(key)) return _assetDataCache.get(key);
  const file = resolveSqbtAssetPath(key, assetRoot);
  if (!file) {
    _assetDataCache.set(key, key);
    return key;
  }
  const ext = path.extname(file).toLowerCase();
  const mime =
    { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml" }[
      ext
    ] || "application/octet-stream";
  const data = `data:${mime};base64,${fs.readFileSync(file).toString("base64")}`;
  _assetDataCache.set(key, data);
  return data;
}

/** Embed leftover sqbt-asset URLs as data: (coui:// stays — painted as background-image). */
function inlineSqbtAssetUrls(value, assetRoot = DEFAULT_ASSET_ROOT) {
  if (typeof value === "string") return sqbtAssetToDataUrl(value, assetRoot);
  if (Array.isArray(value)) return value.map((row) => inlineSqbtAssetUrls(row, assetRoot));
  if (value && typeof value === "object") {
    const out = Array.isArray(value) ? [] : {};
    for (const [k, v] of Object.entries(value)) out[k] = inlineSqbtAssetUrls(v, assetRoot);
    return out;
  }
  return value;
}

/** Keep primary rows intact; only inline any remaining sqbt-asset paths. Never drop icons. */
function prepareClassmodCardModel(model, assetRoot = DEFAULT_ASSET_ROOT) {
  return inlineSqbtAssetUrls(model || {}, assetRoot);
}
function createNativeCardDocument(root = path.join(__dirname, "native_card_ui")) {
  const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
  const templates = Object.fromEntries(
    ["item_card", "rarity_pips", "element_damage_type", "firmware"].map((name) => [
      name,
      read(
        name === "item_card"
          ? `uiresources/${name}/${name}.html`
          : `uiresources/components/${name}/${name}.html`
      ),
    ])
  );
  const filters = new Map();
  const css = (content) =>
    content
      .replace(/coh-color-matrix\(([^)]+)\)/g, (_, values) => {
        const id =
          "matrix" + crypto.createHash("sha256").update(values).digest("hex").slice(0, 12);
        filters.set(id, values.replace(/,/g, " "));
        return `url(#${id})`;
      })
      .replace(/(?<!-)\btext-stroke(?=-|:)/g, "-webkit-text-stroke")
      .replace(/@media \(language: None\)/g, "@media all");
  const styles =
    [
      "_shared/css/gbx.css",
      "_shared/css/oakgame.css",
      "_shared/css/oak_icons.css",
      "_shared/css/oak_markup.css",
      "_shared/css/oak_tooltip.css",
      "_shared/css/color_tint_filters.css",
      "item_card/css/item_card.css",
      "components/rarity_pips/css/rarity_pips.css",
      "components/element_damage_type/css/element_damage_type.css",
      "components/firmware/css/firmware.css",
    ]
      .map((file) => css(read("uiresources/" + file)))
      .join("\n") +
    css(read("DLC/Common/uiresources/dlc_rarity_pips/css/dlc_rarity_pips.css"));
  const scripts = [
    "_shared/js/markup_manager.js",
    "components/rarity_pips/js/rarity_pips.js",
    "components/element_damage_type/js/element_damage_type.js",
    "components/firmware/js/firmware.js",
    "item_card/js/item_card.js",
  ].map((file) => read("uiresources/" + file));
  const script = (content) =>
    `<script>${content.replace(/<\/script/gi, "<\\/script")}</script>`;
  return `<!doctype html><html><head><meta charset="utf-8"><style>${styles}</style>
<style>${fs.readFileSync(path.join(__dirname, "native_card_compat.css"), "utf8")}
html,body{background:transparent!important;color-scheme:dark;margin:0;padding:0 3.2rem;overflow:visible;height:auto;min-height:0;box-sizing:border-box}
html{font-size:10px}
#card-host{position:relative;margin:0;background:transparent;width:100%}
widget-item-card{position:relative;display:block;width:100%!important;max-width:100%!important}widget-item-card>br{display:none}
.item_card,.item_card_tooltip,#def_item_card,#def_item_card_hud{width:100%!important;max-width:100%!important;box-sizing:border-box}
.tooltip_container,.item_card_tooltip{opacity:1!important;visibility:visible!important;transform:none!important;position:relative!important;top:auto!important;left:auto!important}
.item_card_wrapper,#def_item_card_hud .item_card_wrapper{transform:none!important}
svg#filters{position:absolute;width:0;height:0}
</style></head><body><svg id="filters"><defs>${[...filters]
    .map(
      ([id, v]) =>
        `<filter id="${id}" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="${v}"/></filter>`
    )
    .join("")}</defs></svg><div id="card-host"></div>
${script(fs.readFileSync(path.join(__dirname, "native_card_adapter.js"), "utf8"))}${scripts
    .map(script)
    .join("")}
${script(`const MarkupMgr=new MarkupManager();const templates=${JSON.stringify(templates)};
let pending=null,running=false,lastPostedH=0,lastPostedW=0,fitTimer=0,fitGen=0,sizeObserver=null;
function measure(){
  // Leave room for border-image overhang (≈3rem each side) so the right edge is not clipped.
  const pad = 64;
  const usable = Math.max(280, innerWidth - pad);
  document.documentElement.style.fontSize=Math.max(8, usable/54.6)+'px';
  const card=document.querySelector('.item_card');
  if(!card)return null;
  const rect=card.getBoundingClientRect();
  const host=document.getElementById('card-host');
  // Prefer scrollHeight so firmware / red-text below a former fixed slideout still count.
  const height=Math.ceil(Math.max(
    rect.height,
    rect.bottom,
    card.scrollHeight || 0,
    host?.scrollHeight || 0
  )+12);
  const width=Math.ceil(Math.max(rect.width, document.documentElement.scrollWidth || 0));
  return {height,width};
}
function postSize(force){
  const m=measure();
  if(!m||m.height<=0)return;
  if(!force&&Math.abs(m.height-lastPostedH)<3&&Math.abs(m.width-lastPostedW)<3)return;
  lastPostedH=m.height;lastPostedW=m.width;
  parent.postMessage({type:'sqbt-card-size',height:m.height,width:m.width},'*');
}
function fit(force){
  if(fitTimer)clearTimeout(fitTimer);
  fitTimer=setTimeout(()=>{fitTimer=0;postSize(!!force);},60);
}
function waitImages(root,ms){
  const imgs=[...((root||document).querySelectorAll('img'))].filter(i=>!i.complete);
  if(!imgs.length)return Promise.resolve();
  return Promise.race([
    Promise.all(imgs.map(img=>new Promise(r=>{const done=()=>r();img.addEventListener('load',done,{once:true});img.addEventListener('error',done,{once:true});}))),
    new Promise(r=>setTimeout(r,ms||400))
  ]);
}
async function settleFit(gen){
  await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  if(gen!==fitGen)return;
  await waitImages(document.getElementById('card-host')||document,450);
  if(gen!==fitGen)return;
  postSize(true);
}
if(typeof ResizeObserver==='function'){
  sizeObserver=new ResizeObserver(()=>fit(false));
  sizeObserver.observe(document.getElementById('card-host'));
}
addEventListener('resize',()=>fit(false));
addEventListener('message',async event=>{if(event.source!==parent||event.data?.type!=='sqbt-card-model')return;pending=event.data.model;if(running)return;running=true;try{while(pending){const model=pending;pending=null;const gen=++fitGen;lastPostedH=0;lastPostedW=0;const result=await renderNativeCard(model,templates);parent.postMessage({type:'sqbt-card-rendered',...result},'*');await settleFit(gen);}}catch(error){parent.postMessage({type:'sqbt-card-error',message:error.message},'*');}finally{running=false;}});
parent.postMessage({type:'sqbt-card-ready'},'*');`)}
</body></html>`;
}
function installNativeCardProtocol(
  protocol,
  root = path.join(__dirname, "native_card_ui"),
  // Real icon files live under renderer/editor/img (assets/img is a dev-only junction
  // that electron-builder does not pack into asar).
  assetRoot = path.join(__dirname, "renderer", "editor")
) {
  let document;
  let documentKey = "";
  const handleNativeCardRequest = (request) => {
    const url = new URL(request.url);
    if (url.hostname !== "inventory" || url.pathname !== "/card.html")
      return new Response("Missing", { status: 404 });
    const key = url.search || "";
    if (!document || documentKey !== key) {
      document = createNativeCardDocument(root);
      documentKey = key;
    }
    return new Response(document, { headers: { "Content-Type": "text/html; charset=utf-8" } });
  };
  protocol.handle("sqbt-card", handleNativeCardRequest);
  for (const scheme of ["coui", "common"])
    protocol.handle(scheme, (request) => {
      const url = new URL(request.url);
      if (url.hostname !== "uiresources") return new Response("Missing", { status: 404 });
      const rel = url.hostname + decodeURIComponent(url.pathname);
      const rootResolved = path.resolve(root);
      const candidates = [];
      if (scheme === "common") {
        candidates.push(path.resolve(root, "DLC/Common", rel));
      } else {
        candidates.push(path.resolve(root, rel));
        // DLC skill glyphs (Harmonica/Corpohacker, etc.) ship under DLC/<pack>/uiresources/...
        const dlcRoot = path.join(root, "DLC");
        if (fs.existsSync(dlcRoot)) {
          try {
            for (const pack of fs.readdirSync(dlcRoot, { withFileTypes: true })) {
              if (!pack.isDirectory()) continue;
              candidates.push(path.resolve(dlcRoot, pack.name, rel));
            }
          } catch {
            /* ignore */
          }
        }
      }
      let file = null;
      for (const cand of candidates) {
        if (
          cand.toLowerCase().startsWith((rootResolved + path.sep).toLowerCase()) &&
          fs.existsSync(cand) &&
          fs.statSync(cand).isFile()
        ) {
          file = cand;
          break;
        }
      }
      if (!file) return new Response("Missing", { status: 404 });
      const mime = {
        ".png": "image/png",
        ".ttf": "font/ttf",
        ".svg": "image/svg+xml",
        ".css": "text/css",
      }[path.extname(file).toLowerCase()];
      if (!mime) return new Response("Unsupported resource", { status: 403 });
      return new Response(fs.readFileSync(file), {
        headers: { "Content-Type": mime, "Access-Control-Allow-Origin": "*" },
      });
    });
  protocol.handle("sqbt-asset", (request) => {
    // Use resolveSqbtAssetPath so classmod-passive ↔ classmod-perks fallback works
    // (many Rafa/skill glyphs live only under classmod-perks).
    const file = resolveSqbtAssetPath(request.url, assetRoot);
    if (!file) return new Response("Missing", { status: 404 });
    const mime = {
      ".png": "image/png",
      ".jpg": "image/jpeg",
      ".jpeg": "image/jpeg",
      ".webp": "image/webp",
      ".svg": "image/svg+xml",
    }[path.extname(file).toLowerCase()];
    if (!mime) return new Response("Unsupported resource", { status: 403 });
    return new Response(fs.readFileSync(file), {
      headers: { "Content-Type": mime, "Access-Control-Allow-Origin": "*" },
    });
  });
}
module.exports = {
  registerNativeCardSchemes,
  installNativeCardProtocol,
  createNativeCardDocument,
  inlineSqbtAssetUrls,
  prepareClassmodCardModel,
  sqbtAssetToDataUrl,
  resolveSqbtAssetPath,
};
