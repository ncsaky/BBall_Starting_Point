// UI batch 1: draft-night layout and per-pick animation, playoff entry layout and injuries card, roster cut-down
// counter, card-gallery previews.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const board = fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8');
const visuals = fs.readFileSync(path.join(gui, 'card-visuals.js'), 'utf8');
const slice = (from, to) => {
  const start = app.indexOf(from);
  const end = app.indexOf(to, start + 1);
  assert.ok(start >= 0 && end > start, `missing app.js section ${from}`);
  return app.slice(start, end);
};
const cardBoard = () => {
  const scope = {window: {}, structuredClone};
  vm.createContext(scope);
  vm.runInContext(board, scope);
  return scope.window.CardBoard;
};
const card = (width, height, minScale = .8) => ({x: 0, y: 0, width, height, scale: 1, minScale, visible: false});
const overlaps = (a, b) => a.x < b.x + b.width * b.scale && b.x < a.x + a.width * a.scale
  && a.y < b.y + 24 + b.height * b.scale && b.y < a.y + 24 + a.height * a.scale;

test('draft-night cards open side by side, centered, without overlap', () => {
  const {arrangeEntryRows} = cardBoard();
  const layout = {'phase-draft-board': card(1060, 700), 'phase-draft-order': card(330, 700), minutes: {...card(500, 400), visible: true}};
  const viewport = {clientWidth: 1600, clientHeight: 900, scrollLeft: 0, scrollTop: 0};
  arrangeEntryRows(layout, [['phase-draft-board', 'phase-draft-order']], viewport);
  const boardCard = layout['phase-draft-board'], order = layout['phase-draft-order'];
  assert.equal(boardCard.visible && order.visible, true);
  assert.equal(boardCard.scale, 1);
  assert.equal(boardCard.y, order.y);
  assert.ok(!overlaps(boardCard, order));
  const left = boardCard.x, right = 1600 - (order.x + order.width);
  assert.ok(Math.abs(left - right) <= 2, `centered: ${left} vs ${right}`);
});

test('a narrow window scales the row down, and splits it when cards would be unreadable', () => {
  const {arrangeEntryRows} = cardBoard();
  const narrow = {'phase-draft-board': card(1060, 500), 'phase-draft-order': card(330, 500)};
  arrangeEntryRows(narrow, [['phase-draft-board', 'phase-draft-order']], {clientWidth: 1300, clientHeight: 900});
  assert.ok(narrow['phase-draft-board'].scale < 1 && narrow['phase-draft-board'].scale >= .8);
  assert.equal(narrow['phase-draft-board'].y, narrow['phase-draft-order'].y);
  assert.ok(!overlaps(narrow['phase-draft-board'], narrow['phase-draft-order']));
  const phone = {'phase-draft-board': card(1060, 500), 'phase-draft-order': card(330, 500)};
  arrangeEntryRows(phone, [['phase-draft-board', 'phase-draft-order']], {clientWidth: 700, clientHeight: 900});
  assert.ok(phone['phase-draft-order'].y > phone['phase-draft-board'].y, 'stacked into two rows');
  assert.ok(!overlaps(phone['phase-draft-board'], phone['phase-draft-order']));
});

test('playoff entry: bracket on top, stats, injuries and minutes below, all inside the window when possible', () => {
  const {arrangeEntryRows} = cardBoard();
  const layout = {
    'phase-playoffs-bracket': card(1380, 480, .74), 'phase-playoffs-leaders': card(600, 400, .78),
    'phase-playoffs-injuries': card(556, 400, .78), minutes: card(570, 430, .65),
  };
  const placed = arrangeEntryRows(layout, [['phase-playoffs-bracket'], ['phase-playoffs-leaders', 'phase-playoffs-injuries', 'minutes']], {clientWidth: 1440, clientHeight: 840});
  assert.deepEqual(Array.from(placed), ['phase-playoffs-bracket', 'phase-playoffs-leaders', 'phase-playoffs-injuries', 'minutes']);
  const ids = Object.keys(layout);
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) assert.ok(!overlaps(layout[ids[i]], layout[ids[j]]), `${ids[i]} / ${ids[j]}`);
  for (const id of ids) assert.ok(layout[id].x + layout[id].width * layout[id].scale <= 1440 - 12 + 1, `${id} inside the width`);
  assert.ok(layout.minutes.y > layout['phase-playoffs-bracket'].y);
  // A small laptop screen: cards never overlap; whatever cannot fit stays closed instead of being piled on top.
  const small = {
    'phase-playoffs-bracket': card(964, 480, .74), 'phase-playoffs-leaders': card(600, 400, .78),
    'phase-playoffs-injuries': card(556, 400, .78), minutes: {...card(570, 430, .65), visible: true},
  };
  const {applyEntryLayout} = cardBoard();
  const shown = Array.from(applyEntryLayout(small, {rows: [['phase-playoffs-bracket'], ['phase-playoffs-leaders', 'phase-playoffs-injuries', 'minutes']]}, {clientWidth: 1010, clientHeight: 670}, {}, true));
  assert.deepEqual(shown, ['phase-playoffs-bracket', 'phase-playoffs-leaders', 'phase-playoffs-injuries']);
  assert.equal(small.minutes.visible, false);
  for (const a of shown) for (const b of shown) if (a < b) assert.ok(!overlaps(small[a], small[b]), `${a} / ${b}`);
  for (const id of shown) assert.ok(small[id].y + 24 + small[id].height * small[id].scale <= Math.floor(670 * 1.3), `${id} inside the board`);
});

test('entry layouts apply once: on entering, or when a card group first appears; reloads keep the user layout', () => {
  const {entryLayoutDue, applyEntryLayout} = cardBoard();
  const rows = {rows: [['phase-playoffs-bracket'], ['phase-playoffs-leaders', 'phase-playoffs-injuries', 'minutes']]};
  assert.equal(entryLayoutDue(rows, {}, true), true);
  const saved = {phaseContext: '2026-27:postseason-v2:playoffs', phaseCards: ['phase-playoffs-bracket', 'phase-playoffs-leaders', 'phase-playoffs-injuries']};
  assert.equal(entryLayoutDue(rows, saved, false), false, 'a reload never rearranges');
  const layout = {minutes: {...card(500, 400), visible: false}, 'phase-playoffs-bracket': card(1380, 480)};
  assert.deepEqual(Array.from(applyEntryLayout(layout, rows, {clientWidth: 1440, clientHeight: 840}, saved, false)), []);
  assert.equal(layout.minutes.visible, false, 'Minutes closed by hand stays closed');
  const results = {rows: [['phase-draft-summary', 'phase-draft-trades']]};
  assert.equal(entryLayoutDue(results, {phaseCards: ['phase-draft-board', 'phase-draft-order']}, false), true, 'draft results appear');
  assert.equal(entryLayoutDue(results, {phaseCards: ['phase-draft-summary', 'phase-draft-trades']}, false), false);
  const focus = {roster: {...card(400, 300), visible: true}, pinned: {...card(200, 200), visible: true, pinned: true}, 'phase-draft-board': card(1060, 600), 'phase-draft-order': card(330, 600)};
  applyEntryLayout(focus, {rows: [['phase-draft-board', 'phase-draft-order']]}, {clientWidth: 1500, clientHeight: 900}, {}, true);
  assert.equal(focus.roster.visible, false, 'other windows step aside on entry');
  assert.equal(focus.pinned.visible, true, 'pinned windows stay');
});

const draftScope = (overrides = {}) => {
  const scope = {
    state: {currentSave: 'save-a', draftPlaybackRunning: false, draftPlaybackReveal: null, ...overrides},
    escapeHtml: String, escapeAttr: String, teamLabel: (team) => team?.abbrev || String(team || ''),
    draftTeamLogo: (team) => `<logo ${team?.abbrev || ''}>`,
  };
  vm.createContext(scope);
  vm.runInContext(slice('function draftFreshPick(', 'function draftLotteryOddsWorkspace('), scope);
  return scope;
};
const timeline = (done, total = 6) => Array.from({length: total}, (_, index) => ({
  selection: {overall_pick: index + 1}, team: {abbrev: `T${index + 1}`}, prospect: {name: `P${index + 1}`, position: 'G', age: 19.6},
  draft_status: index < done ? 'selected' : index === done ? 'current' : 'upcoming', explanation: `T${index + 1} took P${index + 1}: best left.`,
}));

test('each pick animates exactly once: first view, re-renders and the final room never replay', () => {
  const scope = draftScope();
  const room = (done) => ({year: 2027, draft_timeline: timeline(done)});
  assert.equal(scope.draftFreshPick(room(2)), 0, 'picks already made when the room opens do not animate');
  assert.equal(scope.draftFreshPick(room(2)), 0, 'a re-render does not replay');
  assert.equal(scope.draftFreshPick(room(3)), 3, 'a new pick animates');
  assert.equal(scope.draftFreshPick(room(3)), 0, 'once');
  assert.equal(scope.draftFreshPick(room(4)), 4);
  assert.equal(scope.draftFreshPick(room(6)), 6, 'after a skip only the latest pick animates');
  scope.state.currentSave = 'save-b';
  assert.equal(scope.draftFreshPick(room(6)), 0, 'another save starts fresh');
  const stage = scope.draftPickStage(room(3), 3);
  assert.match(stage, /draft-pick-reveal is-fresh is-last-pick/);
  assert.match(stage, /Last pick #3/);
  assert.match(stage, /T3 selects P3/);
  assert.match(stage, /best left/);
  assert.doesNotMatch(scope.draftPickStage(room(3), 0), /is-fresh/);
});

test('playback shows the pick being announced with a Skip button; reduced motion is handled in CSS', () => {
  const scope = draftScope({draftPlaybackRunning: true, draftPlaybackReveal: {type: 'pick', overall_pick: 4, team: {abbrev: 'BKN'}, prospect: {name: 'Caleb Holt', position: 'SG', age: 20}, explanation: 'BKN took Caleb Holt: he slid to 4.'}});
  const stage = scope.draftPickStage({year: 2027, draft_timeline: timeline(4)}, 4);
  assert.match(stage, /is-fresh is-playing/);
  assert.match(stage, /Pick #4/);
  assert.match(stage, /data-draft-playback-skip/);
  assert.match(stage, /role="status" aria-live="polite"/);
  const css = fs.readFileSync(path.join(gui, 'card-board.css'), 'utf8');
  const reduced = css.slice(css.indexOf('@media (prefers-reduced-motion:reduce) {\n  .draft-pick-reveal.is-fresh'));
  assert.match(reduced, /animation:none !important/);
  assert.match(app, /\[data-draft-playback-skip\]:not\(\[data-skip-requested\]\)/, 'Skip stays clickable while the app is busy');
});

test('Skip stops the reveals, keeps the trade alerts once, and lands on the final room', async () => {
  let frames = 0, alerts = 0;
  const final = {state: {status: 'completed'}};
  const scope = {
    state: {busyDepth: 0, data: {}, draftPlaybackRunning: false},
    window: {AssistantGMPhone: {setDraftPlaybackActive() {}, presentDraftTrades: async () => { alerts += 1; }}},
    GameSimulation: {draftPlaybackFrame: (room, events, count) => ({frame: count}), wait: async () => { scope.state.draftPlaybackSkip = frames >= 2; }, reducedMotion: () => false},
    refreshDashboardAfterPhaseMutation: async () => {}, updateDraftPlaybackCard: () => { frames += 1; },
    setBusy() {}, showToast() {}, maybeShowWantReminder: undefined,
  };
  vm.createContext(scope);
  vm.runInContext(slice('async function playDraftSimulation(', 'function updateDraftPlaybackCard('), scope);
  const events = [{type: 'pick', overall_pick: 2}, {type: 'pick', overall_pick: 3}, {type: 'trade'}, {type: 'pick', overall_pick: 4}, {type: 'pick', overall_pick: 5}];
  await scope.playDraftSimulation(final, events, 4);
  assert.equal(frames, 3, 'two revealed frames, then the final room');
  assert.equal(alerts, 1, 'trade alerts still shown once');
  assert.equal(scope.state.data.draft, final);
  assert.equal(scope.state.draftPlaybackRunning, false);
  assert.equal(scope.state.draftPlaybackSkip, false);
});

test('roster cut-down counter: required releases, readiness, extra releases and costs', () => {
  const scope = {state: {}, money: (value) => `$${Number(value).toFixed(1)}M`};
  vm.createContext(scope);
  vm.runInContext(slice('function cutdownReleaseCost(', 'function cutdownContractCell('), scope);
  const player = (id, waive, payout, unquantified = false) => ({player_id: id, name: id, waiver: {remaining_cost_millions: waive, unquantified}, buyout: {payout_millions: payout, unquantified}});
  const room = {current_count: 17, target_count: 15, players: [player('a', 2.4, 2.2), player('b', 3.0, 2.7), player('c', 9, 8, true)]};
  let summary = scope.cutdownSelectionSummary(room, {});
  assert.equal(summary.required, 2);
  assert.equal(summary.after, 17);
  assert.equal(summary.ready, false);
  summary = scope.cutdownSelectionSummary(room, {a: 'waive'});
  assert.equal(summary.remaining, 1);
  assert.equal(summary.ready, false);
  summary = scope.cutdownSelectionSummary(room, {a: 'waive', b: 'buyout'});
  assert.equal(summary.after, 15);
  assert.equal(summary.ready, true);
  assert.equal(summary.extra, 0);
  assert.ok(Math.abs(summary.costMillions - 5.1) < 1e-9);
  assert.equal(summary.unknownCost, false);
  summary = scope.cutdownSelectionSummary(room, {a: 'waive', b: 'waive', c: 'buyout'});
  assert.equal(summary.extra, 1);
  assert.equal(summary.unknownCost, true, 'an unquoted contract is flagged, not counted as zero silently');
  assert.equal(scope.cutdownSelectionSummary({current_count: 15, target_count: 15, players: []}, {}).ready, false);
});

test('playoff injuries card: OVR order by default, your-team filter, sort toggles', () => {
  const scope = {state: {}};
  vm.createContext(scope);
  vm.runInContext(slice('const PLAYOFF_INJURIES_DEFAULT_SORT', 'function playoffInjuryRatingCell('), scope);
  const payload = {players: [
    {name: 'B', overall: 66, status: 'out', days_left: 9, user_team: false},
    {name: 'A', overall: 73, status: 'out', days_left: 2, user_team: true},
    {name: 'C', overall: 60, status: 'returning', rust_games: 2, user_team: false},
  ]};
  assert.deepEqual(Array.from(scope.playoffInjuriesRows(payload, 'league', null), (row) => row.name), ['A', 'B', 'C']);
  assert.deepEqual(Array.from(scope.playoffInjuriesRows(payload, 'team', null), (row) => row.name), ['A']);
  const back = scope.nextPlayoffInjuriesSort(null, 'back');
  assert.equal(back.direction, 'asc');
  assert.deepEqual(Array.from(scope.playoffInjuriesRows(payload, 'league', back), (row) => row.name), ['A', 'B', 'C']);
  assert.deepEqual(JSON.parse(JSON.stringify(scope.nextPlayoffInjuriesSort({key: 'overall', direction: 'desc'}, 'overall'))), {key: 'overall', direction: 'asc'});
  const definitions = slice('function seasonalClipboardCards(', 'function clipboardLockedCards(');
  assert.match(definitions, /\["injuries", "\.playoff-injuries-panel", "Playoff Injuries"\]/);
  assert.match(slice('function clipboardEntryLayout(', 'function seasonalClipboardCards('), /"phase-playoffs-leaders", "phase-playoffs-injuries", "minutes"/);
});

test('every gallery card gets a drawn preview, never an empty or broken thumbnail', () => {
  const scope = {window: {}};
  vm.createContext(scope);
  vm.runInContext(visuals, scope);
  const {preview, previewKind, description} = scope.window.CardVisuals;
  const ids = ['identity', 'signals', 'morale', 'factors', 'offense', 'defense', 'standings', 'week', 'opponent', 'minutes', 'development',
    'efficiency', 'prospects', 'award-mvp', 'award-dpoy', 'award-roty', 'staff', 'league-wire', 'roster', 'stats', 'contracts', 'payroll',
    'picks', 'league-block', 'team-block', 'team-wants', 'trade-builder', 'phase-playoffs-bracket', 'phase-playoffs-leaders',
    'phase-playoffs-injuries', 'phase-draft-lottery', 'phase-draft-board', 'phase-draft-order', 'phase-draft-summary', 'phase-draft-trades',
    'phase-free_agency-market', 'phase-free_agency-selected', 'phase-free_agency-offers', 'phase-cutdown-decision', 'player-card-4'];
  for (const id of ids) {
    const svg = preview(id);
    assert.match(svg, /^<svg class="card-visual-preview" viewBox="0 0 160 100"/, id);
    assert.doesNotMatch(svg, /undefined|NaN/, id);
    assert.ok(svg.length > 600, `${id} has content`);
    assert.ok(description(id), id);
  }
  assert.equal(previewKind('phase-playoffs-injuries'), 'injuries');
  assert.equal(description('phase-playoffs-injuries'), 'Injured & returning players');
  assert.match(board, /window\.CardVisuals\.preview \? window\.CardVisuals\.preview\(id\)/);
});
