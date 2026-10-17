const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const app=process.argv[2] || path.join(__dirname,'..');
const source=fs.readFileSync(path.join(app,'renderer/app.js'),'utf8');
function fn(name) {const a=source.indexOf(`function ${name}(`);assert(a>=0);return source.slice(a,source.indexOf('\n}\n',a)+3);}
let paints=0,polls=0;
const context={lastGiveEverythingStatus:null,lastProgressHtml:'',progressPollTimer:null,
  renderProgressPanel:()=>paints++,startProgressPoll:()=>polls++};
vm.createContext(context);
vm.runInContext(fn('beginGiveEverythingProgress')+'\n'+fn('applyBridgeChallengeSnapshot'),context);
context.beginGiveEverythingProgress();
assert.equal(paints,1);assert.equal(polls,1);
assert.equal(context.lastGiveEverythingStatus.progress_percent,0);
context.applyBridgeChallengeSnapshot({give_everything:{active:false,running:false}});
assert(context.lastGiveEverythingStatus,'initial idle poll must not erase the pending action');
context.applyBridgeChallengeSnapshot({give_everything:{active:true,running:true,progress_percent:18,workflow_phase:'missions'}});
assert.equal(context.lastGiveEverythingStatus.progress_percent,18);
console.log('PASS: Give everything progress appears immediately and survives an initial idle poll.');
