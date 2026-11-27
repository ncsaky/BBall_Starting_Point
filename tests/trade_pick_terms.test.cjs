const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const test=require('node:test');
const path=require('node:path');
const scope={window:{},structuredClone};vm.createContext(scope);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/gui/trade-pick-terms.js'),'utf8'),scope);
const api=scope.window.TradePickTerms;
const pick=(id,year,team='A',round=1)=>({kind:'pick',id,season:String(year),round,original_team_id:team,original_team_abbrev:team,terms_editable:true});
const a=pick('a27',2027), b=pick('a29',2029), c=pick('b27',2027,'B');
const rows=[{team:'A',recipient:'B',selected:[a],payload:{picks:[a,b]}},{team:'B',recipient:'A',selected:[],payload:{picks:[c]}}];
const rule={key:'condition-1',pick_id:a.id,type:'protected_pick',from:1,through:4,fallback_pick_ids:[b.id],enabled:true};

test('structured range and replacement require no text entry',()=>{
  const markup=api.markup(rows,[rule]);
  assert.match(markup,/Protected positions/);assert.match(markup,/If protected, convey instead/);
  assert.match(markup,/data-pick-add/);assert.match(markup,/data-pick-remove/);
  assert.doesNotMatch(markup,/<textarea|type="(?:text|number)"/);
  assert.equal(api.errors([rule],rows).length,0);
  assert.deepEqual(JSON.parse(JSON.stringify(api.request([rule]))),[{pick_id:'a27',type:'protected_pick',from:1,through:4,fallback_pick_ids:['a29']}]);
});
test('incomplete or reused collateral cannot be submitted',()=>{
  assert.equal(api.errors([{...rule,fallback_pick_ids:[]}],rows).length,1);
  assert.equal(api.errors([{...rule,fallback_pick_ids:['b27']}],rows).length,1);
  assert.ok(api.errors([rule,{...rule,key:'condition-2'}],rows).length);
  assert.equal(api.errors([{...rule,enabled:false}],rows).length,0);
  assert.equal(api.request([{...rule,enabled:false}]).length,0);
});
test('first-round protections cannot stop at picks 12 through 15',()=>{
  for (const through of [12,13,14,15]) assert.match(api.errors([{...rule,through}],rows)[0].message,/league doesn't allow/);
  for (const through of [11,16,30]) assert.equal(api.errors([{...rule,through}],rows).length,0);
  const second=[pick('a27',2027,'A',2),pick('a29',2029,'A',2)];
  const secondRows=[{...rows[0],selected:[second[0]],payload:{picks:second}},rows[1]];
  assert.equal(api.errors([{...rule,from:31,through:45}],secondRows).length,0);
});
test('swaps require a known recipient and matching underlying pick',()=>{
  const swap={...rule,type:'pick_swap',other_pick_id:'b27',benefit:'worse'};
  assert.equal(api.errors([swap],rows).length,0);
  assert.match(api.markup(rows,[swap]),/Less favorable pick/);
  assert.equal(api.errors([swap],[{...rows[0],recipient:''}]).length,1);
  assert.equal(api.errors([swap],[rows[0],{...rows[1],payload:{picks:[pick('b27',2028,'B')]}}]).length,1);
});
test('removing a primary prunes its conditions but does not rewrite other rows',()=>{
  assert.equal(api.prune([rule],[{...rows[0],selected:[]}]).length,0);
  assert.equal(api.prune([rule],rows)[0],rule);
  assert.equal(api.eligible({...a,terms_editable:false}),false);
  assert.equal(api.eligible({...a,has_conditions:true}),false);
});
test('checkbox and range events clone the rule and preserve explicit choices',()=>{
  let handler, changed;
  const control={dataset:{pickKey:'condition-1',pickField:'from'},value:'8',addEventListener(name,fn){handler=fn;}};
  const root={querySelector:()=>null,querySelectorAll:selector=>selector==='[data-pick-field]'?[control]:[]};
  api.wire(root,rows,[rule],next=>changed=next);handler();
  assert.equal(changed[0].from,8);assert.equal(changed[0].through,8);assert.equal(rule.from,1);
  control.dataset.pickField='enabled';control.checked=false;
  api.wire(root,rows,[rule],next=>changed=next);handler();
  assert.equal(changed[0].enabled,false);assert.equal(rule.enabled,true);
});
test('labels are escaped rather than becoming executable markup',()=>{
  const bad={...a,original_team_abbrev:'<img src=x onerror=alert(1)>'};
  const markup=api.markup([{...rows[0],selected:[bad]}],[rule]);
  assert.doesNotMatch(markup,/<img src=x/);assert.match(markup,/&lt;img/);
});
