// Q1 GUI fixes: Next Opponent after a result, the S-prefix sim shortcut, and lottery grid order.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const interfaceSource = fs.readFileSync(path.join(gui, 'interface.js'), 'utf8');
const tick = () => new Promise((resolve) => setImmediate(resolve));

function element(tag, {editable = false} = {}) {
  return {
    tagName: tag, isConnected: false, attributes: {},
    closest() { return editable ? this : null; },
    matches() { return false; },
    setAttribute(name, value) { this.attributes[name] = value; },
    getAttribute(name) { return this.attributes[name] ?? null; },
  };
}

function loadInterface() {
  const listeners = [];
  const body = {children: [], append(el) {
    this.children.push(el); el.isConnected = true;
    el.remove = () => { body.children = body.children.filter((child) => child !== el); el.isConnected = false; };
  }};
  const timers = [];
  const ran = [];
  const closed = [];
  const document = {
    body, activeElement: null,
    addEventListener(type, fn, capture) { listeners.push({type, fn, capture: Boolean(capture)}); },
    getElementById(id) { return id === 'app' ? element('div') : body.children.find((child) => child.id === id) || null; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    createElement: (tag) => element(tag),
  };
  const context = {
    document, console, Promise,
    window: {CardBoard: {closeActive: () => closed.push('card'), toggleActiveMinimize: () => false, toggleActivePin: () => false, toggleActiveExpansion: () => false}},
    setTimeout: (fn) => { timers.push(fn); return timers.length; },
    clearTimeout: () => {},
    requestAnimationFrame: () => 0,
    getComputedStyle: () => ({visibility: 'visible'}),
    MutationObserver: class { observe() {} },
  };
  vm.createContext(context);
  vm.runInContext(`${interfaceSource}\nglobalThis.GameInterface = GameInterface;`, context);
  const command = (keys) => ({keys, label: keys, run: () => ran.push(keys)});
  context.GameInterface.init({
    commands: () => [command('s e'), command('s w'), command('s m')],
    busy: () => false, modal: () => false, closeModal: () => closed.push('modal'), error: (error) => { throw error; }, desktop: () => false,
  });
  const dispatch = (type, fields = {}) => {
    const event = {
      key: '', target: element('div'), metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, repeat: false, isComposing: false,
      defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...fields,
    };
    for (const capture of [true, false]) {
      for (const listener of listeners.filter((row) => row.type === type && row.capture === capture)) listener.fn(event);
    }
    return event;
  };
  const armed = () => Boolean(body.children.find((child) => child.id === 'keySequence'));
  return {dispatch, armed, ran, closed, timers};
}

test('S prefix stays armed through any pause and only for the documented exits', async () => {
  assert.doesNotMatch(interfaceSource, /prefixTimer|setTimeout\(clearPrefix/);

  let ui = loadInterface();
  ui.dispatch('keydown', {key: 's'});
  assert.ok(ui.armed());
  assert.equal(ui.timers.length, 0, 'arming the prefix must not start a timer');
  ui.dispatch('keydown', {key: 'Shift', shiftKey: true});
  ui.dispatch('keydown', {key: 's', repeat: true});
  const copy = ui.dispatch('keydown', {key: 'c', metaKey: true});
  assert.equal(copy.defaultPrevented, false, 'browser shortcuts are never hijacked');
  assert.ok(ui.armed(), 'modifiers, key repeats and Cmd/Ctrl combos leave the prefix armed');
  const week = ui.dispatch('keydown', {key: 'W'});
  await tick();
  assert.equal(week.defaultPrevented, true);
  assert.deepEqual(ui.ran, ['s w']);
  assert.equal(ui.armed(), false);

  ui = loadInterface();
  ui.dispatch('keydown', {key: 's'});
  ui.dispatch('pointerdown');
  assert.equal(ui.armed(), false, 'a click anywhere disarms');
  ui.dispatch('keydown', {key: 'e'});
  await tick();
  assert.deepEqual(ui.ran, []);

  ui = loadInterface();
  ui.dispatch('keydown', {key: 's'});
  const escape = ui.dispatch('keydown', {key: 'Escape'});
  assert.equal(ui.armed(), false, 'Escape disarms');
  assert.equal(escape.defaultPrevented, true);
  assert.deepEqual(ui.closed, [], 'Escape that disarms does not also close a card');

  ui = loadInterface();
  ui.dispatch('keydown', {key: 's'});
  ui.dispatch('focusin', {target: element('input', {editable: true})});
  assert.equal(ui.armed(), false, 'focus moving into a text field disarms');

  ui = loadInterface();
  const typed = ui.dispatch('keydown', {key: 's', target: element('input', {editable: true})});
  assert.equal(typed.defaultPrevented, false);
  assert.equal(ui.armed(), false, 'typing S in a text field never arms the prefix');
  ui.dispatch('keydown', {key: 's'});
  ui.dispatch('keydown', {key: 'm', target: element('textarea', {editable: true})});
  await tick();
  assert.deepEqual(ui.ran, []);
  assert.equal(ui.armed(), false);

  ui = loadInterface();
  ui.dispatch('keydown', {key: 's'});
  ui.dispatch('keydown', {key: 'e'});
  await tick();
  assert.deepEqual(ui.ran, ['s e']);
});

test('lottery grid places pick 1 first while picks still reveal from 14 down', () => {
  const scope = {window: {}};
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.join(gui, 'simulation-presentation.js'), 'utf8'), scope);
  const source = app.slice(app.indexOf('function draftLotteryGridPicks('), app.indexOf('\nfunction lotteryRevealKey('));
  assert.ok(source.includes('function draftLotteryRevealWorkspace('));
  let count = 0;
  Object.assign(scope, {
    GameSimulation: scope.window.GameSimulation,
    lotteryRevealCount: () => count,
    escapeHtml: (value) => String(value), teamLabel: (team) => team?.abbrev || '', draftTeamLogo: () => '',
  });
  vm.runInContext(source, scope);
  assert.deepEqual([...scope.draftLotteryGridPicks(14)], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]);
  const reveal = Array.from({length: 14}, (_, index) => ({pick: index + 1, starting_seed: index + 1, movement: 0, original_team: {id: `t${index + 1}`, abbrev: `T${index + 1}`}}));
  const draft = {year: 2027, lottery: {reveal, odds: [], draw_count: 4}};
  const picksIn = (markup) => [...markup.matchAll(/data-lottery-pick="(\d+)"( data-revealed="true")?/g)].map((match) => [Number(match[1]), Boolean(match[2])]);

  const hidden = picksIn(scope.draftLotteryRevealWorkspace(draft));
  assert.deepEqual(hidden.map(([pick]) => pick), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]);
  count = 3;
  const partial = picksIn(scope.draftLotteryRevealWorkspace(draft));
  assert.deepEqual(partial.map(([pick]) => pick), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]);
  assert.deepEqual(partial.filter(([, shown]) => shown).map(([pick]) => pick), [12, 13, 14], 'reveal timing still starts at 14');
  assert.match(scope.draftLotteryRevealWorkspace(draft), /Next: #11/);
});

function loadOpponentFlow() {
  const source = app.slice(app.indexOf('function updateOpponentDuringSimulation('), app.indexOf('\nfunction captureTeamSignalBars('));
  assert.ok(source.includes('function showSimulationOpponentResult('));
  const table = {banner: null, append(el) { this.banner = el; el.table = this; }};
  let html = 'initial';
  const panel = {
    get innerHTML() { return html; },
    set innerHTML(value) { html = value; table.banner = null; },
    querySelector: (selector) => selector === '.season-opponent-table' ? table : selector === '.season-simulation-result-banner' ? table.banner : null,
  };
  const frame = {dataset: {}, querySelector: () => panel};
  const timers = [];
  const label = (team) => !team ? '' : typeof team === 'string' ? team.replace('team_', '').toUpperCase() : team.abbrev || team.id || '';
  const context = {
    state: {
      simulationRunning: true, simulationCompletedGameIds: new Set(), simulationPendingOpponent: null, simulationOpponentResult: null,
      simulationOpponentSignature: '', simulationUpcomingGames: [], teams: [],
      home: {save: {user_team: {id: 'team_gsw', abbrev: 'GSW'}}},
      data: {dashboard: {team: {abbrev: 'GSW'}, next_games: [{game_id: 'g1'}]}, dashboardCalendar: {games: []}, dashboardStandings: {standings: [{team: {id: 'team_nyk', abbrev: 'NYK'}, wins: 4, losses: 2}]}},
    },
    document: {
      querySelector: (selector) => selector === '[data-board-window="opponent"]' ? frame : selector.includes('.season-opponent-panel') ? panel : null,
      createElement: (tag) => ({tagName: tag, setAttribute() {}, remove() { if (this.table?.banner === this) this.table.banner = null; this.removed = true; }}),
    },
    window: {setTimeout: (fn) => timers.push(fn)},
    teamLabel: label, userTeam: () => 'GSW', escapeHtml: (value) => String(value), clampNumber: (value) => value,
    seasonGameTeamLabel: (game, side) => label(game?.[`${side}_team`] || game?.[`${side}_team_id`]),
    seasonGameOpponent: (game, team) => game.opponent_team_id ? label(game.opponent_team_id) : label(game.home_team) === team ? label(game.away_team) : label(game.home_team),
    standingsRows: (data) => data?.standings || [],
    wireDashboardPlayerCards() {}, wireSeasonOpponentSorting() {}, wireSeasonOpponentInjuryTicker() {},
  };
  context.seasonOpponentCard = (dash) => `${(dash.next_games || [])[0]?.game_id || 'none'}|${context.state.data.dashboardOpponent?.pending ? 'pending' : 'live'}|${label(context.state.data.dashboardOpponent?.team)}`;
  vm.createContext(context);
  vm.runInContext(source, context);
  const result = (gameId, date, opponentId) => context.showSimulationOpponentResult({date, game: {game_id: gameId, home_team_id: 'team_gsw', away_team_id: opponentId, home_score: 110, away_score: 100}});
  const opponent = (gameId, date, abbrev) => ({team: {id: `team_${abbrev.toLowerCase()}`, abbrev}, record: {wins: 1, losses: 1}, rotation: [], next_game: {game_id: gameId, date, opponent_team_id: `team_${abbrev.toLowerCase()}`}});
  return {context, table, timers, html: () => html, result, opponent};
}

test('next opponent card switches to the real next opponent after the result banner', async () => {
  const flow = loadOpponentFlow();
  const {context, table, timers} = flow;

  assert.equal(flow.result('g1', '2026-10-21', 'team_okc'), true);
  assert.ok(table.banner, 'W/L banner shows on the completed game');
  context.updateOpponentDuringSimulation(flow.opponent('g2', '2026-10-23', 'BOS'));
  assert.equal(flow.html(), 'initial', 'card stays on the completed game while the banner plays');
  assert.ok(table.banner);
  timers.shift()();
  assert.equal(table.banner, null);
  assert.equal(flow.html(), 'g2|live|BOS', 'after the banner the card shows the next opponent');

  // A later live update must never move the card back to a finished game.
  context.updateOpponentDuringSimulation(flow.opponent('g1', '2026-10-21', 'OKC'));
  assert.equal(flow.html(), 'g2|live|BOS');

  // Fast playback: the next result arrives before the earlier banner ends.
  flow.result('g2', '2026-10-23', 'team_bos');
  context.updateOpponentDuringSimulation(flow.opponent('g3', '2026-10-24', 'ORL'));
  flow.result('g3', '2026-10-24', 'team_orl');
  assert.equal(flow.html(), 'g3|live|ORL', 'each result lands on its own opponent');
  assert.ok(table.banner);
  timers.shift()(); // stale timer for g2 changes nothing
  assert.equal(flow.html(), 'g3|live|ORL');
  assert.ok(table.banner);

  // Banner ends before the sim streams the next opponent: preview from the loaded schedule.
  context.state.data.dashboardCalendar.games = [
    {game_id: 'g3', date: '2026-10-24', home_team: 'GSW', away_team: 'ORL', status: 'simulated'},
    {game_id: 'g9', date: '2026-10-30', home_team: 'SAS', away_team: 'GSW', status: 'scheduled'},
    {game_id: 'g4', date: '2026-10-27', home_team: 'NYK', away_team: 'GSW', status: 'scheduled'},
  ];
  timers.shift()();
  assert.equal(flow.html(), 'g4|pending|NYK');
  assert.deepEqual({...context.state.data.dashboardOpponent.record}, {wins: 4, losses: 2});
  assert.equal(context.state.data.dashboard.next_games[0].is_home, false);
  context.updateOpponentDuringSimulation(flow.opponent('g4', '2026-10-27', 'NYK'));
  assert.equal(flow.html(), 'g4|live|NYK', 'the full card replaces the preview when it streams in');

  // No next game known (season over or not loaded yet): a waiting state, never the finished game.
  context.state.data.dashboardCalendar.games = [];
  flow.result('g4', '2026-10-27', 'team_nyk');
  timers.shift()();
  assert.equal(flow.html(), 'none|pending|');

  // Sim ends or is stopped mid-banner: the banner finishes and the final snapshot owns the card.
  flow.result('g5', '2026-11-01', 'team_lal');
  const hold = context.state.simulationOpponentResult;
  hold.final = true;
  context.updateOpponentDuringSimulation(flow.opponent('g6', '2026-11-03', 'LAC'));
  timers.shift()();
  await hold.done;
  assert.equal(flow.html(), 'none|pending|', 'no extra redraw after the sim has finished');
  assert.equal(context.state.simulationOpponentResult, null);
  assert.equal(context.state.simulationPendingOpponent, null);
});

test('next scheduled game skips finished games and picks the earliest remaining', () => {
  const source = app.slice(app.indexOf('function nextScheduledTeamGame('), app.indexOf('\n// Called when a W/L banner ends'));
  const context = {};
  vm.createContext(context);
  vm.runInContext(source, context);
  const games = [
    {game_id: 'a', date: '2026-10-21', team: 'GSW'},
    {game_id: 'b', date: '2026-10-25', team: 'GSW', home_score: 100, away_score: 90},
    {game_id: 'c', date: '2026-10-29', team: 'GSW'},
    {game_id: 'd', date: '2026-10-27', team: 'LAL'},
    {game_id: 'e', date: '2026-10-28', team: 'GSW'},
  ];
  const pick = (options) => context.nextScheduledTeamGame(games, {involvesTeam: (game) => game.team === 'GSW', ...options})?.game_id ?? null;
  assert.equal(pick({completedIds: new Set(['a']), afterDate: '2026-10-21'}), 'e');
  assert.equal(pick({completedIds: new Set(), afterDate: '2026-10-29'}), 'c');
  assert.equal(pick({completedIds: new Set(['c']), afterDate: '2026-10-29'}), null);
});

test('opponent card has an explicit no-next-game state', () => {
  const source = app.slice(app.indexOf('function seasonOpponentCard('), app.indexOf('\nfunction seasonPreviousGamesCard('));
  const scope = {state: {data: {dashboardOpponent: null}}};
  vm.createContext(scope);
  vm.runInContext(source, scope);
  assert.match(scope.seasonOpponentCard({next_games: []}, 'GSW'), /No upcoming game on the schedule\./);
  scope.state.data.dashboardOpponent = {pending: true};
  assert.match(scope.seasonOpponentCard({next_games: []}, 'GSW'), /Waiting for the next game on the schedule\./);
});

test('prospect injury marker separates history, current injury and risk without inventing data', () => {
  const grab = (name) => app.match(new RegExp(`function ${name}\\([\\s\\S]*?\\n}\\n`))[0];
  const escapeHtml = (v) => String(v);
  const escapeAttr = (v) => String(v);
  const ctx = {escapeHtml, escapeAttr};
  vm.createContext(ctx);
  vm.runInContext(`${grab('prospectInjuryTitle')}\n${grab('prospectInjuryMarkup')}`, ctx);
  assert.equal(ctx.prospectInjuryMarkup(null), '');
  assert.equal(ctx.prospectInjuryMarkup({available: false}), '');
  const html = ctx.prospectInjuryMarkup({available: true, history: [{body_area: 'Knee', severity: 'medium', season: '2025', status: 'recovered'}], current: {body_area: 'Knee', severity: 'medium', return_date: '2026-08-01'}, risk_label: 'High', injury_prone: true});
  assert.match(html, /1 past/);
  assert.match(html, /prospect-injury-current/);
  assert.match(html, /prospect-injury-risk-high/);
  assert.match(html, /Knee \(medium, 2025, recovered\)/);
  const healthy = {available: true, history: [], current: null, risk_label: 'Low'};
  assert.match(ctx.prospectInjuryMarkup(healthy), /Low/);                 // full table shows the risk word
  assert.equal(ctx.prospectInjuryMarkup(healthy, {compact: true}), '');    // dense card stays quiet
  assert.match(ctx.prospectInjuryMarkup({...healthy, risk_label: 'Moderate'}, {compact: true}), /Moderate/);
});

test('rating bars use the provided reference (e.g. positional) and never a made-up midpoint', () => {
  const grab = (name) => app.match(new RegExp(`function ${name}\\([\\s\\S]*?\\n}\\n`))[0];
  const ctx = {
    escapeHtml: (v) => String(v), escapeAttr: (v) => String(v), draftMetric: (v) => String(v),
    clampNumber: (v, lo, hi) => Math.min(hi, Math.max(lo, v)), performanceBarStyle: () => '', ratingTone: () => 'average',
  };
  vm.createContext(ctx);
  vm.runInContext(`${grab('ratingQuartileTone')}\n${grab('playerCardRatingBar')}`, ctx);
  const none = ctx.playerCardRatingBar('Shooting', 60, 'shooting', {is_prospect: true});
  assert.doesNotMatch(none, /rating-average-marker/);
  const pos = ctx.playerCardRatingBar('Shooting', 60, 'shooting', {is_prospect: true, rating_league_averages: {shooting: 47.5}, rating_average_label: 'SF/PF average'});
  assert.match(pos, /title="SF\/PF average: 47\.5"/);
  const league = ctx.playerCardRatingBar('Shooting', 60, 'shooting', {rating_league_averages: {shooting: 52}});
  assert.match(league, /League average: 52\.0/);
});
