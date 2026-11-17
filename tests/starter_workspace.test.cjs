const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const context = {window:{}, structuredClone};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8'), context);
const {defaultLayout, initializeStarterLayout, restoreLayout, enterPhase, clipboardExtent, snapCardPositions} = context.window.CardBoard;

function fixture() {
  const cards = [['minutes',614,661], ['week',452,126], ['standings',184,354], ['opponent',452,224], ['signals',198,114], ['efficiency',266,351], ['staff',415,420], ['prospects',517,315], ['identity',503,354]];
  const result = defaultLayout(cards.map(([id,width,height],i) => ({id,width,height,x:i*100,y:0})));
  result['phase-draft-control'] = {x:16,y:16,width:320,height:240,scale:1,visible:true,required:true};
  return result;
}

function assertPacked(layout, width, height) {
  const cards = Object.entries(layout).filter(([id,item])=>item.visible && !id.startsWith('phase-')).map(([id,item]) => ({id,x:item.x,y:item.y,width:item.width*item.scale,height:24+(item.minimized?0:item.height*item.scale)}));
  for (const card of cards) {
    assert.ok(card.x>=0 && card.y>=0 && card.x+card.width<=width-12+.001 && card.y+card.height<=height-12+.001, card.id);
    for (const other of cards) if (card!==other) {
      assert.ok(card.x+card.width<=other.x || other.x+other.width<=card.x || card.y+card.height<=other.y || other.y+other.height<=card.y, `${card.id} overlaps ${other.id}`);
    }
  }
  const snapOrder = [...cards].sort((a,b)=>a.y-b.y || a.x-b.x);
  assert.equal(snapCardPositions(layout,snapOrder,width,height),true);
  return cards;
}

test('fresh workspaces fit core windows without shrinking text to fit more cards', () => {
  for (const [width,height] of [[1010,706],[1266,738],[1426,932],[1906,1012]]) {
    const extent = clipboardExtent(width,height);
    const layout = fixture();
    delete layout['phase-draft-control'];
    assert.equal(initializeStarterLayout(layout,{},extent.width,extent.height),true);
    const initial = JSON.stringify(layout);
    const cards = assertPacked(layout,extent.width,extent.height);
    assert.ok(cards.length>=3 && cards.length<=5);
    assert.equal(layout.minutes.visible,true);
    assert.equal(layout.week.visible,true);
    assert.equal(layout.week.expanded,true);
    assert.equal(layout.week.width,960);
    assert.equal(layout.minutes.scale,1);
    assert.equal(layout.staff.visible,false);
    assert.equal(layout.prospects.visible,false);
    assert.equal(layout.identity.visible,false);
    assert.equal(layout.efficiency.visible,false);
    const again = fixture();
    delete again['phase-draft-control'];
    initializeStarterLayout(again,{},extent.width,extent.height);
    assert.equal(JSON.stringify(again),initial);
    // Snap is deterministic and does not alter minimized state.
    assert.equal(layout.week.minimized,again.week.minimized);
  }
});

test('large fresh workspaces open exactly five cards, with everything else gallery-only', () => {
  const layout = fixture();
  delete layout['phase-draft-control'];
  initializeStarterLayout(layout,{},4000,3000);
  assert.deepEqual(Object.keys(layout).filter(id=>layout[id].visible).sort(),['minutes','opponent','signals','standings','week']);
});

test('partial preferences cannot reveal every newly introduced card', () => {
  const defaults = fixture();
  const saved = {version:1,cards:{minutes:{...defaults.minutes,x:111,minimized:true},staff:{...defaults.staff,visible:true}}};
  const layout = restoreLayout(JSON.stringify(saved),defaults);
  assert.deepEqual(Object.keys(layout).filter(id=>layout[id].visible).sort(),['minutes','staff']);
  assert.equal(layout.minutes.x,111);
  assert.equal(layout.minutes.minimized,true);
  assert.equal(initializeStarterLayout(layout,saved,1300,900),false);
});

test('phase entry opens at most four starter panels; optional and customized cards retain their state', () => {
  const ids = ['control','market','selected','offers','wire','payroll','cap'].map(name=>'phase-free_agency-'+name);
  const defaults = Object.fromEntries(ids.map(id=>[id,{x:16,y:16,width:320,height:100,visible:false,scale:1}]));
  const layout = structuredClone(defaults);
  enterPhase(layout,defaults,{},ids,'2026:free_agency');
  assert.deepEqual(Object.keys(layout).filter(id=>layout[id].visible),ids.slice(0,4));
  layout[ids[4]].visible=true;
  layout[ids[0]].visible=false;
  const saved = {version:1,cards:structuredClone(layout),phaseCards:ids,phaseContext:'2026:free_agency'};
  enterPhase(layout,defaults,saved,ids,'2026:free_agency');
  assert.equal(layout[ids[0]].visible,false);
  assert.equal(layout[ids[4]].visible,true);
});

test('small-screen starter tables have usable widths and Calendar keeps its full view when minimized', () => {
  const layout = fixture();
  layout.minutes.width=428;
  layout.standings.width=140;
  layout.opponent.width=309;
  const extent = clipboardExtent(1010,706);
  initializeStarterLayout(layout,{},extent.width,extent.height);
  assert.equal(layout.minutes.width,540);
  assert.equal(layout.standings.width,240);
  assert.equal(layout.opponent.width,452);
  assert.equal(layout.week.minimized,true);
  assert.equal(layout.week.expanded,true);
  assertPacked(layout,extent.width,extent.height);
});

test('valid existing preferences, including partial legacy preferences, are never initialized again', () => {
  for (const saved of [{version:1,cards:{}},{version:1,cards:{minutes:{x:111,y:222,minimized:true,pinned:true,scale:1.1}}}]) {
    const layout = fixture();
    Object.assign(layout.minutes,{x:111,y:222,minimized:true,pinned:true,scale:1.1});
    const before = JSON.stringify(layout);
    assert.equal(initializeStarterLayout(layout,saved,1300,900),false);
    assert.equal(JSON.stringify(layout),before);
  }
});

test('invalid preferences get a starter workspace, while phase decisions retain priority and state', () => {
  const layout = fixture();
  const phase = structuredClone(layout['phase-draft-control']);
  assert.equal(initializeStarterLayout(layout,{version:99,cards:{}},1300,900,['phase-draft-control']),true);
  assert.deepEqual(layout['phase-draft-control'],phase);
  assert.equal(layout.minutes.visible,false);
  assert.equal(layout.week.visible,false);
});

test('tutorial previews its hidden cards temporarily and restores the workspace on skip or finish', () => {
  const app = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const board = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(app,/window\.CardBoard\?\.previewTutorialWindow\(step\.card\)/);
  assert.match(app,/function finishGameTutorial\(\)[\s\S]*?window\.CardBoard\?\.endTutorialPreview\(\)/);
  for (const id of ['minutes','signals','development','staff','week','efficiency']) assert.ok(app.includes(`card: "${id}"`));
  const preview = board.slice(board.indexOf('let tutorialWorkspace = null;'),board.indexOf('for (const [id, node] of nodes)',board.indexOf('let tutorialWorkspace = null;')));
  assert.match(preview,/layout = structuredClone\(tutorialWorkspace\.layout\)/);
  assert.match(preview,/item\.visible = true;\s*item\.minimized = false;/);
  assert.doesNotMatch(preview,/save\(\)|options\.onOpen|onExpandedChange/);
});
