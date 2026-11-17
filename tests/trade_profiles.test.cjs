const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
const escape = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
function fixture() {
  const scope = {
    state:{tradeSearchCompleted:false,tradeTab:'builder',data:{}},
    escapeHtml:escape, escapeAttr:escape, teamLabel:value=>String(value).replace('team_','').toUpperCase(),
    userTeam:()=> 'BKN', teamLogoSrc:team=>`/logo/${team}.png`,
    draftMetric:value=>value == null ? '—' : Number(value).toFixed(1),
    money:value=>`$${Number(value).toFixed(1)}M`, shortSeasonLabel:season=>season,
    playerHeadshotMarkup:asset=>asset.headshot_url ? `<img src="${escape(asset.headshot_url)}">` : '',
    playerNameWithInjuryMarkup:(asset,name)=>escape(name),
    clampNumber:(value,min,max)=>Math.max(min,Math.min(max,value)),
    playerEvidenceRing:(label,value)=>`<span data-ring="${label}">${value}</span>`,
    performanceBarStyle:value=>`--fill:${value}%`, playerUpsideColor:()=> '#468563', draftAssetGlyph:()=>'<span class="draft-asset-glyph"></span>',
    rowLabel:value=>value, textValue:value=>value,
    tradeSegmentedValueBoard:()=>'<section>Value breakdown</section>',
    tradeEvaluationPanel:()=>'<section>Evaluation</section>',
    tradeHeadline:()=> 'Trade completed: player for player',
  };
  vm.createContext(scope);
  vm.runInContext(source.slice(source.indexOf('function tradeResultCards('),source.indexOf('function tradeOfferSide(')),scope);
  return scope;
}

test('player proposal rows preserve contract, ratings, age, upside, health and portrait evidence',()=>{
  const s=fixture();
  const markup=s.incomingOfferAsset({kind:'player',id:'one',name:'A <B>',headshot_url:'/one.png',position:'SF',age:24,overall:81.3,potential:88.2,trade_value:62.7,upside_remaining:3.2,health_risk:1.7,mpg:32.5,ppg:21.4,salary_by_year:{'2026-27':20,'2027-28':25,'2028-29':30},contract:'Signed through 2028-29'});
  for (const value of ['81.3','88.2','62.7','3.2','1.7','32.5','21.4','>24<','/one.png','2028-29','$30.0M','Signed through 2028-29']) assert.ok(markup.includes(value),value);
  assert.match(markup,/data-dashboard-player-card="one"/);
  assert.match(markup,/A &lt;B&gt;/);
  assert.doesNotMatch(markup,/A <B>/);
});

test('missing player evidence remains unknown rather than inventing zero meters',()=>{
  const markup=fixture().incomingOfferAsset({kind:'player',id:'unknown',name:'Unknown'});
  assert.doesNotMatch(markup,/data-ring/);
  assert.match(markup,/Injury risk unavailable/);
  assert.match(markup,/Runway unavailable/); // "Upside" renamed "Growth runway" (M03, 2026-11-17)
  assert.doesNotMatch(markup,/NaN|width:0%/);
});

test('unverified legality is not legal and manual-review reasons are visible and escaped',()=>{
  const s=fixture();
  const unknown=s.offerCard({proposal:{from_team:'BKN',to_team:'NYK'}},0);
  assert.match(unknown,/Not verified/);assert.match(unknown,/data-offer-accept="0" disabled/);
  const manual=s.offerCard({proposal:{from_team:'BKN',to_team:'NYK'},legality:{status:'manual_review_required',manual_review:['Missing <salary>']}},0);
  assert.match(manual,/Review required/);assert.match(manual,/Missing &lt;salary&gt;/);
});

test('injury risk preserves the actual model index rather than incorrectly claiming a 0-10 scale',()=>{
  const s=fixture();
  const html=s.incomingOfferAsset({kind:'player',name:'Known',health_risk:13.3});
  assert.match(html,/13.3 model index/);assert.doesNotMatch(html,/13.3\/10/);
});

test('protected pick details appear once; plain picks have no redundant condition text',()=>{
  const s=fixture();
  const markup=s.incomingOfferAsset({kind:'pick',label:'2028 R1 PHI; top-8 protected',protection_summary:'top-8 protected',trade_value:25});
  assert.equal((markup.match(/top-8 protected/g)||[]).length,1);
  assert.doesNotMatch(s.incomingOfferAsset({kind:'pick',label:'2028 R1 BKN',protection_summary:'unprotected'}),/unprotected/i);
});

test('the incoming/finder package renderer is not limited to two receiving teams',()=>{
  const s=fixture();
  const html=s.incomingOfferPackage(['BKN','CHI','ATL','DEN'].map(team=>({team,assets:[{kind:'pick',label:`${team} incoming pick`}]})));
  for(const team of ['BKN','CHI','ATL','DEN'])assert.match(html,new RegExp(`${team} receives`));
  assert.equal((html.match(/class="incoming-offer-side"/g)||[]).length,4);
});

test('crowded incoming and finder packages retain every asset with correct receiving teams',()=>{
  const s=fixture();
  const from=Array.from({length:18},(_,i)=>({kind:i<15?'player':'pick',id:`from-${i}`,name:`Player ${i}`,label:`Asset ${i}`,overall:70+i}));
  const offer={proposal:{from_team_id:'team_bkn',to_team_id:'team_nyk',from_assets:from,to_assets:[]},legality:{status:'illegal',issues:['Salary mismatch']},evaluations:[]};
  for (const markup of [s.offerCard(offer,0),s.tradeCandidateCard(offer,0,'finder')]) {
    for (let i=0;i<18;i++) assert.ok(markup.includes(i<15?`Player ${i}`:`Asset ${i}`),`missing asset ${i}`);
    assert.match(markup,/NYK receives/);
    assert.match(markup,/BKN receives/);
    assert.match(markup,/No assets in this package/);
  }
  assert.match(s.offerCard(offer,0),/data-offer-accept="0" disabled/);
});

test('search states and return navigation preserve a prepared trade without refetching assets',()=>{
  const s=fixture();
  assert.match(s.tradeResultCards([]),/Select assets/);
  s.state.tradeSearchCompleted=true;
  assert.match(s.tradeResultCards([]),/No matching offers/);
  let renders=0;
  s.renderModal=()=>renders++;
  s.tradeRoomModalBody=()=> 'prepared package';
  vm.runInContext(source.slice(source.indexOf('function returnToPlayerTradeContext('),source.indexOf('function wireOfferButtons(')),s);
  s.returnToPlayerTradeContext({kind:'tradeRoom',activeTab:'finder'});
  assert.equal(s.state.tradeTab,'finder');
  assert.equal(s.state.modal.body,'prepared package');
  assert.equal(renders,1);
});

test('contract summaries separate the current deal and extension in the requested compact format',()=>{
  const s=fixture();
  const html=s.tradeAssetContract({salary_by_year:{'2026-27':8,'2027-28':30,'2028-29':32},contract_terms:[{salary:8000000,years:1},{salary:30000000,years:2}]});
  assert.match(html,/\$8.0M x 1, \$30.0M x 2/);
  assert.match(html,/2028-29 \$32.0M/);
});

test('every nutshell rating summary includes OVR, OFF and DEF in the shared bar style',()=>{
  const s=fixture();
  const html=s.playerSummaryRatings({ratings:{overall:80,shooting:75,creation:80,passing:85,defense:70}});
  for(const value of ['OVR','OFF','DEF','80.0','70.0','--fill:80%','--fill:70%']) assert.ok(html.includes(value),value);
  assert.equal((html.match(/assets-rating-bar/g)||[]).length,3);
  assert.match(s.playerSummaryRatings({}),/>—</);
});

test('real draft glyphs safely render legacy swaps and current protected picks',()=>{
  const s=fixture();
  const assetSource=fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/assets-desktop.js'),'utf8');
  vm.runInContext(assetSource.slice(assetSource.indexOf('function pickTeamAbbrev('),assetSource.indexOf('// Keep condition details')),s);
  assert.doesNotThrow(()=>s.draftAssetGlyph({kind:'pick_swap',label:'2028 pick swap'},true,true));
  const swap=s.draftAssetGlyph({kind:'pick_swap',original_team_ids:['team_bkn','team_phi'],label:'2028 BKN/PHI swap'},true,true);
  assert.match(swap,/BKN/);assert.match(swap,/PHI/);
  const pick=s.draftAssetGlyph({kind:'pick',original_team_abbrev:'PHI',label:'2028 R1 PHI; top-8 protected',condition_summary:'top-8 protected'},true,true);
  assert.match(pick,/data-draft-asset-tooltip="2028 R1 PHI; top-8 protected"/);
});

test('a trade player link is wired once even when both the trade and modal wire it',()=>{
  const s=fixture(), listeners=[];
  let opens=0;
  const button={dataset:{dashboardPlayerCard:'one'},addEventListener:(_event,fn)=>listeners.push(fn)};
  const root={querySelectorAll:()=>[button]};
  s.dashboardPlayerCard=()=>opens++;
  vm.runInContext(source.slice(source.indexOf('function wireDashboardPlayerCards('),source.indexOf('function wireDashboardProspectCards(')),s);
  s.wireDashboardPlayerCards(root);s.wireDashboardPlayerCards(root);
  listeners.forEach(fn=>fn());
  assert.equal(opens,1);assert.equal(listeners.length,1);
});
