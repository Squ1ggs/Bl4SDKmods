"use strict";
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const vm=require('node:vm');
const {spawnSync}=require('node:child_process');
const app=path.resolve(process.argv[2] || path.join(__dirname,'..'));
const root=path.join(app,'resources/Squ1ggsBoostingTools');
const fixture=spawnSync('python',[path.join(__dirname,'picture_constable_fixture.py'),root],{encoding:'utf8',windowsHide:true});
assert.equal(fixture.status,0,fixture.stderr);
const {serial}=JSON.parse(fixture.stdout);
const {decodeSerialCard}=require(path.join(app,'lib/serial_codec'));
const decoded=decodeSerialCard(serial,root);
assert.equal(decoded.level,51);
assert.equal(decoded.element,'Radiation');
assert(decoded.name_parts.includes('JAK_SG.comp_06_pearl_constable'));
assert(decoded.name_parts.includes('JAK_SG.part_barrel_01_constable'));
const source=fs.readFileSync(path.join(app,'renderer/app.js'),'utf8');
function fn(name) {
  const start=source.indexOf(`async function ${name}(`);
  assert(start>=0,name);
  return source.slice(start,source.indexOf('\n}\n',start)+3);
}
async function main() {
  const {analyzeItem}=require(path.join(app,'lib/item_analysis'));
  const analysis=await analyzeItem(serial);
  assert.equal(analysis.ok,true);
  assert.equal(analysis.card_props.level,51);
  assert.equal(analysis.card_props.element,'Radiation');
  assert(analysis.card_props.part_names.includes('Weapon.pearl_radiation'));
  assert.match(analysis.display_name,/Constable/i);
  const damage=analysis.stats.find(x=>/damage/i.test(x.label));
  assert(Number(String(damage?.value).replace(/,/g,''))>0,JSON.stringify(analysis.stats));
  global.window=global; global.addEventListener=()=>{};
  require(path.join(app,'native_item_card'));
  const entry=global.SQBTNativeItemCard.propsToEntry(analysis.card_props);
  assert.equal(entry.element,'Radiation');
  assert.equal(entry.manufacturer,'jakobs');
  assert.equal(entry.rarity,'Pearlescent');
  const {evaluateNexusCardStats}=require(path.join(app,'lib/nexus_card_stats'));
  let calcInput;
  const context={window:{sqbt:{analyzeItem:async()=>analysis,nexusCardStats:async(p)=>{calcInput=p;return evaluateNexusCardStats(p);}}},
    resolveNexusCardLevel:()=>51,softCapNativeSecondary:x=>x};
  vm.createContext(context);
  vm.runInContext(fn('attachPartScaleStats'),context);
  const card=await context.attachPartScaleStats({serial,level:51,part_names:[],stats:[],element:'',manufacturer:''});
  assert.equal(calcInput.element,'Radiation');
  assert(calcInput.part_names.includes('JAK_SG.comp_06_pearl_constable'));
  assert(calcInput.part_names.includes('Weapon.pearl_radiation'));
  assert.equal(card.element,'Radiation');
  assert.equal(card.manufacturer,'Jakobs');
  let selected='';
  const auto={editorPicturePreview:null,editorLatest:{preview:analysis.card_props},
    editorUseAnalyzedSerial:async(code,opts)=>{assert.equal(opts.pictureCandidate,true);selected=code;},renderEditorImageResult:()=>{}};
  vm.createContext(auto); vm.runInContext(fn('previewTopPictureCandidate'),auto);
  await auto.previewTopPictureCandidate({ok:true,candidates:[{serial}]});
  assert.equal(selected,serial);
  assert.equal(auto.editorPicturePreview.element,'Radiation');
  assert(!source.includes('This picture does not reveal every hidden part or roll. Load this known catalog serial'));
  const {extractVisibleAttributes}=require(path.join(app,'lib/image_item_match'));
  assert.equal(extractVisibleAttributes('Looming Constable\nRadiation Damage\nLEVEL 51\nJAKOBS').element,'Radiation');
  const fire={idRaw:'1:60',manufacturer:'Maliwan',code:'Weapon.pearl_fire',partType:'Element'};
  const radiation={idRaw:'1:57',manufacturer:'Maliwan',code:'Weapon.pearl_radiation',partType:'Element'};
  const state={itemType:'Weapon',weaponType:'Shotgun',manufacturer:'Jakobs',slots:{element:fire},extras:[]};
  let listener;
  const posts=[];
  const parent={postMessage:p=>posts.push(p)};
  const bridgeWindow={parent,__STX_SIMPLE_STATE:state,STX_DATASET:{ALL_PARTS:[fire,radiation]},
    addEventListener:(type,fn)=>{if(type==='message')listener=fn;},refreshTopSelectors(){},refreshBuilder(){},refreshOutputs(){}};
  const bridgeContext={window:bridgeWindow,document:{readyState:'loading',addEventListener(){},getElementById(){return null;},querySelectorAll(){return[];}},
    setTimeout:fn=>{fn();return 1;},clearTimeout(){},setInterval(){},MutationObserver:function(){}};
  vm.runInNewContext(fs.readFileSync(path.join(app,'renderer/editor/js/sqbt_editor_bridge.js'),'utf8'),bridgeContext);
  listener({source:parent,data:{source:'sqbt-shell',type:'sqbt-load-image-recipe',merge:true,
    extracted:{item_type:'Shotgun',manufacturer:'Jakobs',element:'Radiation',level:51}}});
  assert.equal(state.slots.element,undefined);
  assert.equal(state.slots.additionalParts[0].idRaw,'1:57');
  assert.equal(state.level,51);
  assert(posts.findLast(p=>p.type==='sqbt-editor-imported').resolved_part_ids.includes('1:57'));
  console.log('PASS: L51 pearl Constable identity/barrel, bag Radiation, Jakobs, stats, stale-preview enrichment and automatic top selection.');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
