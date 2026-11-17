const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/assets-desktop.js'),'utf8');
function fixture() {
  const opened=[];
  const scope={state:{data:{dashboard:{team:'GSW',extension_window_open:true}}},userTeam:()=> 'GSW',teamLabel:x=>x,
    escapeAttr:x=>String(x).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),
    openExtensionNegotiation:id=>opened.push(id)};
  vm.createContext(scope);
  vm.runInContext(source.slice(source.indexOf('function assetExtensionCell('),source.indexOf('function pickTeamAbbrev(')),scope);
  return {scope,opened};
}
test('contract actions respect team ownership, the extension window, and backend eligibility',()=>{
  const {scope}=fixture(),player={id:'curry',name:'Stephen Curry',extension_eligible:true};
  assert.match(scope.assetExtensionCell(player),/data-asset-extension="curry"/);
  assert.match(scope.assetExtensionCell(player),/aria-label="Negotiate extension with Stephen Curry"/);
  assert.doesNotMatch(scope.assetExtensionCell({...player,extension_eligible:false}),/<button/);
  scope.state.data.dashboard.extension_window_open=false;
  assert.match(scope.assetExtensionCell(player),/Closed/);
  assert.doesNotMatch(scope.assetExtensionCell(player),/<button/);
  scope.state.data.dashboard.extension_window_open=true;
  scope.state.data.dashboard.team='BOS';
  assert.doesNotMatch(scope.assetExtensionCell(player),/<button/);
});
test('extension action safely quotes player labels and IDs',()=>{
  const {scope}=fixture();
  assert.match(scope.assetExtensionCell({id:'a"b',name:'A <B>',extension_eligible:true}),/data-asset-extension="a&quot;b"/);
  assert.doesNotMatch(scope.assetExtensionCell({id:'a',name:'A <B>',extension_eligible:true}),/<B>/);
});
test('rewiring and replacement rows open the selected player once',()=>{
  const {scope,opened}=fixture();
  let button={dataset:{assetExtension:'curry'}};
  const root={querySelectorAll:()=>[button]};
  scope.wireAssetExtensions(root);scope.wireAssetExtensions(root);button.onclick();
  button={dataset:{assetExtension:'another-player'}};
  scope.wireAssetExtensions(root);button.onclick();
  assert.deepEqual(opened,['curry','another-player']);
});

test('extension preview applies the offer only from its backend start season for the selected term',()=>{
  const app=fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
  const scope={};vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function extensionOfferSchedule('),app.indexOf('function updateExtensionPreview(')),scope);
  const candidate={start_season:'2027-28',cap_projection:['2026-27','2027-28','2028-29','2029-30'].map(season=>({season}))};
  assert.deepEqual(Array.from(scope.extensionOfferSchedule(candidate,1,45.2)),[0,45.2,0,0]);
  assert.deepEqual(Array.from(scope.extensionOfferSchedule(candidate,2,50)),[0,50,50,0]);
  assert.deepEqual(Array.from(scope.extensionOfferSchedule(candidate,2,'')),[0,0,0,0]);
});

test('shared salary previews keep scalar offers working and do not carry term-limited offers into padded years',()=>{
  const app=fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
  const scope={escapeHtml:String,shortSeasonLabel:x=>x,money:x=>`$${x}`,signedMoney:x=>`$${x}`,clampNumber:(x,a,b)=>Math.max(a,Math.min(b,x))};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function approvedOfferCapChart('),app.indexOf('function freeAgentOfferSummary(')),scope);
  const rows=[['2027-28',{salary_total_millions:100}],['2028-29',{salary_total_millions:80}]];
  assert.match(scope.approvedOfferCapChart(rows,[40,0]),/>\$140<.*>\$80</s);
  assert.equal((scope.approvedOfferSalaryTable(rows,[40,0]).match(/data-offer-salary>\$40</g)||[]).length,1);
  assert.equal((scope.approvedOfferSalaryTable(rows,40).match(/data-offer-salary>\$40</g)||[]).length,6);
});
