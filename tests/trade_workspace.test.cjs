const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const workspaceCode = source.slice(source.indexOf('function tradeRoomModalBody('), source.indexOf('function renderOffers('));
const selectionCode = source.slice(source.indexOf('function selectedTradeValue('), source.indexOf('function tradeReadout('));
const ledgerCode = source.slice(source.indexOf('function tradeKnownNumber('), source.indexOf('function incomingOfferAsset('));

function player(id, team) {
  return {kind:'player',id,value:id,name:id,label:id,team_abbrev:team,headshot_url:`/${id}.png`,age:22,position:'PF',height:`6'10"`,ratings:{overall:74},trade_value:38,upside_remaining:3.1,health_risk:2.2,contract:'$12.0M × 3',salary_by_year:{'2026-27':12}};
}
function fixture() {
  const calls = [], messages = [];
  const assets = {BKN:{assets:[player('own','BKN')],players:[player('own','BKN')]},CHI:{assets:[player('target','CHI')],players:[player('target','CHI')]},ATL:{assets:[player('other','ATL')],players:[player('other','ATL')]}};
  const resultsElement = {scrollTop:126};
  const context = {
    state:{currentSave:'save',tradeTab:'builder',tradePartner:'ATL',teams:[{abbrev:'BKN',name:'Nets'},{abbrev:'CHI',name:'Bulls'},{abbrev:'ATL',name:'Hawks'}],selectedFrom:[],selectedTo:[],tradeResults:[],tradeSearchCompleted:false,data:{tradeUser:assets.BKN,tradePartner:assets.ATL},tradeAssetFilters:{from:'all',to:'all'}},
    els:{modalRoot:{querySelector:selector=>selector==='#tradeResults'?resultsElement:null}},
    userTeam:()=> 'BKN', teamLabel:value=>value, teamLogoSrc:team=>`/${team}.svg`, teamBrandStyle:()=>'',
    clipboardLegalActions:()=>new Set(['trades']),savePayload:()=>({save_path:'save'}),
    syncDefaultPartner:()=>{},escapeAttr:value=>String(value??''),escapeHtml:value=>String(value??''),
    money:value=>`$${Number(value||0).toFixed(1)}M`,signedMoney:value=>String(value),draftMetric:value=>value==null?'—':Number(value).toFixed(1),shortSeasonLabel:value=>value,
    clampNumber:(value,min,max)=>Math.max(min,Math.min(max,value)),playerUpsideColor:()=> '#5a8',rowLabel:value=>value,
    playerHeadshotMarkup:asset=>`<span class="player-headshot-frame"><img src="${asset.headshot_url}" /></span>`,
    playerNameWithInjuryMarkup:(asset,name)=>String(name),
    playerEvidenceRing:(label,value)=>`<span class="ring">${label} ${value}</span>`,draftAssetGlyph:()=>'<span class="pick-glyph"></span>',
    showToast:value=>messages.push(value),renderModal:()=>{},tradeHeadline:()=> 'evaluated',
    incomingOfferAsset:asset=>`<article class="offer-player">${asset.headshot_url} ${asset.contract} ${asset.upside_remaining}</article>`,
    playerSummaryRatings:()=>'<span>OVR OFF DEF</span>',tradeAssetContract:asset=>asset.contract || '—',
    action:async(name,payload)=>{calls.push({name,payload});return name==='team_assets'?assets[payload.team]:{candidates:[]};},
  };
  vm.createContext(context);
  vm.runInContext(workspaceCode + '\n' + selectionCode + '\n' + ledgerCode,context);
  return {context,calls,messages,assets,resultsElement};
}

test('a late evaluation cannot approve edited pick terms on the same selected assets',async()=>{
  const f=fixture(),c=f.context;
  c.TradePickTerms={request:rules=>rules,errors:()=>[]};
  c.state.selectedFrom=[f.assets.BKN.assets[0]];
  c.state.tradePickRules=[{pick_id:'p',type:'protected_pick',through:4}];
  let finish;
  c.action=()=>new Promise(resolve=>{finish=resolve;});
  const pending=c.evaluateBuiltTrade();
  c.state.tradePickRules[0].through=10;
  finish({proposal:{id:'outdated'},evaluations:[]});await pending;
  assert.equal(c.state.tradeCandidate,undefined);
});

test('finder results cannot replace the workspace after its pick terms change',async()=>{
  const f=fixture(),c=f.context;
  c.TradePickTerms={request:rules=>rules,errors:()=>[]};
  c.state.tradeTab='finder';c.state.selectedFrom=[f.assets.BKN.assets[0]];
  c.state.tradePickRules=[{pick_id:'p',type:'pick_swap',benefit:'better'}];
  let finish;c.action=()=>new Promise(resolve=>{finish=resolve;});
  const pending=c.runTradeSearch();c.state.tradePickRules[0].benefit='worse';
  finish({candidates:[{proposal:{id:'outdated'}}]});await pending;
  assert.equal(c.state.tradeResults.length,0);
});

test('inspecting a newly granted swap restores its editable primary pick and rule',async()=>{
  const f=fixture(),c=f.context;
  const p={kind:'pick',id:'p',value:'p',label:'2029 R1 BKN',season:'2029',round:1};
  f.assets.BKN.assets.push(p);
  c.state.tradeTab='finder';c.state.tradeResults=[{
    proposal:{from_team_id:'BKN',to_team_id:'CHI',from_assets:[{kind:'pick_swap',id:'right'}],to_assets:[]},
    pick_obligation_terms:[{id:'right',type:'pick_swap',primary_pick_id:'p',pending_asset_grant:true}],
    ui_pick_rules:[{pick_id:'p',type:'pick_swap',other_pick_id:'other',benefit:'better'}],
  }];
  await c.inspectFinderTrade(0);
  assert.equal(c.state.selectedFrom[0].id,'p');assert.equal(c.state.selectedFrom[0].kind,'pick');
  assert.equal(c.state.tradePickRules[0].type,'pick_swap');
  assert.equal(c.state.tradePickRules[0].other_pick_id,'other');
});

test('opening a league target loads its actual team roster and selects the target',async()=>{
  const f=fixture();
  await f.context.openTradeRoomModal('finder',{targetTeam:'CHI',targetPlayerId:'target'});
  assert.equal(f.context.state.tradePartner,'CHI');
  assert.equal(f.context.state.tradeFinderTargetTeam,'CHI');
  assert.equal(f.context.state.selectedTo[0].id,'target');
  assert.deepEqual(f.calls.map(call=>call.payload.team),['BKN','CHI']);
  assert.match(f.context.state.modal.body,/Target team/);
});

test('inspecting a candidate and returning restores finder team, targets, results and scroll',async()=>{
  const f=fixture(), s=f.context.state;
  s.tradeTab='finder';s.tradePartner='CHI';s.tradeFinderTargetTeam='CHI';s.selectedTo=[f.assets.CHI.assets[0]];s.data.tradePartner=f.assets.CHI;
  s.tradeResults=[{proposal:{from_team:'BKN',to_team:'ATL',from_assets:[{kind:'player',id:'own'}],to_assets:[{kind:'player',id:'other'}]}}];s.tradeSearchCompleted=true;
  s.modal={kind:'tradeRoom'};
  await f.context.inspectFinderTrade(0);
  assert.equal(s.tradeTab,'builder');assert.equal(s.tradePartner,'ATL');assert.equal(s.selectedTo[0].id,'other');
  await f.context.switchTradeWorkspace('finder');
  assert.equal(s.tradeTab,'finder');assert.equal(s.tradePartner,'CHI');assert.equal(s.tradeFinderTargetTeam,'CHI');
  assert.equal(s.selectedTo[0].id,'target');assert.equal(s.tradeResults.length,1);assert.equal(s.tradeSearchCompleted,true);
  assert.equal(f.resultsElement.scrollTop,126);
});

test('finder team arrows cycle all-team scope without losing assets and acquisition changes load team assets',async()=>{
  const f=fixture(),s=f.context.state;
  s.tradeTab='finder';s.selectedFrom=[f.assets.BKN.assets[0]];
  await f.context.stepTradeWorkspaceTeam(1);
  assert.equal(s.tradeFinderScope,'CHI');assert.equal(s.selectedFrom[0].id,'own');assert.equal(f.calls.length,0);
  await f.context.stepTradeWorkspaceTeam(-1);assert.equal(s.tradeFinderScope,'');
  s.tradeFinderTargetTeam='CHI';s.tradePartner='CHI';s.selectedTo=[f.assets.CHI.assets[0]];
  await f.context.stepTradeWorkspaceTeam(1);
  assert.equal(s.tradeFinderTargetTeam,'ATL');assert.equal(s.selectedTo.length,0);assert.equal(s.data.tradePartner.assets[0].id,'other');
});

test('switching modes on the same loaded partner is immediate and does not fetch duplicate rosters',async()=>{
  const f=fixture(),s=f.context.state;
  s.modal={kind:'tradeRoom'};s.selectedFrom=[f.assets.BKN.assets[0]];
  await f.context.switchTradeWorkspace('finder');
  assert.equal(s.tradeTab,'finder');assert.equal(f.calls.length,0);
  assert.equal(s.selectedFrom[0].id,'own');
  await f.context.switchTradeWorkspace('builder');
  assert.equal(s.tradeTab,'builder');assert.equal(f.calls.length,0);
  assert.equal(s.selectedFrom[0].id,'own');
});

test('a crowded builder package is preserved when the finder seeds its two-asset search',async()=>{
  const f=fixture(),s=f.context.state;
  s.modal={kind:'tradeRoom'};s.selectedFrom=[player('one','BKN'),player('two','BKN'),player('three','BKN')];
  await f.context.switchTradeWorkspace('finder');assert.equal(s.selectedFrom.length,2);
  await f.context.switchTradeWorkspace('builder');assert.equal(s.selectedFrom.length,3);
  assert.match(f.messages[0],/full builder package is saved/);
});

test('shopping sends the selected buyer scope; acquiring sends the seller without buyer scope',async()=>{
  const f=fixture(),s=f.context.state;
  s.tradeTab='finder';s.selectedFrom=[f.assets.BKN.assets[0]];s.tradeFinderScope='CHI';
  await f.context.runTradeSearch();
  assert.equal(f.calls[0].payload.buyer_team,'CHI');assert.equal(f.calls[0].payload.seller_team,'BKN');
  s.tradeFinderTargetTeam='ATL';s.selectedTo=[f.assets.ATL.assets[0]];
  await f.context.runTradeSearch();
  assert.equal(f.calls[1].payload.buyer_team,undefined);assert.equal(f.calls[1].payload.seller_team,'ATL');
});

test('finder selection keeps full player evidence and caps both modes at two assets',()=>{
  const f=fixture(),s=f.context.state;
  s.tradeTab='finder';s.data.tradePartner={assets:[player('first','ATL'),player('second','ATL'),player('third','ATL')]};
  f.context.toggleAsset('to','player','first');f.context.toggleAsset('to','player','second');f.context.toggleAsset('to','player','third');
  assert.equal(s.selectedTo.length,2);assert.equal(s.selectedTo[0].headshot_url,'/first.png');assert.equal(s.selectedTo[0].upside_remaining,3.1);assert.equal(s.selectedTo[0].contract,'$12.0M × 3');
  assert.match(f.messages[0],/two assets/);
});

test('empty and crowded lists retain all assets; player marks are headshots and evidence stays readable',()=>{
  const f=fixture();
  f.context.tradeCapStrip=()=>'';
  const empty=f.context.assetColumn('BKN assets',{assets:[]},'from','BKN');
  assert.match(empty,/No tradeable assets available/);assert.doesNotMatch(empty,/NaN/);
  const assets=Array.from({length:110},(_,index)=>player(`asset${index}`,'BKN'));
  const crowded=f.context.assetColumn('BKN assets',{assets},'from','BKN');
  assert.equal((crowded.match(/data-asset-side=/g)||[]).length,110);
  assert.match(crowded,/\/asset109.png/);assert.match(crowded,/Upside 3.1/);assert.match(crowded,/Injury risk 2.2 model index/);assert.match(crowded,/Contract/);
  const single=f.context.assetButton(assets[0],'from',100,'BKN');
  assert.doesNotMatch(single,/BKN.svg/);
});

test('a search response for an old team cannot overwrite the current finder team',async()=>{
  const f=fixture(),s=f.context.state;
  s.tradeTab='finder';s.selectedFrom=[f.assets.BKN.assets[0]];
  let resolve;
  f.context.action=()=>new Promise(done=>{resolve=done;});
  const pending=f.context.runTradeSearch();
  s.tradeFinderScope='CHI';s.tradeResults=[];
  resolve({candidates:[{proposal:{id:'stale'}}]});await pending;
  assert.equal(s.tradeResults.length,0);assert.equal(s.tradeSearchCompleted,false);
});

test('a refused trade preserves the entire prepared package and does not refresh as success',async()=>{
  const f=fixture(),s=f.context.state;
  s.selectedFrom=[f.assets.BKN.assets[0]];s.tradeCandidate={proposal:{id:'test'}};
  f.context.action=async()=>({status:'not_applied_rejected',notes:'Partner changed its mind'});
  f.context.refreshHome=async()=>assert.fail('Must not refresh a failed trade as completed');
  await f.context.applyCandidate(s.tradeCandidate,'builder');
  assert.equal(s.selectedFrom.length,1);assert.equal(s.tradeCandidate.proposal.id,'test');
  assert.equal(f.messages[0],'Partner changed its mind');
});

test('evaluation for an old package cannot overwrite a changed selection on the same team',async()=>{
  const f=fixture(),s=f.context.state;
  s.selectedFrom=[f.assets.BKN.assets[0]];
  let resolve;f.context.action=()=>new Promise(done=>{resolve=done;});
  const request=f.context.evaluateBuiltTrade();s.selectedFrom=[];
  resolve({proposal:{id:'stale'}});await request;
  assert.equal(s.tradeCandidate,undefined);
});

test('unknown cap and unresolved salary are not displayed as free space or zero payroll',()=>{
  const f=fixture();
  const result=f.context.tradeCapImpactRows({},[{kind:'player',salary_by_year:{}}],[],['2026-27']);
  for(const key of ['delta','payroll','players','tax','hard'])assert.equal(result[0][key],null,key);
});

test('a third participant loads real team assets and each asset has exactly one non-owner destination',async()=>{
  const f=fixture(),s=f.context.state;
  s.selectedFrom=[f.assets.BKN.assets[0]];s.selectedTo=[f.assets.ATL.assets[0]];
  await f.context.addTradeParticipant('CHI');
  assert.deepEqual(Array.from(s.tradeAdditionalTeams),['CHI']);
  f.context.toggleAsset('extra:CHI','player','target');
  assert.equal(s.tradeExtraSelections.CHI[0].id,'target');
  s.tradeAssetRoutes={'BKN:player:own':'CHI','CHI:player:target':'ATL','ATL:player:other':'BKN'};
  for(const [team,id] of [['CHI','own'],['ATL','target'],['BKN','other']]) {
    assert.deepEqual(Array.from(f.context.tradeReceivedAssets(team),asset=>asset.id),[id]);
  }
  const row=f.context.tradeAssetRow(s.selectedFrom[0],{removeSide:'from',routeFrom:'BKN'});
  assert.match(row,/data-trade-destination="BKN:player:own"/);
  assert.doesNotMatch(row,/<option value="BKN"/);
});

test('multi-team evaluation sends every routed leg and cannot apply a stale bilateral candidate',async()=>{
  const f=fixture();await f.context.addTradeParticipant('CHI');f.calls.length=0;
  f.context.state.selectedFrom=[f.assets.BKN.assets[0]];
  f.context.state.selectedTo=[f.assets.ATL.assets[0]];
  f.context.state.tradeExtraSelections={CHI:[f.assets.CHI.assets[0]]};
  f.context.state.tradeAssetRoutes={'BKN:player:own':'CHI','CHI:player:target':'ATL'};
  await f.context.evaluateBuiltTrade();
  await f.context.applyCandidate({proposal:{id:'stale-two-team'}},'builder');
  assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].name,'evaluate_trade');
  assert.equal(f.calls[0].payload.from_assets,undefined);
  assert.equal(f.calls[0].payload.transfers.length,3);
  assert.equal(f.calls[0].payload.transfers[0].to_team_id,'CHI');
  assert.match(f.messages[0],/complete multi-team/);
});

test('editing a recipient while evaluation is in flight invalidates the response',async()=>{
  const f=fixture(),s=f.context.state;await f.context.addTradeParticipant('CHI');
  s.selectedFrom=[f.assets.BKN.assets[0]];s.selectedTo=[f.assets.ATL.assets[0]];
  s.tradeExtraSelections={CHI:[f.assets.CHI.assets[0]]};
  let finish;f.context.action=()=>new Promise(resolve=>{finish=resolve;});
  const request=f.context.evaluateBuiltTrade();
  s.tradeAssetRoutes={'BKN:player:own':'CHI'};
  finish({proposal:{id:'old'},evaluations:[]});await request;
  assert.equal(s.tradeCandidate,null);
});

test('finder detour preserves a multi-team draft, routes and all extra selections',async()=>{
  const f=fixture(),s=f.context.state;s.modal={kind:'tradeRoom'};
  await f.context.addTradeParticipant('CHI');
  f.context.toggleAsset('extra:CHI','player','target');
  s.selectedFrom=[f.assets.BKN.assets[0]];s.tradeAssetRoutes={'BKN:player:own':'CHI'};
  await f.context.switchTradeWorkspace('finder');
  assert.equal(s.tradeAdditionalTeams.length,0);
  await f.context.switchTradeWorkspace('builder');
  assert.equal(s.tradeAdditionalTeams[0],'CHI');assert.equal(s.tradeExtraSelections.CHI[0].id,'target');
  assert.equal(f.context.tradeAssetDestination('BKN',s.selectedFrom[0]),'CHI');
  f.context.removeTradeParticipant('CHI');
  assert.equal(s.tradeAdditionalTeams.length,0);assert.equal(s.tradeExtraSelections.CHI,undefined);
  assert.equal(s.selectedFrom[0].id,'own');assert.equal(f.context.tradeAssetDestination('BKN',s.selectedFrom[0]),'ATL');
});

test('late additional-team responses cannot populate a different save',async()=>{
  const f=fixture();let resolve;f.context.action=()=>new Promise(done=>{resolve=done;});
  const request=f.context.addTradeParticipant('CHI');f.context.state.currentSave='new-save';
  resolve(f.assets.CHI);await request;
  assert.equal(f.context.state.tradeAdditionalTeams,undefined);
});

test('overlapping additions cannot exceed six participants or duplicate a team',async()=>{
  const f=fixture(),s=f.context.state;
  s.teams.push(...['BOS','CLE','DEN','DET'].map(abbrev=>({abbrev})));
  s.tradeAdditionalTeams=['BOS','CLE','DEN'];
  const pending=[];f.context.action=()=>new Promise(resolve=>pending.push(resolve));
  const first=f.context.addTradeParticipant('CHI');
  const duplicate=f.context.addTradeParticipant('CHI');
  const overflow=f.context.addTradeParticipant('DET');
  pending.forEach(resolve=>resolve({assets:[]}));
  await Promise.all([first,duplicate,overflow]);
  assert.equal(f.context.tradeWorkspaceParticipants().length,6);
  assert.deepEqual(Array.from(s.tradeAdditionalTeams),['BOS','CLE','DEN','CHI']);
});

test('a failed roster request leaves participants, selections and destinations intact',async()=>{
  const f=fixture(),s=f.context.state;
  s.selectedFrom=[f.assets.BKN.assets[0]];
  s.tradeAssetRoutes={'BKN:player:own':'ATL'};
  f.context.action=async()=>{throw new Error('Invalid conditional pick obligation');};
  await assert.rejects(f.context.addTradeParticipant('CHI'),/Invalid conditional/);
  assert.equal(f.context.tradeWorkspaceParticipants().length,2);
  assert.equal(s.selectedFrom[0].id,'own');
  assert.equal(s.tradeAssetRoutes['BKN:player:own'],'ATL');
});

test('three-team payroll routes incoming salary to its actual recipient and conserves dollars',async()=>{
  const f=fixture(),s=f.context.state;await f.context.addTradeParticipant('CHI');
  s.selectedFrom=[f.assets.BKN.assets[0]];s.selectedTo=[f.assets.ATL.assets[0]];
  f.assets.CHI.assets[0].salary_by_year['2026-27']=9;
  f.context.toggleAsset('extra:CHI','player','target');
  s.tradeAssetRoutes={'BKN:player:own':'CHI','CHI:player:target':'ATL','ATL:player:other':'BKN'};
  for(const payload of Object.values(f.assets))payload.cap_by_year=Object.fromEntries(['2026-27','2027-28','2028-29','2029-30'].map(year=>[year,{salary_total_millions:100,tax_line_millions:150,hard_cap_millions:200,tax_space_millions:50,hard_cap_space_millions:100}]));
  const charts=[];f.context.salaryHorizonChart=options=>{charts.push(options);return '<div></div>';};
  f.context.tradeFourYearImplications(f.assets.BKN,f.assets.ATL,s.selectedFrom,s.selectedTo,f.context.tradeWorkspaceParticipants());
  assert.equal(charts.length,6);
  const after=[charts[1],charts[3],charts[5]].map(chart=>chart.payrollByYear['2026-27']);
  assert.deepEqual(after,[100,97,103]);assert.equal(after.reduce((a,b)=>a+b,0),300);
});
