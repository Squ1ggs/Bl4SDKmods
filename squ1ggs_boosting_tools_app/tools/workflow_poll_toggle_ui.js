const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const app=process.argv[2] || path.join(__dirname,'..');
const source=fs.readFileSync(path.join(app,'renderer/app.js'),'utf8').replace(/\r\n/g,'\n');
function fn(name,async=false){const i=source.indexOf(`${async?'async ':''}function ${name}(`);assert(i>=0,name);return source.slice(i,source.indexOf('\n}\n',i)+3);}
async function main(){
  const scope={preferredDeliveryPlayerIndex:()=>-1,latestStatus:{raw:{players:[]}},WORLD_SPAWN_ACTIONS:new Set()};
  vm.createContext(scope);vm.runInContext(fn('enrichPayload'),scope);
  for(const action of ['give_everything','max_all','character_flag','god_mode','infinite_ammo']) {
    assert.equal(scope.enrichPayload(action,{}).player_index,-1,action);
    assert.equal(scope.enrichPayload(action,{player_index:1}).player_index,1,action);
  }
  assert.equal(scope.enrichPayload('low_power',{}).player_index,undefined);
  const requests=[];
  const c={actionsEnabled:()=>true,progressPollInFlight:false,lastChallengeStatus:null,lastUvhmStatus:null,
    lastShapeStatus:null,lastSpawnAllStatus:null,lastSerialDeliveryStatus:null,lastAutoLobbyStatus:null,lastVacuumStatus:null,lastMissionStatus:null,
    lastGiveEverythingStatus:{active:true,running:true,workflow_phase:'missions',progress_percent:24},
    window:{sqbt:{postAction:async(action)=>{requests.push(action);if(action==='challenge_bulk_status')throw Error('busy');
      return action==='give_everything_status'?{data:{give_everything:{active:true,running:true,workflow_phase:'challenges',progress_percent:39}}}:{data:null};}}},
    applyBridgeChallengeSnapshot:data=>{c.lastGiveEverythingStatus=data.give_everything;}};
  for(const name of ['isChallengeBusy','isUvhmBusy','isShapeBusy','isSpawnAllBusy','isSerialDeliveryBusy','isAutoLobbyBusy','isVacuumBusy','isMissionBusy'])c[name]=()=>false;
  c.isGiveEverythingBusy=()=>true;
  let polling=fn('pollProgressOnce',true);
  // Execute its real request/failure/combined-status path; display calculations
  // below it already have dedicated card/progress tests.
  polling=polling.slice(0,polling.indexOf('    const challengeRaw'))+'  } finally { progressPollInFlight=false; }\n}';
  vm.createContext(c);vm.runInContext(polling,c);
  await c.pollProgressOnce();
  assert(requests.includes('give_everything_status'));
  assert.equal(c.lastGiveEverythingStatus.workflow_phase,'challenges');
  assert.equal(c.lastGiveEverythingStatus.progress_percent,39);
  const states=[];
  const board={toggleBoardBusy:false,TOGGLE_BOARD_ACTIONS:{infinite_jump:{action:'mobility_infinite_jump',payloadOn:{enabled:true},payloadOff:{enabled:false}}},
    stickyToggleGraceUntil:{},patchStickyToggleLocal:(key,on)=>states.push(on),syncMobilityToggleButtons(){},fillTogglesBoard(){},
    actionMessage:{},runAction:async()=>({ok:false,message:'apply failed'})};
  vm.createContext(board);
  for(const name of ['beginStickyToggleChange','finishStickyToggleChange'])vm.runInContext(fn(name),board);
  vm.runInContext(fn('toggleBoardRow',true),board);
  await board.toggleBoardRow('infinite_jump','Infinite jump',true);
  assert.deepEqual(states,[true,false]);
  assert.equal(board.toggleBoardBusy,false);
  states.length=0;
  board.runAction=async()=>{throw Error('connection lost');};
  await board.toggleBoardRow('infinite_jump','Infinite jump',true);
  assert.deepEqual(states,[true,false]);
  let painted;
  board.paintToggleButton=(button,def,on)=>painted=on;
  board.writeStickyToggle=()=>{};board.toggleStickyKey=()=>'';
  vm.runInContext(fn('reconcileFailedToggle'),board);
  board.reconcileFailedToggle({}, {syncKey:'infinite_jump',sticky:true}, 'home',false,{ok:false});
  assert.equal(painted,false);
  board.beginStickyToggleChange('infinite_jump',true);
  assert.equal(board.stickyToggleGraceUntil.infinite_jump,Infinity);
  // A request lasting longer than the old 2.5-second grace stays protected.
  assert(Date.now()+10000 < board.stickyToggleGraceUntil.infinite_jump);
  board.finishStickyToggleChange('infinite_jump');
  assert(Number.isFinite(board.stickyToggleGraceUntil.infinite_jump));
  assert.equal((source.match(/beginStickyToggleChange\(actionDef.syncKey, nextOn\)/g)||[]).length,2);
  assert.equal((source.match(/finishStickyToggleChange\(actionDef.syncKey\)/g)||[]).length,2);
  assert(source.includes('.then((result) => reconcileFailedToggle(button, actionDef, sectionId, currentlyOn, result))'));
  console.log('PASS: combined workflow polling survives a child timeout and updates phase/progress; failed board/home toggles revert.');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
