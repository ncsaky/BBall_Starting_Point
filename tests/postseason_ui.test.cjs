const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const board = fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8');

test('postseason opens only the bracket once, preserving later user window choices', () => {
  const scope = {window:{}, structuredClone};
  vm.createContext(scope);
  vm.runInContext(board, scope);
  const {enterPhase} = scope.window.CardBoard;
  const defaults = {'phase-playoffs-bracket':{x:0,y:0,width:1400,height:480,scale:1}};
  const cards = ['phase-playoffs-bracket','phase-playoffs-leaders'];
  const layout = {roster:{visible:true}, minutes:{visible:true}, 'phase-playoffs-bracket':{}, 'phase-playoffs-leaders':{}};
  const phaseContext = '2026-27:postseason-v2:playoffs';
  assert.equal(enterPhase(layout, defaults, {}, cards, phaseContext), true);
  assert.deepEqual(Object.keys(layout).filter(id=>layout[id].visible), ['phase-playoffs-bracket']);
  assert.equal(layout['phase-playoffs-bracket'].minimized, false);
  layout.roster.visible = true;
  layout['phase-playoffs-bracket'].minimized = true;
  const saved = {phaseContext, phaseCards:cards};
  assert.equal(enterPhase(layout, defaults, saved, cards, phaseContext), false);
  assert.equal(layout.roster.visible, true);
  assert.equal(layout['phase-playoffs-bracket'].minimized, true);
  enterPhase(layout, defaults, saved, cards, '2027-28:postseason-v2:playoffs');
  assert.equal(layout.roster.visible, false);
  assert.match(board, /item\.x = Math\.max\(0, \(board\.clientWidth - item\.width/);
  assert.match(board, /item\.y = 16;/);
  assert.match(board, /item\.topAlignedRevision = 1;/);
});

test('completed playoff bracket keeps the Finals winner label without a duplicate champion banner', () => {
  const scope = {
    state:{data:{playoffs:{champion:{abbrev:'SAS'},series:[],play_in:{}},playoffLeaders:{leaders:[]}},playoffLeaderStat:'points'},
    escapeHtml:String,
    teamLabel:team=>team.abbrev,
    playoffBracket:()=>'<div class="bracket-champion">Champion: SAS</div>',
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function playoffDashboardWorkspace()'),app.indexOf('function draftDashboardWorkspace()')),scope);
  const html = scope.playoffDashboardWorkspace();
  assert.doesNotMatch(html,/phase-champion/);
  assert.match(html,/bracket-champion/);
  const css = fs.readFileSync(path.join(gui,'styles.css'),'utf8');
  assert.match(css,/\.playoff-command-center \{[^}]*grid-template-rows: minmax\(0, 1fr\);/);
  assert.doesNotMatch(css,/\.playoff-command-center:has\(\.phase-champion\)/);
});

test('shared Sim menu substitutes playoff actions and retains keyboard targets', () => {
  const scope = {window:{}, structuredClone};
  vm.createContext(scope);
  vm.runInContext(board, scope);
  const {simulationMenuMarkup} = scope.window.CardBoard;
  const normal = simulationMenuMarkup(false);
  const playoffs = simulationMenuMarkup(true);
  for (const label of ['Next Event','Next Week','Next Month']) assert.match(normal, new RegExp(label));
  for (const label of ['One Game Per Series','One Full Series','Finish Playoffs']) assert.match(playoffs, new RegExp(label));
  assert.doesNotMatch(playoffs, /Next Event|Next Week|Next Month/);
  for (const mode of ['next-event','week','month']) assert.match(playoffs, new RegExp(`data-advance="${mode}"`));
  assert.match(app, /postseason_sim:\{"next-event":"game", week:"series", month:"all"\}\[mode\]/);
  const css = fs.readFileSync(path.join(gui,'card-board.css'), 'utf8');
  assert.match(css, /body \.has-card-board \.card-board-scroll \{[^}]*overflow:auto;/);
});

test('postseason phase command matches top-bar styling and hides trade tools', () => {
  assert.match(board, /const tradeMarkup = String\(options\.phaseContext\)\.includes\(":postseason-v2:"\) \? "" :/);
  assert.match(board, /\$\{tradeMarkup\}/);
  const css = fs.readFileSync(path.join(gui,'card-board.css'), 'utf8');
  assert.match(css, /\.card-board-tools > button,\s*body \.has-card-board \.card-board-phase-actions > button,/);
  assert.match(css, /\.card-board-phase-actions > button:hover:not\(:disabled\),/);
  assert.match(css, /\.card-board-phase-actions > button:active:not\(:disabled\),/);
  const html = fs.readFileSync(path.join(gui,'index.html'),'utf8');
  assert.match(html,/<link\b[^>]*href="\/card-board\.css\?v=[\w.-]+"/);
});

test('champion modal uses clipboard window chrome and keeps its button label dark on hover', () => {
  const css = fs.readFileSync(path.join(gui,'card-board.css'),'utf8');
  assert.match(css,/\.modal-box-score,\.modal-settings,\.modal-trade-offers,\.modal-champion\) > \.card-board-titlebar/);
  assert.match(css,/\.modal-champion > \.modal-head\.card-board-titlebar \{[\s\S]*?height:24px/);
  assert.match(css,/\.modal-champion \.modal-head \.card-board-control \{[\s\S]*?width:19px !important/);
  assert.match(css,/\.modal-champion \.champion-celebration > \.ui-command:hover:not\(:disabled\) \{[\s\S]*?color:#17212a !important/);
  const html = fs.readFileSync(path.join(gui,'index.html'),'utf8');
  assert.match(html,/<link\b[^>]*href="\/card-board\.css\?v=[\w.-]+"/);
});

test('champion popup celebrates the winner with brief confetti and honors reduced motion', () => {
  const scope = {
    state:{home:{save:{postseason_exit_required:true,season:'2027-28'}},currentSave:'test',data:{playoffs:{champion:{abbrev:'SAS'}}}},
    window:{CardBoard:{open:()=>{}}},
    sessionStorage:{getItem:()=>null,setItem:()=>{}},
    teamLabel:team=>team.abbrev,
    dashboardTeamName:name=>name,
    escapeHtml:String,
    renderModal:()=>{},
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function maybeCelebrateChampion()'),app.indexOf('function tradeDeadlineDate()')),scope);
  scope.maybeCelebrateChampion();
  assert.equal(scope.state.modal.kind,'champion');
  assert.match(scope.state.modal.body,/class="champion-confetti"/);
  assert.equal((scope.state.modal.body.match(/class="champion-confetti-piece"/g)||[]).length,30);
  assert.match(scope.state.modal.body,/>SAS<\/h2>/);
  const css = fs.readFileSync(path.join(gui,'styles.css'),'utf8');
  assert.match(css,/@keyframes championConfettiFall/);
  assert.match(css,/@media \(prefers-reduced-motion:reduce\)[\s\S]*?\.champion-confetti \{ display:none; \}/);
  const html = fs.readFileSync(path.join(gui,'index.html'),'utf8');
  assert.match(html,/<link\b[^>]*href="\/styles\.css\?v=[\w.-]+"/);
  assert.match(html,/<script\b[^>]*src="\/app\.js\?v=[\w.-]+"/);
});

test('lottery handoff opens only the lottery once and puts draft commands in the top bar', () => {
  const scope = {window:{},structuredClone,state:{home:{save:{postseason_exit_required:true}},data:{draft:{}}},
    dashboardPhaseKind:()=> 'draft',localStorage:{getItem:()=> '14'},escapeHtml:String};
  vm.createContext(scope);
  vm.runInContext(board,scope);
  const layout = {roster:{visible:true},'phase-playoffs-bracket':{visible:true},'phase-draft-lottery':{}};
  const cards = ['phase-draft-lottery'];
  const phaseContext = '2026-27:lottery-v2:draft';
  assert.equal(scope.window.CardBoard.enterPhase(layout,{}, {},cards,phaseContext),true);
  assert.deepEqual(Object.keys(layout).filter(id=>layout[id].visible),cards);
  layout.roster.visible=true;
  assert.equal(scope.window.CardBoard.enterPhase(layout,{}, {phaseContext,phaseCards:cards},cards,phaseContext),false);
  assert.equal(layout.roster.visible,true);
  vm.runInContext(app.slice(app.indexOf('function lotteryRevealKey('),app.indexOf('function draftProspectBoard(')),scope);
  assert.match(scope.clipboardPhaseCommands(),/class="ui-command"[^>]+data-phase-command="postseason-exit"/);
  scope.state.home.save.postseason_exit_required=false;
  scope.state.draftPresentationStage='odds';
  assert.match(scope.clipboardPhaseCommands(),/Reveal Lottery/);
  scope.state.draftPresentationStage='reveal';
  scope.state.data.draft={year:2027,lottery:{reveal:Array.from({length:14},()=>({}))}};
  assert.match(scope.clipboardPhaseCommands(),/Enter Draft Night/);
  const draftDefinitions = app.slice(app.indexOf('function seasonalClipboardCards('),app.indexOf('function clipboardLockedCards('));
  assert.doesNotMatch(draftDefinitions,/"Draft Controls"/);
});

test('bracket includes play-in, zero-zero matchups, and West to the left of East', () => {
  const scope = {escapeHtml:String, escapeAttr:String, rowLabel:String,
    teamLabel:t=>typeof t==='string'?t:t?.abbrev || '', teamLogoSrc:t=>/^[A-Z]{2,3}$/.test(t)?`assets/team_logos/${t}.png`:''};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function seriesCard('), app.indexOf('function html(')), scope);
  const series = [{id:'west-r1-1',round:'first_round',conference:'West',teams:[{abbrev:'OKC'},null],pending_seed:'8',score:[0,0]}];
  const playIn = {West:{teams:{7:{abbrev:'LAL'},8:{abbrev:'MEM'},9:{abbrev:'DAL'},10:{abbrev:'SAC'}},games:[]}};
  const result = scope.playoffBracket(series, null, playIn);
  assert.match(result, /7 vs 8/);
  assert.match(result, /Final · Winner → #8/);
  assert.match(result, /OKC<\/strong><span>0/);
  assert.match(result, /TBD<\/strong><span>0/);
  assert.match(result, /<img src="assets\/team_logos\/DAL\.png" alt="" \/><strong>DAL<\/strong>/);
  assert.match(result, /<img src="assets\/team_logos\/SAC\.png" alt="" \/><strong>SAC<\/strong>/);
  assert.match(result, /<strong>9\/10 winner<\/strong>/);
  assert.doesNotMatch(result, /<img src="assets\/team_logos\/(?:9\/10|7\/8)/);
  assert.match(result, /class="play-in-feeder-label winner">Winner<\/span>/);
  assert.match(result, /class="play-in-feeder-label loser">Loser<\/span>/);
  assert.match(result,/marker-end="url\(#bracket-play-in-flow-west\)"/);
  assert.match(result,/marker-end="url\(#bracket-play-in-qualifier-west\)"/);
  assert.match(result,/marker-end="url\(#bracket-link-west-first_round\)"/);
  assert.match(result,/marker-end="url\(#bracket-link-east-conference_finals\)"/);
  assert.doesNotMatch(result, /<text[^>]*>Winner<\/text>/);
  assert.ok(result.indexOf('bracket-conference west') < result.indexOf('bracket-conference east'));
  playIn.West.games = [{game_id:'pi1',away_team:{abbrev:'MEM'},home_team:{abbrev:'LAL'},away_score:101,home_score:99}];
  const played = scope.playoffBracket(series, null, playIn);
  assert.match(played, /data-game-box="pi1"/);
  assert.match(played, /<img src="assets\/team_logos\/MEM\.png" alt="" \/><strong>MEM<\/strong>/);
  const css = fs.readFileSync(path.join(gui, 'styles.css'), 'utf8');
  assert.match(css, /bracket-conference\.west \.bracket-round-title \{ justify-content: flex-end; text-align: right; \}/);
  assert.match(css, /bracket-conference\.east \.bracket-round-title \{ justify-content: flex-start; text-align: left; \}/);
  assert.match(css, /bracket-conference\.east \.play-in-feeder-links \{ left:auto; right:0; transform:scaleX\(-1\); \}/);
  assert.match(css, /bracket-conference\.east \.play-in-feeder-label \{ left:auto; right:-9px; \}/);
});

test('pending play-in final shows known teams and the bracket dims eliminated teams', () => {
  const scope = {escapeHtml:String, escapeAttr:String, rowLabel:String,
    teamLabel:t=>typeof t==='string'?t.replace('team_','').toUpperCase():t?.abbrev || '',
    teamLogoSrc:t=>/^[A-Z]{2,3}$/.test(t)?`assets/team_logos/${t}.png`:''};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function seriesCard('), app.indexOf('function html(')), scope);
  const team = (id,abbrev)=>({id,abbrev});
  const teams = {7:team('team_7','LAL'),8:team('team_8','MEM'),9:team('team_9','DAL'),10:team('team_10','SAC')};
  const playIn = {West:{teams,games:[
    {game_id:'pi-78',away_team:teams[8],home_team:teams[7],away_score:91,home_score:103},
    {game_id:'pi-910',away_team:teams[10],home_team:teams[9],away_score:97,home_score:106},
  ]}};
  const markup = scope.playoffBracket([],null,playIn);
  const finalNode = markup.slice(markup.indexOf('data-play-in-stage="2"'),markup.indexOf('data-play-in-stage="1"'));
  assert.match(finalNode,/data-team-id="team_9"[^>]*>.*?<strong>DAL<\/strong><span>—/);
  assert.match(finalNode,/data-team-id="team_8"[^>]*>.*?<strong>MEM<\/strong><span>—/);
  assert.doesNotMatch(finalNode,/9\/10 winner|7\/8 loser/);
  assert.match(markup,/class="series-team series-team-winner" data-team-id="team_7"/);
  assert.match(markup,/class="series-team series-team-advancing" data-team-id="team_8"/);
  assert.match(markup,/class="series-team series-team-loser" data-team-id="team_10"/);
  const css = fs.readFileSync(path.join(gui,'styles.css'),'utf8');
  assert.match(css,/\.series-team-loser \{ opacity:\.4; filter:grayscale\(1\); \}/);
  assert.match(css,/bracket-conference\.east \.bracket-play-in \.bracket-round-links \{ width:18px; \}/);
  assert.doesNotMatch(css,/bracket-conference\.east \.bracket-play-in \.bracket-round-links \{ width:48px; \}/);
});

test('play-in progress routes both 7/8 teams, then only advancing teams, through the bracket', () => {
  const start = app.indexOf('function playoffProgressFlightPlan(');
  const end = app.indexOf('\nfunction bracketTeamRow(',start);
  assert.ok(start>=0 && end>start);
  const scope = {};
  vm.createContext(scope);
  vm.runInContext(app.slice(start,end),scope);
  const game = (game_id,home,away,home_score,away_score)=>({game_id,home_team_id:home,away_team_id:away,home_score,away_score});
  const stage0 = scope.playoffProgressFlightPlan({play_in:{West:{games:['pi-78']}}},{game:game('pi-78','team_7','team_8',101,96)});
  assert.deepEqual(JSON.parse(JSON.stringify(stage0.map(item=>[item.teamId,item.destination,item.route,item.seed||'']))),[
    ['team_7','first_round','qualifier','7'],['team_8','play_in_final','7-8-loser',''],
  ]);
  const stage1 = scope.playoffProgressFlightPlan({play_in:{West:{games:['pi-78','pi-910']}}},{game:game('pi-910','team_9','team_10',100,95)});
  assert.deepEqual(JSON.parse(JSON.stringify(stage1.map(item=>[item.teamId,item.destination,item.route]))),[['team_9','play_in_final','9-10-winner']]);
  const stage2 = scope.playoffProgressFlightPlan({play_in:{West:{games:['pi-78','pi-910','pi-final']}}},{game:game('pi-final','team_8','team_9',99,97)});
  assert.deepEqual(JSON.parse(JSON.stringify(stage2.map(item=>[item.teamId,item.destination,item.seed]))),[['team_8','first_round','8']]);
  const completed = scope.playoffProgressFlightPlan({series:[{id:'west-r1-1',conference:'West',status:'completed',winner_team_id:'team_1'}]},{series_id:'west-r1-1'});
  assert.deepEqual(JSON.parse(JSON.stringify(completed.map(item=>[item.teamId,item.sourceSeriesId,item.destination]))),[['team_1','west-r1-1','next_series']]);
  assert.match(app,/bracketPathScreenPoints\(path\)/);
  assert.match(app,/animatePlayoffFlights\(shell,flights\)/);
  assert.match(app,/play-in-feeder-links path\[data-playin-flow\]/);
  assert.match(app,/sourceLogoClone:sourceLogo\.cloneNode\(true\)/);
  const flightAnimation = app.slice(app.indexOf('function animatePlayoffFlights('),app.indexOf('\nasync function displaySimulationProgress('));
  assert.match(flightAnimation,/targetLogo = target\?\.querySelector\("img"\)/);
  assert.doesNotMatch(flightAnimation,/scaleX|scaleY|scale\(/);
});

test('legacy semifinals reorder their actual feeders and preserve scores and saved data', () => {
  const scope = {escapeHtml:String, escapeAttr:String, rowLabel:String,
    teamLabel:t=>typeof t==='string'?t:t?.abbrev || '', teamLogoSrc:()=>''};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function seriesCard('), app.indexOf('function html(')), scope);
  const team = id=>({id,abbrev:id});
  const first = [0,1,2,3].map(i=>({id:`r1-${i}`,conference:'West',round:'first_round',
    team_ids:[`w${i}`,`l${i}`],teams:[team(`w${i}`),team(`l${i}`)],score:[4,1],winner:team(`w${i}`),winner_team_id:`w${i}`}));
  const semis = [
    {id:'semi-A',conference:'West',round:'conference_semifinals',team_ids:['w3','w1'],teams:[team('w3'),team('w1')],score:[1,4],winner:team('w1'),winner_team_id:'w1'},
    {id:'semi-B',conference:'West',round:'conference_semifinals',team_ids:['w2','w0'],teams:[team('w2'),team('w0')],score:[4,2],winner:team('w2'),winner_team_id:'w2'},
  ];
  const series = [...first,...semis];
  const before = JSON.stringify(series);
  const [leaves, parents, final] = scope.bracketConferenceRounds('West',series);
  assert.deepEqual(Array.from(leaves,s=>s.id), ['r1-0','r1-2','r1-1','r1-3']);
  assert.deepEqual(Array.from(parents,s=>s.id), ['semi-B','semi-A']);
  assert.deepEqual(Array.from(parents[0].teams,t=>t.id), ['w0','w2']);
  assert.deepEqual(Array.from(parents[0].score), [2,4]);
  assert.deepEqual(Array.from(parents[0].source_series_ids), ['r1-0','r1-2']);
  assert.deepEqual(Array.from(final[0].teams,t=>t.id), ['w2','w1']);
  assert.equal(JSON.stringify(series),before);
  const markup = scope.playoffBracket(series,null,{});
  assert.match(markup,/data-from-series="r1-0" data-to-series="semi-B"/);
  assert.match(markup,/data-from-series="r1-2" data-to-series="semi-B"/);
});

test('future round placeholders and play-in links have explicit stable destinations', () => {
  const scope = {escapeHtml:String, escapeAttr:String, rowLabel:String,
    teamLabel:t=>typeof t==='string'?t:t?.abbrev || '', teamLogoSrc:()=>''};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function seriesCard('), app.indexOf('function html(')), scope);
  const series = [0,1,2,3].map(i=>({id:`r1-${i}`,conference:'West',round:'first_round',
    teams:[{id:`a${i}`,abbrev:`A${i}`},null],pending_seed:i===0?'8':i===3?'7':null,score:[0,0]}));
  const rounds = scope.bracketConferenceRounds('West',series);
  assert.equal(rounds[1].length,2);
  assert.deepEqual(Array.from(rounds[1][0].source_series_ids), ['r1-0','r1-1']);
  assert.deepEqual(Array.from(rounds[1][1].source_series_ids), ['r1-2','r1-3']);
  const markup = scope.playoffBracket(series,null,{West:{teams:{},games:[]}});
  assert.match(markup,/data-qualifier-seed="8" data-to-series="r1-0"/);
  assert.match(markup,/data-qualifier-seed="7" data-to-series="r1-3"/);
  assert.ok(markup.indexOf('data-play-in-stage="2"') < markup.indexOf('data-play-in-stage="0"'));
  assert.match(markup,/class="play-in-feeder-label loser">Loser<\/span>/);
  assert.match(markup,/class="play-in-feeder-label winner">Winner<\/span>/);
  assert.doesNotMatch(markup,/<text[^>]*>(?:Loser|Winner)<\/text>/);
});

test('only shared Sim controls are exposed, with the normal deadline-style confirmation', () => {
  assert.doesNotMatch(app, /<button[^>]+data-playoff-sim/);
  assert.doesNotMatch(app, /\["control", "\.playoff-command-header"/);
  const commands = app.slice(app.indexOf('function gameCommands('), app.indexOf('function closeAllModals('));
  assert.match(commands, /keys:"s e"/);
  assert.doesNotMatch(commands, /data-playoff-sim|playoffAdvanceStage|Finish round/);
  assert.doesNotMatch(app, /data-continue-postseason/);
  const storage = new Map();
  const scope = {state:{currentSave:'save-a',home:{save:{season:'2026-27',current_date:'2027-04-13'}}}, localStorage:{getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)}, escapeHtml:String, formatWrittenDate:String, renderModal(){}};
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('function postseasonBoundaryDate('), app.indexOf('async function ensureStartingFiveReadyForAdvance(')), scope);
  scope.showPostseasonPrompt({date:'2027-04-13',requested_to_date:'2027-04-13'}, {next_event:true});
  assert.equal(scope.state.modal.postseasonBoundary, '2027-04-13');
  assert.match(scope.state.modal.body, /trade-deadline-prompt/);
  assert.match(scope.state.modal.body, /data-review-postseason/);
  assert.equal(scope.postseasonBoundaryDate(), '2027-04-13');
  storage.set(scope.postseasonReviewKey('2027-04-13'), '1');
  assert.equal(scope.hasReviewedPostseason('2027-04-13'), true);
  scope.state.currentSave = 'save-b';
  assert.equal(scope.hasReviewedPostseason('2027-04-13'), false);
  assert.equal(scope.hasReviewedPostseason('2028-04-13'), false);
});
