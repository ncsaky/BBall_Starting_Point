const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {loadHouseTables} = require('./house_table_helpers.cjs');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const context = {window:{}, structuredClone};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8'), context);
const {defaultLayout, enterPhase, restoreLayout, migrateDefaultCalendar, toggleWindowExpansion, enforceRequiredWindows, centerNewRequiredWindows, constrainCardBounds, snapCardPositions, clipboardExtent, diagonalScaleDelta, migrateCardSizes, galleryCategoryFor, switchableWindowOrder, frontmostVisibleWindow, selectedWindowId, cycleWindowIndex, altWindowSwitcherDirection} = context.window.CardBoard;

test('prospect origins use bundled college marks or country flags', () => {
  const appSource = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const originStart = appSource.indexOf('const PROSPECT_COLLEGE_LOGOS =');
  const originEnd = appSource.indexOf('\nfunction seasonProspectsCard(',originStart);
  assert.ok(originStart >= 0 && originEnd > originStart);
  const originContext = {
    escapeHtml:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),
    escapeAttr:value=>String(value).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),
  };
  vm.createContext(originContext);
  vm.runInContext(appSource.slice(originStart,originEnd),originContext);
  assert.match(originContext.prospectOriginMarkup('Duke'),/\/assets\/team_logos\/colleges\/duke\.png/);
  assert.match(originContext.prospectOriginMarkup('France'),/season-prospect-flag/);
  assert.match(originContext.prospectOriginMarkup('KK Mega Basket'),/🇷🇸/);
  assert.match(originContext.prospectOriginMarkup('Valencia'),/🇪🇸/);
  assert.match(originContext.prospectOriginMarkup('Unknown Academy'),/season-prospect-source-fallback/);
  // Source names spelled differently from the logo files still find their logo or flag.
  assert.match(originContext.prospectOriginMarkup('Ohio St.'),/colleges\/ohio-state\.png/);
  assert.match(originContext.prospectOriginMarkup('Connecticut'),/colleges\/uconn\.png/);
  assert.match(originContext.prospectOriginMarkup('Baskonia'),/🇪🇸/);
  assert.match(originContext.prospectOriginMarkup('Prolific Prep (Fort Lauderdale, FL)'),/>PP</);
  // Draft-range box plot: whiskers (every team), box (middle half), league tick and your scouts' dot on one scale.
  originContext.clampNumber = (value,min,max)=>Math.min(max,Math.max(min,value));
  const range = originContext.seasonProspectRankRange({consensusRank:9,rank:14,draftRangeLow:7,draftRangeHigh:12,consensusBest:5,consensusWorst:22},25,'rank');
  assert.match(range,/range-whisker" style="left:16\.7%;width:70\.8%"/);
  assert.match(range,/range-box" style="left:25\.0%;width:20\.8%"/);
  assert.match(range,/range-median" style="left:33\.3%"/);
  assert.match(range,/range-ours" style="left:54\.2%"/);
  assert.match(range,/range-number">9</);
  assert.equal(originContext.seasonProspectRankRange({},25,'rank'),'—');
  assert.match(appSource,/sourceTeam:\s*prospect\.source_team/);
  assert.match(appSource,/prospectOriginMarkup\(row\.sourceTeam\)/);

  const draftSource = fs.readFileSync(path.join(__dirname,'../src/nba_gm_data/draft.py'),'utf8');
  const generatedStart = draftSource.indexOf('GENERATED_SOURCE_TEAMS = (');
  const generatedEnd = draftSource.indexOf('\n)\n\n\ndef generated_source_team',generatedStart);
  const generatedSources = draftSource.slice(generatedStart,generatedEnd);
  const origins = [...generatedSources.matchAll(/"([^"]+)"/g)].map(([,origin])=>origin);
  assert.ok(origins.length >= 60);
  for (const origin of origins) {
    assert.match(originContext.prospectOriginMarkup(origin),/season-prospect-(?:college-logo|flag)/,origin);
  }
  assert.match(draftSource,/generated_source_team\(rng, available_source_teams\)/);
  assert.match(draftSource,/available\.pop\(rng\.randrange\(len\(available\)\)\)/);

  const collegeAssets = fs.readdirSync(path.join(gui,'assets/team_logos/colleges')).filter(file=>file.endsWith('.png'));
  assert.equal(collegeAssets.length,125); // 44 original marks plus 81 added 2026-11-23 (every college in the prospect data)
});

test('window switcher follows recent window order and wraps forward and backward', () => {
  const layout = {
    first:{visible:true,z:2},
    recent:{visible:true,z:5},
    closed:{visible:false,z:9},
  };
  assert.deepEqual(switchableWindowOrder(layout,['first','recent','closed']),['recent','first']);
  assert.equal(cycleWindowIndex(0,2,1),1);
  assert.equal(cycleWindowIndex(0,2,-1),1);
  assert.equal(cycleWindowIndex(1,2,1),0);
  assert.equal(cycleWindowIndex(0,0,1),-1);
});

test('Option+Tab cycles forward and Option+Backquote cycles backward', () => {
  assert.equal(altWindowSwitcherDirection({key:'Tab',code:'Tab',altKey:true}),1);
  assert.equal(altWindowSwitcherDirection({key:'Tab',code:'Tab',altKey:true,shiftKey:true}),-1);
  assert.equal(altWindowSwitcherDirection({key:'Dead',code:'Backquote',altKey:true}),-1);
  assert.equal(altWindowSwitcherDirection({key:'`',code:'Backquote',altKey:true}),-1);
  assert.equal(altWindowSwitcherDirection({key:'`',code:'Backquote',altKey:false}),null);
  assert.equal(altWindowSwitcherDirection({key:'Tab',code:'Tab',altKey:true,metaKey:true}),null);
});

test('Escape targets the selected visible card, then the frontmost remaining card', () => {
  const layout = {
    lower:{visible:true,z:2},
    selected:{visible:true,z:4},
    minimized:{visible:true,z:6},
    closed:{visible:false,z:9},
  };
  assert.equal(selectedWindowId(layout,['lower','selected','minimized','closed'],'selected'),'selected');
  assert.equal(selectedWindowId(layout,['lower','selected','minimized','closed'],'closed'),'minimized');
  assert.equal(frontmostVisibleWindow(layout,['lower','selected','minimized','closed'],'minimized'),'selected');
  assert.equal(frontmostVisibleWindow(layout,['lower','selected','minimized','closed'],'selected'),'minimized');
  assert.equal(frontmostVisibleWindow({closed:{visible:false,z:1}},['closed']),null);
});

test('Escape closes and Shift+Escape toggles the active card without bypassing locks', () => {
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const interfaceSource = fs.readFileSync(path.join(gui,'interface.js'),'utf8');
  assert.match(interfaceSource,/if \(event\.key === 'Escape'\)[\s\S]*?if \(event\.repeat\) return;[\s\S]*?else if \(config\.modal\(\)\) config\.closeModal\(\);[\s\S]*?else if \(event\.shiftKey\) window\.CardBoard\?\.toggleActiveMinimize\(\);[\s\S]*?else window\.CardBoard\?\.closeActive\(\);/);
  assert.match(source,/const closeWindow = \(id, focusNext = false\) => \{[\s\S]*?nodes\.get\(id\)\?\.required\) return false;/);
  assert.match(source,/const toggleWindowMinimized = \(id, focusControl = false\) => \{[\s\S]*?locked\(id\) \|\| nodes\.get\(id\)\?\.required\) return false;/);
  assert.match(source,/aria-keyshortcuts="Escape Shift\+Escape M P Space" title="Move \$\{safeTitle\}; Esc closes, Shift\+Esc minimizes or restores; M minimizes or restores, P pins, Space expands or collapses"/);
});

test('M, P, and Space operate on the selected card', () => {
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const interfaceSource = fs.readFileSync(path.join(gui,'interface.js'),'utf8');
  assert.match(interfaceSource,/if \(!config\.modal\(\) && \['m', 'p', ' '\]\.includes\(key\)\)[\s\S]*toggleActiveMinimize\(\)[\s\S]*toggleActivePin\(\)[\s\S]*toggleActiveExpansion\(\)/);
  assert.match(source,/const toggleActiveWindowPinned = \(\) => \{[\s\S]*const id = selectedWindow\(\);[\s\S]*layout\[id\]\.pinned = !layout\[id\]\.pinned;/);
  assert.match(source,/const toggleActiveWindowExpanded = \(\) => galleryOpen \? false : toggleWindowExpanded\(selectedWindow\(\), true\)/);
  assert.match(source,/toggleActiveMinimize:toggleActiveWindowMinimized, toggleActivePin:toggleActiveWindowPinned, toggleActiveExpansion:toggleActiveWindowExpanded/);
});

test('window switcher has keyboard access and an accessible dialog', () => {
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const appSource = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  assert.match(source,/data-window-switcher-open[^>]*aria-controls="cardWindowSwitcher"[^>]*aria-haspopup="dialog"/);
  assert.match(source,/aria-keyshortcuts="Alt\+Tab Alt\+Backquote"/);
  assert.match(source,/event\.code === "Backquote"/);
  assert.match(source,/aria-modal="true" aria-label="Switch windows"/);
  assert.match(source,/const direction = altWindowSwitcherDirection\(event\)/);
  assert.match(source,/event.shiftKey \? -1 : 1/);
  assert.match(source,/event.key === "Escape"[\s\S]*?finishWindowSwitcher\(false\)/);
  assert.match(appSource,/label:"Switch windows", keys:"g w"/);
  const interfaceSource = fs.readFileSync(path.join(gui,'interface.js'),'utf8');
  assert.match(interfaceSource,/Option\/Alt\+Tab forward, Option\/Alt\+\$\{String\.fromCharCode\(96\)\} backward/);
});
test('Trades menu opens with T without stealing the G C Cards shortcut', () => {
  const interfaceSource = fs.readFileSync(path.join(gui,'interface.js'),'utf8');
  const boardSource = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const appSource = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  assert.match(interfaceSource,/if \(key === 't' && !config\.modal\(\)\) \{\s*const trigger = document\.querySelector\('\[data-trade-menu-trigger\]'\);\s*if \(trigger && !trigger\.disabled\) \{ event\.preventDefault\(\); trigger\.click\(\); \}/);
  assert.ok(interfaceSource.indexOf('if (prefix) {') < interfaceSource.indexOf("if (key === 't' && !config.modal())"));
  const prefixStart = interfaceSource.indexOf("if (['g','s'].includes(key))");
  const prefixEnd = interfaceSource.indexOf('\n  }',prefixStart);
  assert.doesNotMatch(interfaceSource.slice(prefixStart,prefixEnd),/data-trade-menu-trigger/);
  assert.match(interfaceSource,/\['\[data-trade-menu-trigger\]', 'T'\]/);
  assert.match(boardSource,/data-trade-menu-trigger[^>]*aria-keyshortcuts="T"/);
  assert.match(appSource,/label:"Cards gallery", keys:"g c"/);
});

test('prospect and staff extensions do not retain navigation keybinds and card tables use stronger labels', () => {
  const appSource = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const interfaceSource = fs.readFileSync(path.join(gui,'interface.js'),'utf8');
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.doesNotMatch(appSource,/label:"Prospects", keys:"g p"|label:"Coaching staff", keys:"g s"/);
  assert.doesNotMatch(interfaceSource,/\[data-dashboard-view="draft"\].*G P|\[data-dashboard-view="staff"\].*G S/);
  assert.match(css,/\.season-minutes-head,[\s\S]*?\.assets-block-head\s*\)\s*\{\s*border-bottom:1px solid var\(--season-line\);\s*color:var\(--season-text\);\s*font-weight:var\(--gm-weight-semibold\);/);
  assert.match(css,/\.card-board-body :is\(table th,\.staff-workspace \.data-table th\)\s*\{\s*border-bottom:1px solid var\(--season-line\);\s*color:var\(--season-text\);\s*font-weight:var\(--gm-weight-semibold\);/);
});

test('window titles replace only redundant headings, preserving informative headers', () => {
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const start = source.indexOf('const redundantHeader =');
  const end = source.indexOf('createWindowFrame(id, {card, title, assets});', start);
  assert.ok(start >= 0 && end > start);
  const code = source.slice(start,end);
  for (const id of ['signals','morale','factors','standings','offense','defense','award-mvp','award-dpoy','award-roty','opponent','efficiency','minutes']) {
    const removed = [];
    const classes = [];
    const card = {width:300,height:200,querySelector:selector=>({remove:()=>removed.push(selector)}),classList:{add:name=>classes.push(name)}};
    const scope = {id,card};
    vm.createContext(scope);
    vm.runInContext(code,scope);
    const preserve = id === 'opponent';
    assert.equal(removed.length,preserve ? 0 : 1,id);
    assert.equal(classes.length,preserve ? 0 : 1,id);
    assert.equal(card.width,300);
    assert.equal(card.height,200);
  }
});

test('new mandatory windows center in the scrolled viewport and stay put on refresh', () => {
  const layout = {required:{width:900,height:300,x:16,y:1800},ordinary:{x:8,y:20}};
  const cards = [{id:'required',required:true},{id:'ordinary',required:false}];
  const viewport = {scrollLeft:100,scrollTop:200,clientWidth:1200,clientHeight:700};
  centerNewRequiredWindows(layout,cards,{},true,viewport);
  assert.equal(layout.required.x,250);
  assert.equal(layout.required.y,386); // round 6: 28px title bar
  assert.equal(layout.required.positioned,true);
  assert.deepEqual(layout.ordinary,{x:8,y:20});
  layout.required.x=320;
  layout.required.y=440;
  centerNewRequiredWindows(layout,cards,{phaseCards:['required']},false,viewport);
  assert.equal(layout.required.x,320);
  assert.equal(layout.required.y,440);
});

test('oversized mandatory windows start at the visible edge without resizing', () => {
  const layout = {required:{width:966,height:900}};
  centerNewRequiredWindows(layout,[{id:'required',required:true}],{},true,{scrollLeft:0,scrollTop:150,clientWidth:390,clientHeight:700});
  assert.equal(layout.required.x,0);
  assert.equal(layout.required.y,150);
  assert.equal(layout.required.width,966);
  assert.equal(layout.required.height,900);
});

test('gallery groups cards by workflow and omits irrelevant seasonal cards', () => {
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const categories = source.slice(source.indexOf('const GALLERY_CATEGORIES ='),source.indexOf('const memory = new Map'));
  const children = () => ({items:[],append(...items){this.items.push(...items);}});
  const makeElement = tag => ({
    tag,
    dataset:{},
    attributes:{},
    children:[],
    classList:{add(){},toggle(){}},
    setAttribute(name,value){this.attributes[name]=value;},
    append(...items){this.children.push(...items);},
    querySelector(selector){
      return ['.card-board-thumb-frame','.card-board-thumbnail'].includes(selector) ? makeElement('span') : null;
    },
  });
  const scope = {
    nodes:new Map([
      ['identity',{title:'Team Identity'}],
      ['phase-draft-board',{title:'Draft Board',galleryVisible:false}],
      ['phase-free_agency-market',{title:'Free-Agent Market',galleryVisible:true}],
    ]),
    layout:{identity:{visible:true},'phase-draft-board':{visible:true,minimized:true},'phase-free_agency-market':{visible:false}},
    galleryGroupsOpen:new Map(),
    gallery:{id:'seasonCardGallery'},
    galleryList:{...children(),replaceChildren(){this.items=[];}},
    document:{createElement:makeElement},
    window:{CardVisuals:{icon:()=>'<svg></svg>',description:()=>''}}, escapeHtml:String, icon:()=>'',
  };
  vm.createContext(scope);
  vm.runInContext(categories,scope);
  vm.runInContext(source.slice(source.indexOf('const galleryIcon ='),source.indexOf('const showGallery ='))+'refreshGallery();',scope);
  const groups = scope.galleryList.items;
  assert.deepEqual(groups.map(group=>group.dataset.boardGalleryGroup),['free-agency','team']);
  assert.deepEqual(groups[0].children[1].children[0].children.map(entry=>entry.dataset.boardGalleryCard),['phase-free_agency-market']);
  assert.deepEqual(groups[1].children[1].children[0].children.map(entry=>entry.dataset.boardGalleryCard),['identity']);
  assert.equal(groups[0].children[0].attributes['aria-expanded'],'true');
  assert.equal(groups[1].children[0].attributes['aria-expanded'],'false');
  assert.deepEqual(scope.layout['phase-draft-board'],{visible:true,minimized:true});
  assert.equal(galleryCategoryFor('phase-staff_retention-decision'),'required');
  assert.equal(galleryCategoryFor('phase-playoffs-bracket'),'playoffs');
  assert.equal(galleryCategoryFor('phase-draft-order'),'draft');
  assert.equal(galleryCategoryFor('phase-free_agency-market'),'free-agency');
  assert.equal(galleryCategoryFor('phase-fantasy_draft-board'),'fantasy-draft');
  assert.equal(galleryCategoryFor('development'),'season');
  assert.equal(galleryCategoryFor('team-block'),'front-office');
});

test('gallery thumbnails use static card icons without cloning card layouts', () => {
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const code = source.slice(source.indexOf('const galleryIcon ='),source.indexOf('const refreshGallery ='));
  const scope = {
    window:{},
    document:{createElement:()=>({setAttribute(name,value){this[name]=value;}})},
  };
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.join(gui,'card-visuals.js'),'utf8'),scope);
  vm.runInContext(code,scope);
  const art = vm.runInContext('galleryIcon("phase-draft-board")',scope);
  assert.equal(art.className,'card-board-gallery-icon');
  assert.equal(art['aria-hidden'],'true');
  assert.match(art.innerHTML,/<svg\b/);
  assert.notEqual(art.innerHTML, vm.runInContext('galleryIcon("week")',scope).innerHTML);
  assert.doesNotMatch(code,/cloneNode|querySelectorAll|layout\[/);
});

const defaults = () => ({
  regular:{x:10, y:20, width:300, height:200, visible:true, minimized:false, pinned:false, z:1},
  control:{x:16, y:16, width:1200, height:60, visible:false, minimized:false, pinned:false, z:2, measured:true, positioned:false},
  board:{x:16, y:16, width:900, height:600, visible:false, minimized:false, pinned:false, z:3, measured:true, positioned:false},
});

test('phase entry opens measured cards below existing windows without moving them', () => {
  const initial = defaults();
  const layout = structuredClone(initial);
  assert.equal(enterPhase(layout, initial, {}, ['control','board'], '2027:draft'), true);
  assert.deepEqual(layout.regular, initial.regular);
  // Round 6: the title bar is 28px (was 24), so each window below another sits 4px lower.
  assert.equal(layout.control.y, 260);
  assert.equal(layout.board.y, 360);
  assert.equal(layout.board.width, 900);
  assert.equal(layout.board.height, 600);
  assert.equal(layout.board.visible, true);
});

test('same-phase refresh preserves closed, minimized, pinned and moved windows', () => {
  const initial = defaults();
  const layout = structuredClone(initial);
  Object.assign(layout.control, {x:180,y:900,minimized:true,pinned:true,positioned:true});
  Object.assign(layout.board, {visible:false,positioned:true});
  const saved = {version:1,cards:layout,phaseContext:'2027:draft',phaseCards:['control','board']};
  const restored = restoreLayout(JSON.stringify(saved), initial);
  enterPhase(restored, initial, saved, ['control','board'], '2027:draft');
  assert.equal(restored.board.visible, false);
  assert.equal(restored.control.x, 180);
  assert.equal(restored.control.y, 900);
  assert.equal(restored.control.minimized, true);
  assert.equal(restored.control.pinned, true);
});

test('new draft presentation sections open once and next season reopens saved cards', () => {
  const initial = defaults();
  const layout = structuredClone(initial);
  const saved = {cards:{control:{...layout.control,positioned:true}},phaseContext:'2027:draft',phaseCards:['control']};
  enterPhase(layout, initial, saved, ['control','board'], '2027:draft');
  assert.equal(layout.board.visible, true);
  layout.board.visible = false;
  layout.board.positioned = true;
  const next = {cards:structuredClone(layout),phaseContext:'2027:draft',phaseCards:['control','board']};
  enterPhase(layout, initial, next, ['control','board'], '2028:draft');
  assert.equal(layout.board.visible, true);
  assert.equal(layout.board.y, next.cards.board.y);
});

const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
function loadPlayerRowMarkup(scope) {
  const start = app.indexOf('function playerHeadshotMarkup(');
  const end = app.indexOf('function injuryGamesRemaining(', start);
  assert.ok(start >= 0 && end > start);
  vm.runInContext(app.slice(start, end), scope);
}

test('minutes table keeps identity, minutes and fatigue without ratings or box stats', () => {
  const calls = {mpg:0,stats:0};
  const scope = {
    state:{rotationDraft:{p1:24},rotationLockedPlayerIds:new Set()},
    developmentPlayerCandidates:()=>{throw new Error('Development should render in its own card');}, seasonPanelHeader:()=>'', isPlayerInjured:()=>false,
    injuryGamesRemaining:()=>null, compactPos:value=>value, heightFromRow:()=>"6'5\"",
    rating:()=>80, playerRatingBarStyle:()=>'', PLAYER_ROLE_CHIPS:{}, seasonMiniRating:()=>'<span></span>', escapeHtml:value=>String(value),
    escapeAttr:value=>String(value), clampNumber:(value,min,max)=>Math.min(max,Math.max(min,value)),
    seasonFatigueCell:()=>'<span class="season-fatigue low"></span>', signedNumber:value=>String(value),
    mpgFromRow:()=>{calls.mpg++;throw new Error('MPG should not render in this table');},
    statNumber:()=>{calls.stats++;throw new Error('Box stats should not render in this table');},
  };
  vm.createContext(scope);
  loadHouseTables(scope);
  vm.runInContext(app.slice(app.indexOf('function ensureRotationDraft('),app.indexOf('\nfunction autofillRotationDraft')),scope);
  loadPlayerRowMarkup(scope);
  vm.runInContext(app.slice(app.indexOf('function seasonMinutesCard('),app.indexOf('\nfunction seasonMiniRating')),scope);
  const markup = scope.seasonMinutesCard([{id:'p1',name:'Test Player',age:25,position:'PG'}],true);
  assert.match(markup, /class="season-minute-position"[^>]*>PG</);
  assert.match(markup, /class="season-minute-height">6'5"</);
  for (const field of ['Player','Pos','Height','Minutes','Fatigue']) assert.match(markup, new RegExp(`data-house-sort="[a-z]+"[^>]*>${field}<`));
  assert.ok(!markup.includes('Development'));
  for (const field of ['Age','OVR','OFF','DEF','MPG','PTS','REB','AST']) assert.ok(!markup.includes(`<span>${field}</span>`));
  assert.match(markup,/class="season-minute-control"/);
  assert.match(markup,/class="season-fatigue /);
  assert.deepEqual(calls,{mpg:0,stats:0});
});
test('injured minutes rows keep black player text and show a red cross with the return count', () => {
  const scope = {
    state:{rotationDraft:{},rotationLockedPlayerIds:new Set()},
    seasonPanelHeader:()=>'', isPlayerInjured:()=>true, injuryGamesRemaining:()=>4, heightFromRow:()=>'',
    escapeHtml:value=>String(value), escapeAttr:value=>String(value),
    clampNumber:(value,min,max)=>Math.min(max,Math.max(min,value)),
    seasonFatigueCell:()=>'<span class="season-fatigue low"></span>',
    rating:()=>80, playerRatingBarStyle:()=>'', PLAYER_ROLE_CHIPS:{},
  };
  vm.createContext(scope);
  loadHouseTables(scope);
  vm.runInContext(app.slice(app.indexOf('function ensureRotationDraft('),app.indexOf('\nfunction autofillRotationDraft')),scope);
  loadPlayerRowMarkup(scope);
  vm.runInContext(app.slice(app.indexOf('function seasonMinutesCard('),app.indexOf('\nfunction seasonMiniRating')),scope);
  const markup = scope.seasonMinutesCard([{id:'p1',name:'Injured Player',health:{}}],true);
  assert.match(markup,/<span class="season-minute-player-name">Injured Player<\/span>/);
  assert.match(markup,/<span class="season-injury-status" role="img" aria-label="Injured, 4 games remaining" title="Injured, 4 games remaining"><span aria-hidden="true">✚<\/span><span>4<\/span><\/span>/);
  const css = fs.readFileSync(path.join(gui,'styles.css'),'utf8');
  assert.match(css,/\.season-minute-row\.injured > button \{ color: var\(--season-text\) !important; \}/);
  assert.doesNotMatch(css,/\.season-minute-row\.injured,\s*\.season-minute-row\.injured \*/);
});

test('next opponent injury list shows remaining games without repeating injured status', () => {
  const source = app.slice(app.indexOf('function seasonOpponentCard('),app.indexOf('\nfunction seasonPreviousGamesCard('));
  const scope = {
    state:{data:{dashboardOpponent:{team:'NYK',record:{wins:3,losses:4},last_games:[],team_identity:{ranks:{}},rotation:[{
      name:'Test Player',minutes_projection:30,health:{status:'injured',label:'injured ~4g',days_left:10},
    }]}}},
    teamLabel:value=>typeof value==='string'?value:value?.abbrev||'NYK', seasonGameOpponent:()=>'NYK', teamLogoSrc:()=>'',
    clampNumber:value=>value, performanceBarStyle:()=>'', playerRatingBarStyle: ()=>'', ratingInkColor: ()=>'#333', escapeAttr:value=>String(value), escapeHtml:value=>String(value),
    formatDashboardShortDate:value=>value, isPlayerInjured:health=>health?.status==='injured', injuryGamesRemaining:()=>4,
    rating:()=>80, seasonMiniRating:()=>'<span>80</span>', statNumber:()=>0, playerOverallToday:()=>null, playerRatingDrop:()=>({drop:0,out:false}),
  };
  vm.createContext(scope);
  loadHouseTables(scope, {block:false});
  loadPlayerRowMarkup(scope);
  vm.runInContext(source,scope);
  const markup = scope.seasonOpponentCard({next_games:[{date:'2030-11-05',opponent_team_id:'NYK',is_home:false}]},'BOS');
  assert.match(markup,/Current injuries:<\/span>[\s\S]*?data-injury-ticker-text>Test Player — 4 G<\/span>/);
  assert.doesNotMatch(markup,/Test Player — injured/);
  const fidelity = fs.readFileSync(path.join(gui,'paper-fidelity.css'),'utf8');
  assert.match(fidelity,/season-efficiency-legend span\.negative \{ color:#b44f48; \}[\s\S]*?season-opponent-injuries > span \{ color:#b44f48; \}/);
});
test('player development stays as a separate clipboard card without team growth controls', () => {
  const scope = {
    developmentPlayerCandidates:()=>[{player_id:'p1',name:'Test Player',points:[{label:'Start',value:70},{label:'10',value:72},{label:'11',value:73.5}]}],
    developmentMovementScore:player=>player.points.at(-1).value,
    escapeAttr:value=>String(value), escapeHtml:value=>String(value),
    clampNumber:(value,min,max)=>Math.min(max,Math.max(min,value)),
    signedNumber:value=>`${value>=0?'+':''}${Number(value).toFixed(1)}`,
    state:{data:{dashboardTrends:{development:{latest_month:'2030-11'}}}},
  };
  vm.createContext(scope);
  loadHouseTables(scope);
  loadPlayerRowMarkup(scope);
  vm.runInContext(app.slice(app.indexOf('function playerUpsideColor('),app.indexOf('function gameArtwork(')),scope);
  vm.runInContext(app.slice(app.indexOf('function seasonDevelopmentCard('),app.indexOf('\nfunction seasonLeagueWire')),scope);
  const markup = scope.seasonDevelopmentCard([{id:'p1'}]);
  assert.doesNotMatch(markup,/data-team-development|Team growth|season-panel-header/);
  assert.match(markup,/<span class="season-development-name">Test Player<\/span>/);
  assert.match(markup,/class="season-development-row"/);
  assert.match(markup,/aria-label="Test Player, age —: growth runway 0\.0 of 5, rating change this season \+3\.5, Nov \+1\.5"/);
  assert.match(markup,/class="season-development-period">Season<\/span>/);
  assert.match(markup,/class="season-development-period">Nov<\/span>/);
  assert.match(markup,/class="season-development-diverging"/);
  assert.match(markup,/class="positive">\+3\.5<\/strong>/);
  assert.match(markup,/class="positive">\+1\.5<\/strong>/);
  assert.equal((markup.match(/class="season-development-metric"/g)||[]).length,2);
  assert.doesNotMatch(markup,/season-development-spark/);
  assert.doesNotMatch(app,/openTeamDevelopmentModal|teamDevelopment|data-team-development/);
  assert.doesNotMatch(fs.readFileSync(path.join(gui,'interface.js'),'utf8'),/data-team-development|G D/);
  assert.match(app,/<section class="season-command-panel season-development-panel">\$\{seasonDevelopmentCard\(rows\)\}<\/section>/);
  assert.match(fs.readFileSync(path.join(gui,'card-board.js'),'utf8'),/\["development", "\.season-development-panel", "Player Development"\]/);
});
test('focused minutes rows retain the readable panel background', () => {
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(css,/\.season-minute-row:focus-within\s*\{\s*background:var\(--season-panel\) !important;/);
  assert.match(css,/:is\(\.season-minutes-head,\.season-minute-row\)\s*\{\s*grid-template-columns:(?:minmax\([^)]*\) ){4}minmax\([^)]*\);/);
  assert.match(css,/\.season-minutes-head > span:nth-child\(5\)\s*\{[^}]*justify-self:end;[^}]*text-align:center;/);
  assert.match(css,/\.season-fatigue\s*\{[^}]*justify-self:end;[^}]*width:100%;/);
});
test('minutes typography matches standings labels and row text', () => {
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(css,/\[data-board-window="minutes"\] \.season-minutes-head\s*\{\s*font-size:11px;/);
  assert.match(css,/\[data-board-window="minutes"\] \.season-minute-row > button,[\s\S]*?\[data-board-window="minutes"\] \.season-minute-control output\s*\{\s*font-size:11px;/);
});
test('opponent and staff card body typography matches standings rows', () => {
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(css,/\[data-board-window="opponent"\] :is\([\s\S]*?\.season-opponent-row > span,[\s\S]*?\)\s*\{\s*font-size:11px;/);
  assert.match(css,/\[data-board-window="staff"\] \.season-staff-row > span,[\s\S]*?\.season-staff-grade em\s*\{\s*font-size:11px;/);
  assert.match(css,/\[data-board-window="staff"\] \.season-staff-summary strong\s*\{[^}]*font-size:11px/);
  assert.match(css,/\[data-board-window="staff"\] \.season-staff-person strong\s*\{[^}]*font-size:11px/);
});
test('coaching staff card keeps payroll only and displays compact single-line contracts', () => {
  const source = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const cardSource = source.slice(source.indexOf('const COACH_PORTRAIT_IDS'),source.indexOf('\nfunction staffRoleLabel('));
  const scope = {
    state:{data:{}},
    staffRows:()=>[
      {id:'hc',name:'Coach One',slot:'head_coach',grade:85,aav:12000000,years:1},
      {id:'oc',name:'Coach Two',slot:'offensive_coordinator',grade:72,aav:5000000,years:3},
    ],
    staffRoleLabel:role=>role === 'head_coach' ? 'Head Coach' : 'Offensive Coordinator',
    staffGrade:row=>row.grade, staffAav:row=>row.aav, staffYears:row=>row.years,
    staffBudgetSummary:()=>({used:17000000,max:40000000}),
    staffName:row=>row.name, money:value=>`$${(value / 1000000).toFixed(1)}M`,
    escapeAttr:value=>String(value), escapeHtml:value=>String(value),
    seasonPanelHeader:title=>`<header>${title}</header>`,
    performanceBarStyle:()=>'', playerRatingBarStyle: ()=>'',
  };
  vm.createContext(scope);
  loadHouseTables(scope);
  vm.runInContext(cardSource,scope);
  const markup = scope.seasonStaffCard({});
  assert.match(markup,/STAFF PAYROLL/);
  assert.doesNotMatch(markup,/FILLED ROLES|AVERAGE GRADE|>01<|>02</);
  assert.match(markup,/<strong>\$12\.0M × 1<\/strong>/);
  assert.match(markup,/<strong>\$5\.0M × 3<\/strong>/);
  assert.doesNotMatch(markup,/<small>1 yr<\/small>|<small>3 yrs<\/small>/);
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(css,/grid-template-columns:minmax\(150px,1\.55fr\) minmax\(64px,\.7fr\) minmax\(116px,1fr\)/);
  assert.match(css,/\.season-staff-contract strong\s*\{[^}]*white-space:nowrap/s);
});
test('staff rows and coach cards share six distinct transparent coach portraits', async () => {
  const app = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const source = app.slice(app.indexOf('const COACH_PORTRAIT_IDS'),app.indexOf('\nfunction staffRoleLabel('));
  const roles = ['head_coach','offensive_coordinator','defensive_coordinator','performance_lead','development_lead','scouting_lead'];
  const rows = roles.map((slot,index)=>({
    id:`coach-${index}`,team_id:'team-test',name:`Coach ${index}`,slot,grade:70+index,
    aav:2+index,years:2,archetype:`Archetype ${index}`,morale:60+index,job_security:70+index,
    skill_traits:{scheme_balance:70+index,communication:65+index},personality_traits:{adaptability:68+index},
  }));
  let opened;
  const scope = {
    staffRoleLabel:slot=>({head_coach:'Head Coach',offensive_coordinator:'Offensive Coordinator',defensive_coordinator:'Defensive Coordinator',performance_lead:'Performance Lead',development_lead:'Development Lead',scouting_lead:'Scouting Lead'})[slot] || slot,
    staffRows:dash=>dash.staff_slots, staffGrade:row=>row.grade, staffAav:row=>row.aav,
    staffYears:row=>row.years, staffName:row=>row.name,
    staffBudgetSummary:()=>({used:27,max:40}), money:value=>`$${Number(value).toFixed(1)}M`,
    rowLabel:value=>String(value).replaceAll('_',' '), draftMetric:value=>Number.isFinite(Number(value))?Number(value).toFixed(1):'—',
    performanceBarStyle:value=>`--fill:${value}%`, playerRatingBarStyle: value=>`--fill:${value}%`, escapeAttr:value=>String(value), escapeHtml:value=>String(value),
    seasonPanelHeader:title=>`<header>${title}</header>`, showToast:()=>{}, renderModal:()=>{},
    state:{data:{dashboard:{staff_slots:rows}}},
    savePayload:()=>({}),
    action:async (name,payload) => {
      assert.equal(name,'coach_card');
      assert.equal(payload.staff_id,'coach-0');
      return {staff:rows[0]};
    },
    openPlayerCardOnClipboard:async card => {opened=card;},
  };
  vm.createContext(scope);
  loadHouseTables(scope);
  vm.runInContext(source,scope);
  const portraits = Array.from(scope.coachPortraitAssignments(rows).values());
  assert.equal(new Set(portraits).size,6);
  const markup = scope.seasonStaffCard({staff_slots:rows});
  assert.equal((markup.match(/data-dashboard-staff-card=/g)||[]).length,6);
  assert.equal((markup.match(/coach-portrait-art/g)||[]).length,6);
  await scope.dashboardCoachCard('coach-0');
  assert.equal(opened.kind,'coach');
  assert.equal(opened.key,'coach:coach-0');
  assert.match(opened.body,/Coach 0/);
  assert.match(opened.body,/Coaching Traits/);
  assert.match(opened.body,/Working Style/);
  assert.ok(opened.body.includes(`/assets/game-art/coaches/${portraits[0]}-silver.webp`));
  const portraitDir = path.join(gui,'assets/game-art/coaches');
  for (const portrait of portraits) {
    assert.ok(fs.existsSync(path.join(portraitDir,`${portrait}-silver.webp`)));
    assert.ok(fs.existsSync(path.join(portraitDir,`${portrait}-ink.webp`)));
  }
  const board = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(board,/staff: \[1\.58, 1\.12\]/);
  assert.match(board,/staff:7/);
});
test('standings typography matches the larger team-block type without scaling the card', () => {
  const css = fs.readFileSync(path.join(gui,'styles.css'),'utf8');
  const board = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(css,/\.season-standings-head \{[^}]*font-size: 10px/);
  assert.match(css,/\.season-standing-row > span \{[^}]*font-size: 11px/);
  const sizeFactors = board.slice(board.indexOf('const CARD_SIZE_FACTORS'),board.indexOf('const CARD_SIZE_REVISIONS'));
  assert.doesNotMatch(sizeFactors,/standings/);
});
test('radar shape tracks league rank and uses the full card body at standings-sized type', () => {
  const app = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const board = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  const source = app.slice(app.indexOf('function seasonIdentityRadar('),app.indexOf('\nfunction seasonStandingsCard('));
  const scope = {
    clampNumber:(value,min,max)=>Math.min(max,Math.max(min,value)),
    escapeAttr:value=>String(value), escapeHtml:value=>String(value),
  };
  vm.createContext(scope);
  vm.runInContext(source,scope);
  assert.equal(scope.seasonRadarRankScore(5,30),85);
  assert.ok(scope.seasonRadarRankScore(5,30) > scope.seasonRadarRankScore(25,30) + 60);
  const markup = scope.seasonIdentityRadar('Offense',[['Shooting','spacing']],{spacing:5},30);
  assert.match(markup,/viewBox="0 0 360 280"/);
  assert.match(markup,/dy="16">#5\/30/);
  assert.match(markup,/aria-label="Offense league rank profile"/);
  assert.match(markup,/#5\/30/);
  assert.match(markup,/class="season-radar-rank"/);
  assert.doesNotMatch(markup,/season-radar-healthy|season-radar-legend/);
  assert.doesNotMatch(board,/card\.matches\("\.season-radar-card"\) \? " season-radars-stack"/);
  assert.doesNotMatch(board,/id === "offense" \|\| id === "defense" \? " season-radars-stack"/);
  assert.match(css,/\[data-board-window="offense"\] \.season-radar-card text,[\s\S]*?\[data-board-window="defense"\] \.season-radar-card text \{ font-size:13\.5px !important; \}/);
});
test('standings expansion toggles the existing window size and restores its compact dimensions', () => {
  const item = {width:360,height:260,scale:1.1,expanded:false};
  assert.equal(toggleWindowExpansion(item,'standings'),true);
  assert.deepEqual([item.width,item.height,item.scale,item.expanded],[720,390,1.1,true]);
  const defaults = defaultLayout([{id:'standings',x:0,y:0,width:360,height:260}]);
  const restored = restoreLayout(JSON.stringify({version:1,cards:{standings:item}}),defaults).standings;
  assert.equal(restored.expanded,true);
  assert.equal(JSON.stringify(restored.compactSize),JSON.stringify({width:360,height:260,scale:1.1}));
  assert.equal(toggleWindowExpansion(restored,'standings'),false);
  assert.deepEqual([restored.width,restored.height,restored.scale,restored.expanded],[360,260,1.1,false]);
  assert.equal(restored.compactSize,undefined);
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(source,/EXPANDABLE_CARDS = new Set\(\[[^\]\n]*"standings"/);
  assert.match(source,/data-board-expand="\$\{safeId\}"/);
});
test('prospects and staff expand inside their existing cards, with wider prospect fields', () => {
  const board = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  const appSource = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const desktop = fs.readFileSync(path.join(gui,'assets-desktop.js'),'utf8');
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(board,/prospects:\s*\[1\.92, 1\.22\]/);
  assert.match(board,/offense:\s*\[1\.4, 1\.55\]/);
  for (const [id,width,height] of [['prospects',1000,650],['staff',496,600]]) {
    const item = {width:400,height:300,scale:1};
    assert.equal(toggleWindowExpansion(item,id),true);
    assert.deepEqual([item.width,item.height],[width,height]);
    assert.equal(toggleWindowExpansion(item,id),false);
    assert.deepEqual([item.width,item.height],[400,300]);
  }
  assert.match(desktop,/setProspectsCardExpanded\(expanded,card\)/);
  assert.match(desktop,/setStaffCardExpanded\(expanded,card\)/);
  assert.match(appSource,/SEASON_PROSPECT_COLUMNS = \[[\s\S]*?\["from", \[\["from", "From"/);
  assert.match(appSource,/season-prospects-expanded-body[\s\S]*?seasonProspectsCard\(\{rows, expanded:true\}\)/);
  assert.doesNotMatch(desktop,/clipboardWindowCards\(\)|loadClipboardWindow/);
  assert.doesNotMatch(board,/data-dashboard-view="draft"|data-dashboard-view="staff"/);
  assert.match(css,/\.season-prospect-list\s*\{[^}]*height:100%;[^}]*overflow:hidden;/);
  assert.match(css,/\.season-prospect-list-expanded\s*\{[^}]*overflow:auto;/);
  assert.match(css,/\.season-prospect-table thead th\s*\{[^}]*position:sticky;/);
  assert.match(css,/season-staff-expanded/);
});
test('Calendar opens compact and unmarked legacy weekly layouts migrate once', () => {
  const defaults = defaultLayout([{id:'week',x:24,y:40,width:360,height:150}]);
  assert.equal(defaults.week.expanded,false);
  assert.deepEqual([defaults.week.width,defaults.week.height],[360,150]);
  assert.equal(defaults.week.compactSize,undefined);

  const legacy = {version:1,cards:{week:{x:24,y:40,width:390,height:170,scale:1}}};
  const restored = migrateDefaultCalendar(restoreLayout(JSON.stringify(legacy),defaults),legacy);
  assert.equal(restored.week.expanded,true);
  assert.deepEqual([restored.week.width,restored.week.height],[960,560]);
  assert.deepEqual(JSON.stringify(restored.week.compactSize),JSON.stringify({width:390,height:170,scale:1}));
  assert.ok(restored.week.z > defaults.week.z);
  const migrated = {version:1,cards:restored};
  const migratedAgain = migrateDefaultCalendar(restoreLayout(JSON.stringify(migrated),defaults),migrated);
  assert.deepEqual(migratedAgain.week,restored.week);
  assert.equal(toggleWindowExpansion(restored.week,'week'),false);
  assert.deepEqual([restored.week.width,restored.week.height],[390,170]);
  const compact = {version:1,cards:restored};
  assert.deepEqual(migrateDefaultCalendar(restoreLayout(JSON.stringify(compact),defaults),compact).week,restored.week);

  const appSource = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const boardSource = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(boardSource,/\["week", "\.season-week-panel", "Calendar"\]/);
  assert.doesNotMatch(boardSource,/\["calendar", "Full Calendar"\]/);
  assert.match(appSource,/renderCalendar\(panel, \{team:viewedTeam,dataKey:"dashboardCalendar"\}\)/);
  assert.match(appSource,/window\.CardBoard\?\.open\("week"\)/);
});
test('expanding Calendar fetches a full month when the snapshot only has a week', async () => {
  const source = app.slice(app.indexOf('async function setWeekCardExpanded('),app.indexOf('\nfunction seasonGameOpponent('));
  let fetched = 0;
  const panel = {
    isConnected:true,
    expanded:false,
    classList:{toggle(_name,value){panel.expanded=value;},contains(name){return name==='is-expanded'&&panel.expanded;}},
  };
  const state = {calendarMonth:'2030-11',home:{save:{current_date:'2030-11-12'}},dashboardTeam:'WAS',data:{dashboard:{team:'WAS'},dashboardCalendar:{from_date:'2030-11-10',through_date:'2030-11-16',games:[]}}};
  const scope = {
    state,
    els:{content:{querySelector:()=>panel}},
    teamLabel:value=>value,userTeam:()=>'WAS',
    async loadDashboardCalendar(){fetched++;state.data.dashboardCalendar={from_date:'2030-11-01',through_date:'2030-11-30',games:[]};},
    renderCalendar(target,options){target.renderedDataKey=options.dataKey;},
    GameInterface:{enhance(){}},seasonWeekCard:()=>'',showToast:()=>{},monthEndDate:first=>first.slice(0,7)+'-30',
  };
  vm.createContext(scope);
  vm.runInContext(source,scope);
  assert.equal(await scope.setWeekCardExpanded(true,panel),true);
  assert.equal(fetched,1);
  assert.equal(panel.renderedDataKey,'dashboardCalendar');
  await scope.setWeekCardExpanded(true,panel);
  assert.equal(fetched,1);
});
test('expanded standings show West left and East right with fifteen teams each', () => {
  const rows = ['East','West'].flatMap(conference => Array.from({length:15},(_unused,index) => ({
    team:{abbrev:`${conference[0]}${index}`,conference}, wins:15-index, losses:index, win_pct:(15-index)/15,
  })));
  const app = fs.readFileSync(path.join(gui,'app.js'),'utf8');
  const source = app.slice(app.indexOf('function seasonStandingsCard('),app.indexOf('\nfunction setStandingsCardExpanded'));
  const scope = {
    state:{data:{dashboardStandings:{standings:rows}}},
    standingsRows:data=>data?.standings||[], teamLabel:team=>team?.abbrev||'E0', teamLogoSrc:()=>'',
    escapeAttr:value=>String(value), escapeHtml:value=>String(value), winPct:value=>String(value),
  };
  vm.createContext(scope);
  loadHouseTables(scope);
  vm.runInContext(source,scope);
  const compact = scope.seasonStandingsCard('E0');
  const expanded = scope.seasonStandingsCard('E0',true);
  assert.equal((compact.match(/class="season-standing-row/g)||[]).length,10);
  assert.doesNotMatch(compact,/E10|W0/);
  assert.equal((expanded.match(/class="season-standing-row/g)||[]).length,30);
  assert.ok(expanded.indexOf('Western Conference') < expanded.indexOf('Eastern Conference'));
  assert.match(expanded,/E14/);
  assert.match(expanded,/W14/);
  assert.match(expanded,/--standings-count:15/);
});
test('top menu buttons keep black labels through hover and focus styling', () => {
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  const topButtonStyles = css.slice(css.indexOf('body .has-card-board .season-command-actions > button,'),css.indexOf('body .has-card-board .card-board-menu > button { justify-content'));
  assert.match(topButtonStyles,/color:#111 !important;/);
  assert.match(topButtonStyles,/card-board-window\[data-board-window="week"\] \.clipboard-calendar-head button/);
  assert.match(css,/\.card-board-window\[data-board-window="week"\] \.clipboard-calendar-head button:hover:not\(:disabled\)/);
  assert.match(css,/\.card-board-window\[data-board-window="week"\] \.clipboard-calendar-head button:active:not\(:disabled\)/);
  assert.match(topButtonStyles,/\.card-board-menu > button/);
  assert.match(topButtonStyles,/\.card-board-gallery-toggle/);
});
test('team identity heatmaps size to the court aspect ratio with content-tight rows', () => {
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(css,/\[data-board-window="identity"\] \.spatial-heatmap\s*\{\s*grid-template-rows:28px auto 42px;\s*align-content:start;/);
  assert.match(css,/\[data-board-window="identity"\] \.spatial-court\s*\{\s*height:auto;\s*aspect-ratio:500 \/ 470;/);
});
test('heatmap hover targets summarize whole regions and emphasize only their hexes', () => {
  const scope = { escapeHtml:value=>String(value), escapeAttr:value=>String(value) };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function spatialEfficiencyColor('),app.indexOf('\nfunction spatialHeatmapMarkup(')),scope);
  const profile = {shot_chart:{regions:[
    {id:1,label:'Paint',fg_pct:41.1,league_fg_pct:40.3,delta_pp:0.8,suppression_delta_pp:0.5},
    {id:2,label:'Short left',fg_pct:39,league_fg_pct:38,delta_pp:1,suppression_delta_pp:0.2},
  ],cells:[
    [52.5,250,1,0.2,0.1,0.1],[74.15,250,1,0.3,0.2,0.2],[100,130,2,0.1,0.1,0.1],
  ]}};
  const regions = scope.spatialHeatmapRegions(profile,'offense');
  // Both paint cells pool into one coarse hex; the short-range cell is below the league's average hex volume.
  assert.equal((regions.match(/class="spatial-court-hex"/g)||[]).length,1);
  assert.equal((regions.match(/class="spatial-court-hex-region"/g)||[]).length,2);
  assert.equal((regions.match(/class="spatial-region-hit"/g)||[]).length,2);
  assert.equal((regions.match(/class="spatial-region-fill"/g)||[]).length,2);
  assert.match(regions,/Paint: 83\.3% of shots \(league 75\.0%\) · Projected FG 41\.1%, league 40\.3% · FG vs league: \+0\.8 pts \(typical player \+2\.9\)/);
  assert.doesNotMatch(regions,/spatial-region-outline/);
  assert.match(regions,/<g class="spatial-region-fills">[\s\S]+?<\/g><g class="spatial-court-hex-region" data-region="1">\s*<polygon[^>]+data-region="1"[\s\S]+?<path class="spatial-region-hit"/);
  const css = fs.readFileSync(path.join(gui,'styles.css'),'utf8');
  assert.match(css,/\.spatial-court-hex \{ pointer-events: none;/);
  assert.match(css,/\.spatial-region-hit \{[^}]*pointer-events: all;/);
  assert.match(css,/\.spatial-court:has\(\.spatial-region-hit:is\(:hover,:focus-visible\)\)[\s\S]*?opacity: \.16;/);
  assert.match(css,/\.spatial-court-hex-region:has\(\.spatial-region-hit:is\(:hover,:focus-visible\)\) \{ filter: brightness\(1\.12\); \}/);
  const heat = fs.readFileSync(path.join(gui,'heatmaps.css'),'utf8');
  assert.match(heat,/\.spatial-region-hit:is\(:hover,:focus-visible\) \{ stroke:#24323c;/);
  // Selected view tabs are a light tint with an underline, never black with white text.
  assert.match(heat,/\.spatial-court-tab\[aria-pressed="true"\],[\s\S]*?background:#e0eaf3;[\s\S]*?border-bottom-color:#2f5f86;/);
  assert.doesNotMatch(heat,/spatial-court-tab[^{]*\{[^}]*color:#fff/);
});
test('four factors draw a league box plot with our team as a dot coloured by league rank', () => {
  const scope = { clampNumber:(v,a,b)=>Math.min(b,Math.max(a,v)), escapeHtml:String, escapeAttr:String };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('const FOUR_FACTOR_MEANINGS'),app.indexOf('// Player rating bars (OVR/OFF/DEF)')),scope);
  const row = scope.seasonFactorBar({key:'tov',label:'TOV%',value:14.2,league_average:13.1,rank:28,team_count:30,score:10,
    league_spread:{min:11.2,q1:12.4,median:13.0,q3:13.8,max:15.6}});
  for (const part of ['whisker','iqr','median']) assert.match(row,new RegExp(`class="season-factor-${part}"`));
  assert.match(row,/class="season-factor-dot" style="left:/);
  assert.match(row,/--factor-color:#/);
  assert.match(row,/<strong class="season-factor-value">14\.2<\/strong>/);
  assert.match(row,/middle half 12\.4–13\.8, median 13\.0/);
  // Without a league spread (older data) the row still shows the average tick and the dot.
  const plain = scope.seasonFactorBar({key:'efg',label:'eFG%',value:55,league_average:53,score:80});
  assert.doesNotMatch(plain,/season-factor-iqr|NaN/);
  assert.match(plain,/season-factor-median[\s\S]*season-factor-dot/);
});
test('weekly efficiency labels weeks, not dates, and puts small y labels on round values', () => {
  const points = Array.from({length:12},(_,i)=>{ const d=new Date(Date.UTC(2026,9,19)+i*7*86400000).toISOString().slice(0,10); return {date:d,label:d.slice(5),offense:112+9*Math.sin(i/2),defense:110-6*Math.cos(i/3)}; });
  const scope = { state:{data:{dashboardTrends:{efficiency:{points,league_average:112,events:[]}}}}, clampNumber:(v,a,b)=>Math.min(b,Math.max(a,v)), escapeHtml:String, escapeAttr:String, signedNumber:v=>String(v), seasonPanelHeader:t=>t };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function seasonEfficiencyCard('),app.indexOf('function efficiencyEventDetail(')),scope);
  const svg = scope.seasonEfficiencyCard({},420,220,true);
  assert.deepEqual([...svg.matchAll(/>Week (\d+)</g)].map(m=>Number(m[1])),[1,5,10,15,20,25]);
  assert.doesNotMatch(svg,/>10-19<|rotate\(/);
  assert.deepEqual([...svg.matchAll(/class="axis-label y-label"[^>]*>(-?\d+)</g)].map(m=>Number(m[1])),[40,20,0,-20,-40]);
  assert.match(svg,/<title>Week 3 OFF vs league/);
});
test('payroll segment hover text includes the contract amount and escaped player name', () => {
  const scope = {
    clampNumber:(value,min,max)=>Math.min(max,Math.max(min,value)),
    escapeAttr:value=>String(value).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),
    escapeHtml:value=>String(value),
    money:value=>`$${value}M`,
    shortSeasonLabel:value=>String(value),
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function salaryHorizonChart('),app.indexOf('\nfunction summaryPlayerNameCell')),scope);
  const markup = scope.salaryHorizonChart({
    seasons:['2030'],
    rows:[{id:'p1',name:'A&B Player',salary_by_year:{2030:20}}],
    capByYear:{2030:{salary_total_millions:25}},
  });
  assert.match(markup,/title="\$20M · A&amp;B Player"/);
  assert.match(markup,/title="Other payroll: \$5M"/);
});
const calendar = {state:{teams:[]},teamLabel:value=>value,teamLogoSrc:team=>`/logos/${team}.svg`,escapeHtml:value=>String(value),escapeAttr:value=>String(value),resultForTeam:()=>'',tradeDeadlineDate:()=> '2027-02-05'};
vm.createContext(calendar);
for (const [start,end] of [
  ['function clipboardCalendarDay(', 'function renderSocial('],
  ['function monthCalendarCells(', 'function wireTradeAssetControls('],
  ['function scoreLine(', 'function rating('],
  ['function seasonGameOpponent(', 'function dashboardProspectYear('],
]) vm.runInContext(app.slice(app.indexOf(start),app.indexOf(end)),calendar);

test('calendar places dates on Monday-first weeks, including leap February', () => {
  const january = calendar.monthCalendarCells('2027-01');
  assert.equal(january[4].date,'2027-01-01');
  assert.equal(january.length,35);
  assert.equal(calendar.monthCalendarCells('2028-02').filter(cell=>cell.date).length,29);
});

test('calendar completed game cells show opponent logo, own-team score and box-score target', () => {
  const game = {game_id:'done',date:'2027-01-04',home_team:'MIA',away_team:'NYK',home_score:112,away_score:100};
  const markup = calendar.clipboardCalendarDay({date:game.date},[game],'2027-01-06','MIA');
  assert.match(markup,/data-box-score="done"/);
  assert.match(markup,/\/logos\/NYK.svg/);
  assert.match(markup,/W 112–100/);
  assert.match(markup,/past/);
  assert.match(markup,/vs NYK/);
});

test('future calendar games show logos without invented scores or box-score buttons', () => {
  const game = {game_id:'future',date:'2027-01-07',home_team:'BOS',away_team:'MIA',home_score:null,away_score:null};
  const markup = calendar.clipboardCalendarDay({date:game.date},[game],'2027-01-06','MIA');
  assert.match(markup,/\/logos\/BOS.svg/);
  assert.match(markup,/@ BOS/);
  assert.doesNotMatch(markup,/Scheduled/);
  assert.doesNotMatch(markup,/data-box-score|0–0|completed/);
  const offDay = calendar.clipboardCalendarDay({date:'2027-01-06'},[game],'2027-01-06','MIA');
  assert.match(offDay,/today/);
  assert.doesNotMatch(offDay,/<img/);
});

test('national TV games carry a small TV marker; other games do not', () => {
  const game = {game_id:'tv',date:'2027-01-07',home_team:'BOS',away_team:'MIA',national_tv:true};
  assert.match(calendar.clipboardCalendarDay({date:game.date},[game],'2027-01-06','MIA'),/class="national-tv-marker"[^>]*>TV</);
  assert.doesNotMatch(calendar.clipboardCalendarDay({date:game.date},[{...game,national_tv:false}],'2027-01-06','MIA'),/national-tv-marker/);
});

const actions = {state:{home:{save:{legal_actions:[]}},data:{dashboard:{legal_actions:['trades']}}},dashboardPhaseKind:()=>''};
vm.createContext(actions);
vm.runInContext(app.slice(app.indexOf('function isClipboardPhase('),app.indexOf('async function openClipboardWindow(')),actions);

test('backend legal actions override stale dashboard permissions', () => {
  const locks = actions.clipboardLockedCards();
  assert.equal(locks['trade-builder'], true);
  assert.equal(locks['team-block'], true);
  actions.state.home.save.legal_actions = ['draft_trades','advance'];
  assert.equal(actions.clipboardLockedCards()['trade-builder'], undefined);
});

test('fantasy draft locks ordinary simulation and rotation but remains a clipboard phase', () => {
  actions.dashboardPhaseKind = () => 'fantasy_draft';
  const locks = actions.clipboardLockedCards();
  assert.equal(locks.week, true);
  assert.equal(locks.minutes, true);
  for (const phase of ['fantasy_draft','draft','playoffs','free_agency']) assert.equal(actions.isClipboardPhase(phase), true);
  assert.equal(actions.isClipboardPhase('staff_retention'), true);
  assert.equal(actions.isClipboardPhase('cutdown'), true);
});

test('required decisions override saved closure and minimization without moving windows', () => {
  const layout = defaults();
  Object.assign(layout.control, {x:180,y:900,visible:false,minimized:true,pinned:true});
  enforceRequiredWindows(layout, [{id:'control',required:true},{id:'board',required:false}]);
  assert.equal(layout.control.visible, true);
  assert.equal(layout.control.minimized, false);
  assert.equal(layout.control.x, 180);
  assert.equal(layout.control.y, 900);
  assert.equal(layout.control.pinned, true);
  assert.equal(layout.board.visible, false);
  enforceRequiredWindows(layout, [{id:'control',required:false}]);
  assert.equal(layout.control.visible, true);
});

test('completed mandatory windows close, persist closed and reopen for the next requirement', () => {
  const initial = defaults();
  const layout = structuredClone(initial);
  Object.assign(layout.control,{visible:true,x:240,y:350,pinned:true,positioned:true});
  layout.regular.visible = true;
  enforceRequiredWindows(layout,[{id:'control',mandatory:true,required:false}]);
  assert.equal(layout.control.visible,false);
  assert.equal(layout.regular.visible,true);
  const restored = restoreLayout(JSON.stringify({version:1,cards:layout}),initial);
  enforceRequiredWindows(restored,[{id:'control',mandatory:true,required:false}]);
  assert.equal(restored.control.visible,false);
  assert.equal(restored.control.x,240);
  assert.equal(restored.control.y,350);
  assert.equal(restored.control.pinned,true);
  enforceRequiredWindows(restored,[{id:'control',mandatory:true,required:true}]);
  assert.equal(restored.control.visible,true);
  assert.equal(restored.control.minimized,false);
});

test('staff decisions precede cutdown and seasonal progression until cleared', () => {
  const scope = {state:{home:{save:{phase:'free_agency',pending_counts:{staff:1,cutdowns:1}}}}};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function requiredClipboardDecision('),app.indexOf('function syncNavActive(')),scope);
  assert.equal(scope.dashboardPhaseKind(), 'staff_retention');
  scope.state.home.save.pending_counts.staff = 0;
  assert.equal(scope.dashboardPhaseKind(), 'cutdown');
  scope.state.home.save.pending_counts.cutdowns = 0;
  assert.equal(scope.dashboardPhaseKind(), 'free_agency');
});

test('underlying progression actions are blocked before transport, not just through buttons', async () => {
  let calls = 0;
  let reveals = 0;
  const scope = {
    state:{busyDepth:0,hydrating:false,multiplayer:{}},
    requiredClipboardDecision:()=> 'cutdown',
    revealRequiredClipboardDecision:()=>{reveals += 1;},
    setBusy:()=>{},
    apiHeaders:async()=>({'Content-Type':'application/json','X-NBA-GM-Token':'unit-session'}),
    fetch:async()=>{calls += 1;return {ok:true,json:async()=>({result:{status:'ok'}})};},
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('async function action('),app.indexOf('async function multiplayerRequest(')),scope);
  const progression = ['advance_save','advance_free_agency','advance_re_signing','simulate_playoff_round','draft_sim_all','fantasy_draft_sim_one','draft_apply_current','draft_reveal_lottery','fantasy_draft_pick'];
  for (const name of progression) {
    await assert.rejects(scope.action(name), /required clipboard decision/);
  }
  assert.equal(calls, 0);
  assert.equal(reveals, progression.length);
  await scope.action('roster_cutdown');
  await scope.action('waive_player');
  await scope.action('resolve_staff_retention');
  assert.equal(calls, 3);
  scope.requiredClipboardDecision = ()=>'';
  await scope.action('advance_save');
  assert.equal(calls, 4);
});

test('shortcut lookup reaches closed controls but skips phase-locked controls', () => {
  const banned = {disabled:false,closest:selector=>selector === '.is-phase-locked' ? {} : null};
  const closed = {disabled:false,closest:()=>null};
  const scope = {querySelectorAll:()=>[banned,closed]};
  const ui = {document:{querySelector:()=>null,getElementById:()=>scope}};
  vm.createContext(ui);
  vm.runInContext(fs.readFileSync(path.join(gui,'interface.js'),'utf8'),ui);
  const find = vm.runInContext('GameInterface.findControl',ui);
  assert.equal(find('[data-playoff-sim]',{includeHidden:true}),closed);
  closed.disabled = true;
  assert.equal(find('[data-playoff-sim]',{includeHidden:true}),undefined);
});

test('card bounds keep the full window inside the 130 percent canvas', () => {
  const canvasWidth = 1300;
  const canvasHeight = 1040;
  const card = {x:5000,y:600,width:1600,height:1200,scale:1,minScale:.7};
  constrainCardBounds(card,canvasWidth,canvasHeight,12,24);
  assert.ok(card.x >= 0 && card.y >= 0);
  assert.ok(card.x + card.width * card.scale + 12 <= canvasWidth);
  assert.ok(card.y + 24 + card.height * card.scale + 12 <= canvasHeight);
  assert.equal(card.width,1600);
  assert.equal(card.height,1200);
  assert.ok(card.scale < 1);

  const minimum = {x:0,y:0,width:600,height:400,scale:.1,minScale:.75};
  constrainCardBounds(minimum,canvasWidth,canvasHeight,12,24);
  assert.equal(minimum.scale,.75);
  assert.equal(minimum.width,600);
  assert.equal(minimum.height,400);
});

test('snap packs visible cards while preserving their sizes and minimized states', () => {
  const layout = {
    first:{x:300,y:100,width:70,height:50,scale:1,visible:true,minimized:false,pinned:true,expanded:true},
    second:{x:10,y:500,width:60,height:80,scale:1,visible:true,minimized:true,expanded:false},
    closed:{x:40,y:90,width:40,height:30,scale:1,visible:false,minimized:false},
  };
  assert.equal(snapCardPositions(layout,[
    {id:'first',width:70,height:74},
    {id:'second',width:60,height:28},
  ],180,150,10),true);
  assert.deepEqual([layout.first.x,layout.first.y],[10,10]);
  assert.deepEqual([layout.second.x,layout.second.y],[90,10]);
  assert.deepEqual([layout.first.width,layout.first.height,layout.first.scale,layout.first.minimized,layout.first.pinned,layout.first.expanded],[70,50,1,false,true,true]);
  assert.deepEqual([layout.second.width,layout.second.height,layout.second.minimized],[60,80,true]);
  assert.deepEqual([layout.closed.x,layout.closed.y],[40,90]);
});

test('snap leaves the current layout unchanged when every visible card cannot fit', () => {
  const layout = {
    first:{x:20,y:30,width:60,height:60,scale:1,visible:true},
    second:{x:90,y:80,width:60,height:60,scale:1,visible:true},
  };
  assert.equal(snapCardPositions(layout,[
    {id:'first',width:60,height:60},
    {id:'second',width:60,height:60},
  ],140,120,10),false);
  assert.deepEqual([layout.first.x,layout.first.y,layout.second.x,layout.second.y],[20,30,90,80]);
});

test('clipboard always exposes its full 130 percent extent and minimized windows use their visible height', () => {
  const extent = clipboardExtent(1000,800);
  assert.equal(extent.width,1300);
  assert.equal(extent.height,1040);
  const source = fs.readFileSync(path.join(gui,'card-board.js'),'utf8');
  assert.match(source,/canvas\.style\.width = `\$\{extent\.width\}px`/);
  assert.match(source,/canvas\.style\.height = `\$\{extent\.height\}px`/);

  const card = {x:100,y:900,width:600,height:500,scale:1,minScale:.7,minimized:true};
  constrainCardBounds(card,1300,1040,12,24,50);
  assert.equal(card.y,900);
  card.minimized = false;
  constrainCardBounds(card,1300,1040,12,24);
  assert.equal(card.y,504);
});

test('card scale and card-specific minimums survive layout restoration', () => {
  const initial = defaultLayout([
    {id:'identity',x:0,y:0,width:600,height:400},
    {id:'minutes',x:0,y:420,width:700,height:240},
    {id:'phase-playoffs-control',x:620,y:0,width:500,height:180},
  ]);
  assert.equal(initial.identity.scale,1);
  assert.equal(initial.identity.minScale,.72);
  assert.equal(initial.minutes.minScale,.65);
  assert.equal(initial['phase-playoffs-control'].minScale,.9);
  const restored = restoreLayout(JSON.stringify({version:1,cards:{identity:{scale:.84},'phase-playoffs-control':{scale:.94}}}),initial);
  assert.equal(restored.identity.scale,.84);
  assert.equal(restored['phase-playoffs-control'].scale,.94);
  assert.equal(restored.identity.width,600);
  assert.equal(restored.identity.height,400);
});

test('league wire width migration halves existing cards once and preserves height', () => {
  const layout = {'league-wire':{width:800,height:180,sizeRevision:1}};
  const saved = {cards:{'league-wire':{sizeRevision:1}}};
  migrateCardSizes(layout,saved);
  assert.equal(layout['league-wire'].width,400);
  assert.equal(layout['league-wire'].height,180);
  assert.equal(layout['league-wire'].sizeRevision,2);
  migrateCardSizes(layout,{cards:{'league-wire':{sizeRevision:2}}});
  assert.equal(layout['league-wire'].width,400);

  const legacy = {'league-wire':{width:1000,height:200}};
  migrateCardSizes(legacy,{cards:{'league-wire':{}}});
  assert.equal(legacy['league-wire'].width,610);
  assert.equal(legacy['league-wire'].height,210);

  const fresh = {'league-wire':{width:610,height:210}};
  migrateCardSizes(fresh,{});
  assert.equal(fresh['league-wire'].width,610);
});

test('prospect card widens for the side portrait without changing its height', () => {
  const layout = {prospects:{width:539,height:219,sizeRevision:2}};
  migrateCardSizes(layout,{cards:{prospects:{sizeRevision:2}}});
  // Round 13: never narrower than 760 (the wider scouted bar and the range key).
  assert.deepEqual([layout.prospects.width,layout.prospects.height,layout.prospects.sizeRevision],[760,219,3]);
  migrateCardSizes(layout,{cards:{prospects:{sizeRevision:3}}});
  assert.deepEqual([layout.prospects.width,layout.prospects.height],[760,219]);
});

test('minutes card migration narrows older windows once, making room for the current columns', () => {
  for (const [revision,width,height] of [[1,1680,720],[2,1360,720],[5,577,504]]) {
    const layout = {minutes:{width,height,sizeRevision:revision}};
    migrateCardSizes(layout,{cards:{minutes:{sizeRevision:revision}}});
    // Round 6: never narrower than 760 (the table's 10px inset on each side).
    assert.equal(layout.minutes.width, 760);
    assert.deepEqual([layout.minutes.height, layout.minutes.sizeRevision], [504, 7]);
    const saved = {cards:structuredClone(layout)};
    migrateCardSizes(layout,saved);
    assert.deepEqual(layout,saved.cards);
  }
});

test('team identity card migration removes excess saved height without changing width', () => {
  const layout = {identity:{width:1320,height:1300,scale:1,sizeRevision:1}};
  migrateCardSizes(layout,{cards:{identity:{sizeRevision:1}}});
  assert.equal(layout.identity.width,1320);
  // From revision 1 straight to the current one: 1/1.3 (old excess) times 1.1 (2026-11-23: courts fit above the legend).
  // Round 4: 7% taller for the Offense / Defense labels above the tabs.
  assert.equal(layout.identity.height,1177);
  assert.equal(layout.identity.scale,1);
  assert.equal(layout.identity.sizeRevision,5);
  migrateCardSizes(layout,{cards:{identity:{sizeRevision:5}}});
  assert.equal(layout.identity.height,1177);
});

test('radar cards widen for standings-sized labels without changing height', () => {
  const layout = {offense:{width:263,height:241},defense:{width:263,height:241}};
  const saved = {cards:{offense:{sizeRevision:3},defense:{sizeRevision:3}}};
  migrateCardSizes(layout,saved);
  assert.deepEqual([layout.offense.width,layout.offense.height,layout.offense.sizeRevision],[335,241,4]);
  assert.deepEqual([layout.defense.width,layout.defense.height,layout.defense.sizeRevision],[335,241,4]);
  migrateCardSizes(layout,{cards:{offense:{sizeRevision:4},defense:{sizeRevision:4}}});
  assert.equal(layout.offense.width,335);
  assert.equal(layout.defense.width,335);
});

test('resize input projects onto the window diagonal and preserves its aspect ratio', () => {
  const card = {width:800,height:500};
  const factor = .08;
  assert.ok(Math.abs(diagonalScaleDelta(card,card.width*factor,card.height*factor)-factor)<1e-12);
  assert.ok(Math.abs(diagonalScaleDelta(card,-card.width*factor,card.height*factor,'left')-factor)<1e-12);
  assert.ok(Math.abs(diagonalScaleDelta(card,card.width*factor,-card.height*factor,'left')+factor)<1e-12);
});
