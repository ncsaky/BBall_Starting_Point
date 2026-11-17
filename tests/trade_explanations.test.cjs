const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const source=fs.readFileSync(require('node:path').join(__dirname,'../src/nba_gm_data/gui/app.js'),'utf8');
function panel(row){
  const scope={tradeKnownNumber:v=>v==null?null:Number(v),clampNumber:(v,a,b)=>Math.max(a,Math.min(b,v)),
    textValue:String,escapeHtml:v=>String(v).replaceAll('<','&lt;'),teamLabel:String};
  vm.createContext(scope);
  vm.runInContext(source.slice(source.indexOf('function tradeEvaluationPanel('),source.indexOf('function freeAgentOfferPanel(')),scope);
  return scope.tradeEvaluationPanel(row);
}
test('legacy phase names map to the four window phases and real note threshold repairs old meters',()=>{
  const html=panel({accepted:true,net_value:1,acceptance_threshold:2,acceptance_score:45,
    notes:'Phase=retooling; threshold 0.8; strategic fit 1; personality adjustment 0.'});
  assert.match(html,/Exiting peak window/);
  assert.match(html,/\+0.2 above line/);
  assert.match(html,/Not an acceptance probability/);
});
test('a positive value meter does not hide a premium-return rejection',()=>{
  const html=panel({accepted:false,decision:'reject_premium_return',net_value:20,acceptance_threshold:2,
    incoming_asset_value:100,outgoing_value:85,strategic_adjustment:4,personality_adjustments:{total:1},
    window_phase:'entering',notes:'Phase=entering;',decision_reasons:['Missing <centerpiece>']});
  assert.match(html,/Would decline/);assert.match(html,/Entering peak window/);
  assert.match(html,/Missing &lt;centerpiece>/);assert.match(html,/Strategy \+ roster plan/);
  assert.match(html,/\+18.0 above line/);
});
test('bounded negotiation is named explicitly rather than suggesting ordinary approval',()=>{
  const html=panel({accepted:true,decision:'accept_bounded_ai_discretion',net_value:-3.7,acceptance_threshold:.8,
    incoming_asset_value:40,notes:''});
  assert.match(html,/Accepts limited value loss/);
  assert.match(html,/below line/);
  assert.match(html,/bounded negotiation discretion/);
});
