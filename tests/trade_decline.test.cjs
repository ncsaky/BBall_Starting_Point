const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const responseCode = source.slice(source.indexOf('async function respondOffer('), source.indexOf('function isClipboardPhase('));

test('an offer follow-up renders one actionable package with its repeat count', () => {
  const code = source.slice(source.indexOf('function offerCard('), source.indexOf('function tradeCandidateCard('));
  const context = {teamLabel:value=>value, escapeHtml:String, tradeLegalityBadge:()=>'',
    incomingOfferPackage:()=>'<div>package</div>', tradeReceipts:()=>[],
    tradeLegalityIssues:()=>'', tradeCandidateInsights:()=>''};
  vm.createContext(context); vm.runInContext(code, context);
  const html = context.offerCard({proposal:{id:'one',from_team_id:'a',to_team_id:'b'},
    legality:{status:'legal'}, repeat_count:3, repeat_dates:['2026-12-01','2026-12-03']},0);
  assert.match(html,/incoming-offer--repeated/);
  assert.match(html,/Sent 3×/);
  assert.match(html,/latest 2026-12-03/);
  assert.equal((html.match(/data-offer-accept=/g)||[]).length,1);
});

function fixture(view = 'dashboard', handler) {
  const offers = [{proposal:{id:'first'}}, {proposal:{id:'second'}}];
  const calls = [], counts = [];
  let refreshes = 0, modalRenders = 0, offerRenders = 0;
  let shell = {scrollTop:320};
  const context = {
    state:{currentSave:'save', view, data:{dashboardOffers:{offers}}, home:{save:{pending_counts:{user_trade_offers:2}}},
      modal:view === 'dashboard' ? {kind:'tradeOffers', offers} : null},
    els:{modalRoot:{querySelector:()=>shell}},
    window:{CardBoard:{updateOfferCount:count=>counts.push(count)}},
    savePayload:()=>({save_path:'save'}), rowLabel:value=>value, showToast:()=>{}, tradeResponseEffect:()=>{},
    action:async (name,payload)=>{
      calls.push({name,payload});
      return handler ? handler(name,payload) : {status:'rejected',pending_offer_ids:['second'],offer_count:1};
    },
    refreshHome:async()=>{refreshes++;}, tradeOffersModalBody:offers=>offers.map(row=>row.proposal.id).join(','),
    renderModal:()=>{modalRenders++;shell={scrollTop:0};}, renderOffers:()=>offerRenders++,
  };
  vm.createContext(context); vm.runInContext(responseCode,context);
  return {context, offers, calls, counts, refreshes:()=>refreshes, modalRenders:()=>modalRenders, offerRenders:()=>offerRenders, scroll:()=>shell.scrollTop};
}

test('declining updates the modal and badge with one request, preserves scrolling, and skips dashboard refresh', async()=>{
  const f=fixture();
  await f.context.respondOffer(f.offers[0],'reject');
  assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].payload.summary_only,true);
  assert.equal(f.context.state.data.dashboardOffers.offers[0].proposal.id,'second');
  assert.equal(f.context.state.modal.body,'second');
  assert.equal(f.context.state.home.save.pending_counts.user_trade_offers,1);
  assert.deepEqual(f.counts,[1]);
  assert.equal(f.refreshes(),0);
  assert.equal(f.modalRenders(),1);
  assert.equal(f.scroll(),320);
});

test('standalone inbox and the empty inbox update without loading the dashboard', async()=>{
  const f=fixture('offers',()=>({status:'rejected',pending_offer_ids:[],offer_count:0}));
  await f.context.respondOffer(f.offers[0],'reject');
  assert.equal(f.context.state.data.offers.offers.length,0);
  assert.equal(f.offerRenders(),1);
  assert.equal(f.refreshes(),0);
});

test('failed decline keeps the offer visible and does not report success', async()=>{
  const f=fixture('dashboard',()=>{throw new Error('Save failed');});
  await assert.rejects(f.context.respondOffer(f.offers[0],'reject'),/Save failed/);
  assert.equal(f.context.state.modal.offers.length,2);
  assert.equal(f.modalRenders(),0);
  assert.deepEqual(f.counts,[]);
});

test('a newly arrived offer fetches inbox details once without refreshing the dashboard', async()=>{
  const f=fixture('dashboard',name=>name === 'respond_user_trade_offer'
    ? {status:'rejected',pending_offer_ids:['second','new'],offer_count:2}
    : {offer_count:2,offers:[{proposal:{id:'second'}},{proposal:{id:'new'}}]});
  await f.context.respondOffer(f.offers[0],'reject');
  assert.deepEqual(f.calls.map(call=>call.name),['respond_user_trade_offer','user_trade_offers']);
  assert.equal(f.context.state.modal.offers[1].proposal.id,'new');
  assert.equal(f.refreshes(),0);
});

test('acceptance retains the full dashboard refresh for roster and contract changes', async()=>{
  const f=fixture('offers',()=>({status:'applied',offers:{offer_count:0,offers:[]}}));
  await f.context.respondOffer(f.offers[0],'accept');
  assert.equal(f.calls[0].payload.summary_only,undefined);
  assert.equal(f.refreshes(),1);
});
