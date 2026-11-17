const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/feedback.js'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');

function harness() {
  const handlers = {};
  const video = {classList:{contains:()=>true}, paused:false, readyState:4, currentTime:12.5, error:null};
  const scope = {navigator:{userAgent:'Mozilla/5.0 Chrome/130.0.0 Secret-UA'}, document:{querySelector:()=>video, querySelectorAll:()=>[]}};
  scope.window = {innerWidth:1280, innerHeight:800, devicePixelRatio:2, matchMedia:()=>({matches:false}), addEventListener:(key,handler)=>{handlers[key]=handler;}};
  vm.createContext(scope);
  vm.runInContext(source, scope);
  return {feedback:scope.window.GameFeedback, handlers};
}

test('reports copy only allowlisted fields and never raw state or runtime secrets', () => {
  const {feedback} = harness();
  const report = feedback.snapshot({currentSave:'/Users/secret/friend-save.json', view:'home', home:{save:{name:'Private Name', phase:'regular_season', current_date:'2026-10-25', season:'2026-27', token:'secret-token'}}, multiplayer:{session:{session_token:'manager-secret'}}}, {version:'beta.8', root:'/Users/secret', save_dir:'/private/saves', token:'runtime-secret', packaged:true}, {summary:'Minutes slider'});
  const json = JSON.stringify(report);
  for (const secret of ['friend-save', 'Private Name', '/Users/', '/private/', 'secret-token', 'manager-secret', 'runtime-secret', 'Secret-UA']) assert.ok(!json.includes(secret), secret);
  assert.equal(report.context.date, '2026-10-25');
  assert.equal(report.context.screen, 'game');
  assert.equal(report.startup_video.time, 12.5);
  assert.equal(report.browser.major, '130');
  assert.equal(report.notes.summary, 'Minutes slider');
});

test('action history is bounded, excludes payloads/errors, and snapshots are detached', () => {
  const {feedback} = harness();
  for(let i=0;i<100;i++) feedback.recordAction('set_rotation_minutes', i, i%2);
  const before = feedback.snapshot({});
  assert.equal(before.recent_actions.length, 40);
  assert.equal(before.recent_actions[0].duration_ms, 60);
  assert.deepEqual(Object.keys(before.recent_actions[0]).sort(), ['action','duration_ms','succeeded']);
  feedback.recordAction('/Users/secret', 10, false);
  assert.equal(feedback.snapshot({}).recent_actions.at(-1).action, 'unknown');
  assert.equal(before.recent_actions.at(-1).duration_ms, 99);
});

test('error collection excludes messages, stacks, paths and rejection reasons', () => {
  const {feedback, handlers} = harness();
  for(let i=0;i<100;i++) handlers.error({message:'/Users/secret runtime-token', filename:'/Users/secret'});
  handlers.unhandledrejection({reason:'manager-token'});
  const report = feedback.snapshot({});
  assert.equal(report.browser_errors.length, 40);
  assert.equal(report.browser_errors.at(-1).type, 'unhandled_rejection');
  assert.ok(!JSON.stringify(report).includes('secret'));
  assert.ok(!JSON.stringify(report).includes('manager-token'));
});

test('offline report and malformed context remain bounded with notes included as written', () => {
  const {feedback} = harness();
  const report = feedback.snapshot({view:'/secret/path', home:{save:{current_date:'/secret', season:'name', phase:'/secret'}}}, null, {summary:'x'.repeat(4000), actual:'User-written personal note'});
  assert.equal(report.runtime_available, false);
  assert.equal(report.context.date, null);
  assert.equal(report.context.phase, 'unknown');
  assert.equal(report.notes.summary.length, 3000);
  assert.equal(report.notes.actual, 'User-written personal note');
});

test('report metadata request carries no save or user notes and download is local JSON', async () => {
  const scope = {state:{tutorial:false,busy:false,modal:null}, apiHeaders(){}, GameFeedback:{runtime:async()=>({version:'beta.8'}), snapshot:()=>({schema:'nba_gm_issue_v1',created_at:'2026-10-04T01:02:03.000Z'})}, renderModal(){}, escapeHtml:String, els:{modalRoot:{querySelector:()=>({focus(){}})}}};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('async function openIssueReport()'), app.indexOf('async function openExtensionNegotiation(')),scope);
  await scope.openIssueReport();
  assert.equal(scope.state.modal.kind,'issueReport');
  assert.match(scope.state.modal.body,/Nothing is uploaded/);
  const downloads=[];
  Object.assign(scope,{Blob,URL:{createObjectURL:blob=>{scope.blob=blob;return 'blob:issue';},revokeObjectURL(){}},document:{body:{append(){}},createElement:()=>({click(){downloads.push(this.download);},remove(){}})},setTimeout:fn=>fn()});
  scope.downloadIssueReport({preventDefault(){},currentTarget:{elements:{namedItem:key=>({value:key})},querySelector:()=>({textContent:''})}});
  assert.equal(downloads.length,1);
  assert.match(downloads[0],/^nba-gm-issue-.*\.json$/);
  const report=JSON.parse(await scope.blob.text());
  assert.equal(report.notes.steps,'steps');
});

test('late metadata response cannot reopen a closed dialog', async () => {
  let resolve;
  const origin={kind:'dashboardSettings'};
  const scope={state:{modal:origin},apiHeaders(){},renderModal(){},escapeHtml:String,els:{modalRoot:{querySelector:()=>({focus(){}})}},GameFeedback:{runtime:()=>new Promise(r=>{resolve=r;}),snapshot:()=>({})}};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('async function openIssueReport()'),app.indexOf('function downloadIssueReport(')),scope);
  const pending=scope.openIssueReport();
  scope.state.modal=null;
  resolve({});
  await pending;
  assert.equal(scope.state.modal,null);
});

test('runtime request uses empty authenticated payload and can time out during session acquisition', async () => {
  const scope={window:{addEventListener(){}},AbortController,setTimeout,clearTimeout,fetch:async(url,options)=>{
    assert.equal(url,'/api/action');
    assert.deepEqual(JSON.parse(options.body),{action:'diagnostic_runtime',payload:{}});
    assert.equal(options.headers.token,'auth');
    return {ok:true,json:async()=>({result:{version:'beta.8'}})};
  }};
  vm.createContext(scope);
  vm.runInContext(source,scope);
  assert.equal((await scope.window.GameFeedback.runtime(async()=>({token:'auth'}))).version,'beta.8');
  scope.setTimeout=callback=>setTimeout(callback,1);
  assert.equal(await scope.window.GameFeedback.runtime(()=>new Promise(()=>{})),null);
});
