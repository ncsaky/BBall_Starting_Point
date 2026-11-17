const assert = require('node:assert/strict');
const test = require('node:test');
const projection = require('../src/nba_gm_data/gui/trade-projection.js');
const players = () => Array.from({length:12},(_,i)=>({id:`p${i}`,kind:'player',name:`Player ${i}`,mpg:Math.max(0,36-i*4),ratings:{overall:90-i*2},position:['PG','SG','SF','PF','C'][i%5],health:{status:'healthy'}}));
const profile = (delta=0) => ({zones:[{key:'rim'}],shot_chart:{basis:'projected',regions:[{id:1,frequency:.8,delta_pp:delta,suppression_delta_pp:delta/2,league_fg_pct:50}],cells:[[0,0,1,.5,.5,.5],[1,0,1,.5,.5,.5]]}});

test('baseline and inferred rotations conserve 240 minutes and never mutate player inputs',()=>{
  const roster=players(),before=JSON.stringify(roster);
  for(const infer of [false,true]){
    const result=projection.rotation(roster,infer);
    assert.equal(result.reduce((sum,row)=>sum+row.minutes,0),240);
    assert.ok(result.every(row=>row.minutes>=0&&row.minutes<=(infer?40:48)));
  }
  assert.equal(JSON.stringify(roster),before);
});

test('injuries get no projected minutes and insufficient available players refuse a full rotation',()=>{
  const roster=players();roster[0].health={status:'injured',label:'Out ~4g'};
  assert.equal(projection.rotation(roster,true)[0].minutes,0);
  assert.equal(projection.rotation(roster.slice(0,5),true),null);
});

test('draft-only packages do not change the roster; player trades retain unique identities',()=>{
  const roster=players();
  assert.deepEqual(projection.afterRoster(roster,[{kind:'pick',id:'pick'}],[]),roster);
  const incoming={...roster[0],id:'new'};
  const result=projection.afterRoster(roster,[roster[0]],[incoming,incoming]);
  assert.equal(result.length,roster.length);assert.ok(!result.some(row=>row.id==='p0'));
  assert.equal(result.filter(row=>row.id==='new').length,1);
});

test('chart aggregation uses region attempts for offense, minutes for defense, and conserves density',()=>{
  const rows=[{id:'a',minutes:180},{id:'b',minutes:60}];
  const profiles={a:profile(10),b:profile(-10)};
  const first=JSON.stringify(profiles);
  const chart=projection.combine(rows,profiles,'preview').shot_chart;
  assert.equal(chart.regions[0].delta_pp,5);
  assert.equal(chart.regions[0].suppression_delta_pp,2.5);
  assert.equal(chart.regions[0].fg_pct,55);
  assert.equal(chart.cells.reduce((sum,cell)=>sum+cell[3],0),1);
  assert.equal(chart.cells.reduce((sum,cell)=>sum+cell[4],0),1);
  assert.equal(JSON.stringify(profiles),first);
  profiles.b.shot_chart.regions[0].frequency=.4;
  assert.ok(Math.abs(projection.combine(rows,profiles,'preview').shot_chart.regions[0].delta_pp-50/7)<1e-10);
});

test('missing reference data cannot silently become a neutral or partially normalized map',()=>{
  assert.equal(projection.combine([{id:'a',minutes:240}],{},'missing'),null);
  const profiles={a:profile()};profiles.a.shot_chart.basis='unavailable';
  assert.equal(projection.combine([{id:'a',minutes:240}],profiles,'missing'),null);
});
