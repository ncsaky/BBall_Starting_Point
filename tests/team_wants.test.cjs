const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync('src/nba_gm_data/gui/team-wants.js','utf8');
const escape=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function fixture(){
  const payload={entries:[],roster:[{id:'old',name:'Incumbent',position:'SG'}],suggestions:[]};
  const s={state:{currentSave:'one',teams:[{id:'a',abbrev:'A'},{id:'b',abbrev:'B'}],wantsRead:{save:'one',team:'A',payload},data:{}},
    userTeam:()=> 'A',teamLabel:x=>typeof x==='string'?x:x?.abbrev||'',escapeHtml:escape,escapeAttr:escape,structuredClone,
    crypto:{randomUUID:()=> 'unique'},Date,console};
  vm.createContext(s);vm.runInContext(source,s);return s;
}
test('empty human wants stay empty and invite explicit add',()=>{
  const s=fixture(), html=s.teamWantsMarkup({team:'A'});
  assert.match(html,/No published wants/);assert.match(html,/data-want-add/);assert.doesNotMatch(html,/data-want-edit/);
});
test('AI list is read-only and user list has accessible priority controls',()=>{
  const s=fixture();s.state.wantsRead.payload.entries=[{id:'w',kind:'player',positions:['SF'],conditions:[]}];
  let html=s.teamWantsMarkup({team:'A'});assert.match(html,/Move want 1 up/);assert.match(html,/Edit want 1/);assert.match(html,/Remove want 1/);
  s.state.wantsTeam='B';s.state.wantsRead.team='B';html=s.teamWantsMarkup({team:'B'});assert.doesNotMatch(html,/data-want-add|data-want-edit|data-want-remove/);
});
test('conditions and stale targets are escaped and show their real meaning',()=>{
  const s=fixture();const text=s.wantDescription({kind:'upgrade',target_name:'<Star>',active:false,conditions:[{field:'range',op:'>=',value:90}]});
  assert.match(text,/inactive/);assert.match(text,/Range >= 90/);
  s.state.wantsRead.payload.entries=[{id:'w',kind:'upgrade',target_name:'<Star>',active:false,conditions:[]}];
  assert.match(s.teamWantsMarkup({team:'A'}),/&lt;Star&gt;/);
});
test('editor supports conditions positions picks and suggestions without publishing',()=>{
  const s=fixture(),payload=s.state.wantsRead.payload;
  s.state.wantEditor={payload,index:null,draft:s.wantPreset('youth',payload)};
  let html=s.wantEditorMarkup();assert.match(html,/data-want-position="SF"/);assert.equal((html.match(/data-want-condition=/g)||[]).length,3);
  assert.match(html,/data-condition-add/);assert.match(html,/type="submit"/);
  s.state.wantEditor.draft=s.wantPreset('picks',payload);html=s.wantEditorMarkup();assert.match(html,/Unprotected only/);assert.match(html,/Next 7/);
  assert.equal(payload.entries.length,0);
});
test('backend match labels deduplicate duplicate wants and distinguish near matches',()=>{
  const s=fixture(),html=s.tradeWantsOfferSummary({wants_matches:[{team_id:'A',asset_id:'p',status:'exact'},{team_id:'A',asset_id:'p',status:'exact'},{team_id:'A',asset_id:'q',status:'near'}]});
  assert.match(html,/1 want match/);assert.match(html,/1 near match/);
});
test('an in-progress simulation cannot trigger acquisition reminders',async()=>{
  const s=fixture();s.state.simulationRunning=true;s.action=()=>{throw Error('must not read during playback');};await s.maybeShowWantReminder();
});
test('a late read cannot populate a different save',async()=>{
  const s=fixture();let finish;s.savePayload=()=>({save_path:s.state.currentSave});s.action=()=>new Promise(resolve=>finish=resolve);
  const request=s.readTeamWants('A');s.state.currentSave='two';finish({entries:[{id:'old'}]});
  assert.equal(await request,null);assert.equal(s.state.wantsRead.save,'one');
});
test('a completed edit for the old save cannot refresh or close the new save',async()=>{
  const s=fixture();let finish;s.savePayload=()=>({save_path:s.state.currentSave});s.action=()=>new Promise(resolve=>finish=resolve);
  const request=s.saveTeamWants([],1);s.state.currentSave='two';finish({entries:[],revision:2});
  await assert.rejects(request,/active save has changed/);assert.equal(s.state.wantsTeam,undefined);
});
