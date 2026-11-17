const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
function runtime() {
  const c = {gameArtwork:()=>'', escapeHtml:String,
    playerCardRatingBar:(label,value,key)=>`<div data-key="${key}">${label}:${value}</div>`};
  vm.createContext(c);
  for (const [start,end] of [['function playerCardRatingGroups(', 'function playerCardRatingRows('],
                            ['function playerCardGroupedRatings(', 'function approvedCapShareChart('],
                            ['function rating(row, key)', 'function statsContextLabel(']]) {
    vm.runInContext(source.slice(source.indexOf(start),source.indexOf(end)),c);
  }
  return c;
}
const oldKeys = ['shooting','release','range','versatility','spacing','creation','handle','passing','rim_pressure',
  'defense','def_effort','screen_nav','steal','block','rim_deterrence','rebounding','oreb',
  'athleticism','lateral_agility','stamina','iq','scheme_iq','portability','playoff'];
const legacy = () => Object.fromEntries(oldKeys.map(key=>[key,65]));
const updated = () => ({...legacy(),post_creation:70,assisted_finishing:84,screening:91,offensive_rebounding:98});

test('new offensive ratings add only three bars, retaining all existing skills once',()=>{
  const groups = runtime().playerCardRatingGroups(updated(),false);
  const rows = groups.flatMap(g=>g.rows);
  assert.equal(rows.length,27);
  for (const label of ['Rim pressure','Post creation','Assisted finishing','Screening','Offensive rebounding']) {
    assert.equal(rows.filter(row=>row[0]===label).length,1,label);
  }
  assert.equal(rows.find(row=>row[0]==='Offensive rebounding')[1],98);
});

test('balanced three-column grouping preserves the standard row markup',()=>{
  const html = runtime().playerCardGroupedRatings(updated(),{}, {Offense:'<div>Existing offense radar</div>',Defense:'<div>Existing defense radar</div>'});
  const columns = html.split('<div class="approved-rating-column">').slice(1);
  assert.equal(columns.length,3);
  assert.equal((columns[0].match(/data-key=/g)||[]).length,8);
  assert.equal((columns[1].match(/data-key=/g)||[]).length,8);
  assert.equal((columns[2].match(/data-key=/g)||[]).length,11);
  assert.ok(columns[0].includes('Existing offense radar'));
  assert.ok(columns[1].includes('Existing defense radar'));
  assert.ok(columns[1].includes('Athleticism'));
  assert.ok(columns[2].indexOf('Interior & Rebounding')<columns[2].indexOf('Mind, Body & Coach'));
  assert.ok(columns[2].includes('Portability')&&columns[2].includes('Playoff translation'));
  assert.ok(html.includes('class="approved-rating-rail"'));
  assert.ok(!html.includes('font-size')&&!html.includes('overflow')&&!html.includes('scale('));
});

test('legacy player cards keep their original groups and column placement',()=>{
  const c=runtime(), groups=c.playerCardRatingGroups(legacy(),false);
  assert.equal(groups.flatMap(g=>g.rows).length,24);
  assert.ok(!groups.some(g=>g.label==='Interior & Rebounding'));
  assert.ok(groups[0].rows.some(row=>row[0]==='Rim pressure'));
  const columns=c.playerCardGroupedRatings(legacy(),{}).split('<div class="approved-rating-column">').slice(1);
  assert.equal((columns[0].match(/data-key=/g)||[]).length,9);
  assert.equal((columns[1].match(/data-key=/g)||[]).length,6);
  assert.equal((columns[2].match(/data-key=/g)||[]).length,9);
  assert.ok(columns[2].includes('Coach Perspective'));
});

test('missing ratings are not invented and locked prospect values stay unknown',()=>{
  const c=runtime(), ratings={...legacy(),post_creation:null,assisted_finishing:null,screening:null};
  const hidden=c.playerCardRatingGroups(ratings,false).find(g=>g.label==='Interior & Rebounding');
  assert.equal(hidden.rows.length,3);
  const locked=c.playerCardRatingGroups(ratings,false,true).find(g=>g.label==='Interior & Rebounding');
  assert.equal(locked.rows.length,6);
  assert.ok(locked.rows.slice(1,4).every(row=>row[1]===null));
});

test('explicit OFF wins over legacy recomputation, without changing the legacy fallback',()=>{
  const c=runtime();
  assert.equal(c.rating({ratings:{shooting:60,creation:60,passing:60,offense:71}},'offense'),71);
  assert.equal(c.rating({offense:75,ratings:{offense:71}},'offense'),75);
  assert.equal(c.rating({ratings:{shooting:60,creation:66,passing:69}},'offense'),65);
});
