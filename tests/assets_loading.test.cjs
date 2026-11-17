const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const source = fs.readFileSync(path.join(gui, 'assets-desktop.js'), 'utf8');
function fixture() {
  const pending = [], calls = [];
  let renders = 0, focuses = 0;
  const state = {currentSave:'fixture',dashboardRevision:1,multiplayer:{},home:{save:{current_date:'2026-10-28'}},
    data:{dashboard:{}},view:'dashboard'};
  const frame = {hidden:false,querySelector:()=>({focus:()=>focuses++})};
  const target = {isConnected:true,querySelector:()=>frame};
  const context = {state,userTeam:()=> 'GSW',teamLabel:x=>x,savePayload:()=>({save_path:state.currentSave}),
    document:{activeElement:{closest:()=>({dataset:{boardWindow:'roster'}})}},
    renderDashboard:()=>{throw new Error('Loading assets must not rebuild the dashboard');},
    refreshAssetsSurface:refreshed=>{assert.equal(refreshed,target);renders++;},
    action:(...args)=>{calls.push(args);return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
  vm.createContext(context);
  vm.runInContext(source.slice(0,source.indexOf('async function openTeamRosterCard')),context);
  return {context,state,target,frame,calls,pending,renders:()=>renders,focuses:()=>focuses};
}
const settle = () => new Promise(resolve=>setImmediate(resolve));

test('ordinary cards and gallery previews do not fetch valuations; first opened asset card does', async () => {
  const f = fixture();
  for(const id of ['minutes','standings','week','staff','identity']) f.context.loadOpenedAssetsCard(f.target,id);
  assert.equal(f.calls.length,0);
  f.context.loadOpenedAssetsCard(f.target,'roster');
  f.context.loadOpenedAssetsCard(f.target,'picks');
  assert.equal(f.calls.length,1);
  f.pending[0].resolve({team:'GSW',players:[]});
  await settle();
  assert.equal(f.renders(),1);
  assert.equal(f.focuses(),1);
  assert.equal(f.state.data.tradeUser.team,'GSW');
  f.context.loadOpenedAssetsCard(f.target,'team-block');
  assert.equal(f.calls.length,1);
});

test('tutorial, hydration and absent saves never start asset reads', () => {
  const f = fixture();
  for(const flag of ['tutorial','hydrating']) {
    f.state[flag]=true;
    f.context.loadOpenedAssetsCard(f.target,'roster');
    f.state[flag]=false;
  }
  f.state.currentSave=null;
  f.context.loadOpenedAssetsCard(f.target,'roster');
  assert.equal(f.calls.length,0);
});

test('stale success and failure cannot overwrite a newer dashboard or refresh it', async () => {
  for(const fail of [false,true]) {
    const f = fixture();
    f.context.loadOpenedAssetsCard(f.target,'picks');
    f.state.data.dashboard={newer:true};
    if(fail) f.pending[0].reject(new Error('stale failure'));
    else f.pending[0].resolve({team:'GSW'});
    await settle();
    assert.equal(f.state.data.assetsDesktop,undefined);
    assert.equal(f.state.assetsError,'');
    assert.equal(f.state.assetsLoading,false);
    assert.equal(f.renders(),0);
    f.context.loadOpenedAssetsCard(f.target,'picks');
    assert.equal(f.calls.length,2);
    f.pending[1].resolve({team:'GSW'});
    await settle();
  }
});

test('a failure stops automatic retry loops; explicit retry clears the error and recovers', async () => {
  const f = fixture();
  f.context.loadOpenedAssetsCard(f.target,'league-block');
  f.pending[0].reject(new Error('offline'));
  await settle();
  assert.equal(f.state.assetsError,'offline');
  assert.equal(f.renders(),1);
  f.context.loadOpenedAssetsCard(f.target,'league-block');
  assert.equal(f.calls.length,1);
  const retry=f.context.loadAssetsDesktop();
  assert.equal(f.state.assetsError,'');
  f.pending[1].resolve({team:'GSW'});
  await retry;
  assert.equal(f.state.assetsLoading,false);
  assert.equal(f.state.data.assetsDesktop.payload.team,'GSW');
});

test('a newer dashboard starts its own read while an old request is still in flight', async () => {
  const f=fixture();
  f.context.loadOpenedAssetsCard(f.target,'roster');
  f.state.data.dashboard={newer:true};
  f.context.loadOpenedAssetsCard(f.target,'roster');
  assert.equal(f.calls.length,2);
  f.pending[0].resolve({team:'GSW',old:true});
  await settle();
  assert.equal(f.state.assetsLoading,true);
  assert.equal(f.renders(),0);
  f.pending[1].resolve({team:'GSW',newer:true});
  await settle();
  assert.equal(f.state.assetsLoading,false);
  assert.equal(f.state.data.assetsDesktop.payload.newer,true);
  assert.equal(f.renders(),1);
});

test('failure on an old dashboard does not prevent loading a new dashboard', async () => {
  const f=fixture();
  f.context.loadOpenedAssetsCard(f.target,'roster');
  f.pending[0].reject(new Error('old failure'));
  await settle();
  assert.equal(f.context.assetsErrorForContext(),'old failure');
  f.state.dashboardRevision++;
  assert.equal(f.context.assetsErrorForContext(),'');
  f.context.loadOpenedAssetsCard(f.target,'roster');
  assert.equal(f.calls.length,2);
  f.pending[1].resolve({team:'GSW'});
  await settle();
});

test('refresh does not steal focus from a modal or a closed window', async () => {
  for(const modal of [true,false]) {
    const f = fixture();
    f.context.loadOpenedAssetsCard(f.target,'contracts');
    if(modal) f.state.modal={kind:'player'};
    else f.frame.hidden=true;
    f.pending[0].resolve({team:'GSW'});
    await settle();
    assert.equal(f.renders(),1);
    assert.equal(f.focuses(),0);
  }
});

test('window add, saved visibility, unminimize and switcher restore all notify the loader', () => {
  const board=fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(board,/if \(!layout\[id\]\.minimized\) options\.onOpen\?\.\(id/);
  assert.match(board,/layout\[id\]\.visible && !layout\[id\]\.minimized && !locked\(id\)\) options\.onOpen/);
  assert.ok((board.match(/options\.onOpen\?\.\(id/g)||[]).length>=4);
  const mount=source.slice(source.indexOf('function mountDashboardCardBoard'));
  assert.match(mount,/onOpen:id=>loadOpenedAssetsCard\(target,id\)/);
  assert.doesNotMatch(mount,/loadAssetsDesktop\(\)/);
  assert.match(source,/role="alert"[\s\S]*?data-assets-retry/);
});
