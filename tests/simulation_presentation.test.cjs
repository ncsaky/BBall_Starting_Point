const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const scope = {window:{},TextDecoder,setTimeout};
vm.createContext(scope);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/simulation-presentation.js'),'utf8'),scope);
const {readStream,lotteryRevealState,draftPlaybackFrame} = scope.window.GameSimulation;

function stream(text, split=7) {
  const bytes = new TextEncoder().encode(text);
  return new Response(new ReadableStream({start(controller){
    for(let i=0;i<bytes.length;i+=split) controller.enqueue(bytes.slice(i,i+split));
    controller.close();
  }}));
}
test('incremental UTF-8 frames arrive before the terminal committed result', async()=>{
  const progress = [];
  const result = await readStream(stream('{"type":"progress","event":{"date":"2027-06-10","name":"Montréal"}}\n{"type":"progress","event":{"score":4}}\n{"type":"result","result":{"saved":true}}\n',1),async event=>{progress.push(event);});
  assert.equal(progress.length,2);
  assert.equal(progress[0].name,'Montréal');
  assert.equal(progress[1].score,4);
  assert.equal(result.saved,true);
});
test('errors and disconnected streams never become successful results',async()=>{
  await assert.rejects(()=>readStream(stream('{"type":"error","error":"Save blocked"}\n'),()=>{}),/Save blocked/);
  await assert.rejects(()=>readStream(stream('{"type":"progress","event":{}}\n'),()=>{}),/before confirmation/);
  await assert.rejects(()=>readStream(stream('{bad}\n'),()=>{}));
});
test('lottery reveals only visible envelopes and infers jumps without exact-pick spoilers',()=>{
  const team = id=>({id,abbrev:id});
  const odds = Array.from({length:14},(_,i)=>({seed:i+1,team:team(`t${i+1}`)}));
  // Teams 14, 13, 2 and 1 are drawn. At #14, team 12 appears instead of 14.
  const order = [14,13,2,1,3,4,5,6,7,8,9,10,11,12];
  const lottery = {draw_count:4,odds,reveal:order.map((seed,i)=>({pick:i+1,starting_seed:seed,original_team:team(`t${seed}`)}))};
  const empty = lotteryRevealState(lottery,0);
  assert.equal(empty.revealed.length,0);
  assert.equal(empty.promoted.length,0);
  assert.equal(empty.nextPick,14);
  const first = lotteryRevealState(lottery,1);
  assert.deepEqual(Array.from(first.revealed,r=>r.pick),[14]);
  assert.deepEqual(Array.from(first.promoted).sort(),['t13','t14']);
  assert.equal(first.nextPick,13);
  assert.equal(first.complete,false);
  const done = lotteryRevealState(lottery,14);
  assert.deepEqual(Array.from(done.revealed,r=>r.pick),Array.from({length:14},(_,i)=>14-i));
  assert.equal(done.complete,true);
  assert.equal(done.nextPick,null);
  assert.deepEqual(Array.from(done.promoted).sort(),['t1','t13','t14','t2']);
  assert.equal(lotteryRevealState({...lottery,draw_count:0},1).promoted.length,0);
});
test('the 3-2-1 lottery draws every pick: 16 envelopes, nobody "jumps into the top four"',()=>{
  const team = id=>({id,abbrev:id});
  const odds = Array.from({length:16},(_,i)=>({seed:i+1,team:team(`t${i+1}`)}));
  const order = [9,3,16,1,2,4,5,6,7,8,10,11,12,13,14,15];
  const lottery = {format:'3-2-1',draw_count:16,odds,reveal:order.map((seed,i)=>({pick:i+1,starting_seed:seed,original_team:team(`t${seed}`)}))};
  const first = lotteryRevealState(lottery,1);
  assert.equal(first.total,16);
  assert.equal(first.nextPick,15);
  assert.deepEqual(Array.from(first.revealed,r=>r.pick),[16]);
  assert.equal(first.promoted.length,0);
  assert.equal(lotteryRevealState(lottery,16).promoted.length,0);
  assert.equal(lotteryRevealState(lottery,16).complete,true);
});

test('draft playback reveals selections and prospect availability in chronological frames',()=>{
  const row=(pick,team,prospect,status='selected')=>({selection:{overall_pick:pick,team_id:team,prospect_id:prospect},team:{id:team,abbrev:team},prospect:{id:prospect,name:`Prospect ${pick}`},draft_status:status});
  const room={team:{id:'user'},state:{current_index:3,total_picks:3,status:'completed'},draft_timeline:[row(1,'other','p1'),row(2,'user','p2'),row(3,'other','p3')],draft_board:{entries:['p1','p2','p3'].map((id,index)=>({prospect:{id,name:id},draft_status:'drafted',selected_pick:index+1}))}};
  const events=[{type:'trade',headline:'Trade completed.'},{type:'pick',overall_pick:2,team:{id:'user'},prospect:{id:'p2'}},{type:'pick',overall_pick:3,team:{id:'other'},prospect:{id:'p3'}}];
  const before=draftPlaybackFrame(room,events,0);
  assert.equal(before.state.current_index,1);
  assert.deepEqual(Array.from(before.draft_timeline,row=>row.draft_status),['selected','current','upcoming']);
  assert.equal(before.current_selection.selection.overall_pick,2);
  assert.deepEqual(Array.from(before.draft_board.entries,row=>row.draft_status),['drafted','available','available']);
  const first=draftPlaybackFrame(room,events,1);
  assert.deepEqual(Array.from(first.draft_timeline,row=>row.draft_status),['selected','selected','current']);
  assert.equal(first.draft_board.entries[1].selected_pick,2);
  assert.equal(first.draft_board.entries[2].draft_status,'available');
  const complete=draftPlaybackFrame(room,events,2);
  assert.equal(complete.state.status,'completed');
  assert.deepEqual(Array.from(complete.draft_timeline,row=>row.draft_status),['selected','selected','selected']);
  assert.deepEqual(Array.from(complete.draft_board.entries,row=>row.draft_status),['drafted','drafted','drafted']);
  assert.deepEqual(Array.from(room.draft_timeline,row=>row.draft_status),['selected','selected','selected']);
});

test('skipping a reveal invalidates its pending timer before entering draft night',async()=>{
  const app = fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
  let wake;
  let renders = 0;
  const scope = {
    state:{currentSave:'fixture',data:{draft:{year:2027,lottery:{reveal:Array.from({length:14},()=>({}))}}}},
    localStorage:{getItem:()=>null,setItem(){}},
    GameSimulation:{wait:()=>new Promise(resolve=>{wake=resolve;})},
    renderDashboard(){renders+=1;},
    document:{querySelector(){throw Error('An obsolete reveal timer touched the draft page');}},
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function lotteryRevealKey('),app.indexOf('function draftProspectBoard(')),scope);
  const pending = scope.runLotteryReveal();
  scope.finishLotteryReveal();
  assert.equal(scope.state.lotteryRevealCount,14);
  assert.equal(scope.state.lotteryRevealRunning,false);
  assert.equal(renders,2);
  scope.state.draftPresentationStage='live';
  wake();
  await pending;
  assert.equal(renders,2);
  assert.equal(scope.state.lotteryRevealCount,14);
});
