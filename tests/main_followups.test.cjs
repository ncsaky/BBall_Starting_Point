// What main added, shown in the interface (UI polish pass, 2026-11-27): the 3-2-1 lottery card and reveal, the
// year-end slide's lottery count, and why a free agent left on the signing wire.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const cut = (start, end) => app.slice(app.indexOf(start), app.indexOf(end, app.indexOf(start)));

function lotteryContext() {
  const context = {
    escapeHtml: (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])),
    teamLabel: (team) => team?.abbrev || String(team || ''),
    draftTeamLogo: () => '',
    lotteryRevealCount: () => 1,
    window: {}, TextDecoder, setTimeout,
  };
  vm.createContext(context);
  vm.runInContext(read('simulation-presentation.js'), context);
  vm.runInContext('const GameSimulation = window.GameSimulation;' + cut('function draftLotteryOddsWorkspace(', 'function lotteryRevealKey('), context);
  return context;
}
const team = (id) => ({id, abbrev: id.toUpperCase()});
function lottery(count, format) {
  const odds = Array.from({length: count}, (_, i) => ({seed: i + 1, team: team(`t${i + 1}`), odds: 0.1}));
  return {format, draw_count: format === '3-2-1' ? count : 4, odds,
    reveal: odds.map((row, i) => ({pick: count - i, starting_seed: row.seed, original_team: row.team, owner_team: row.team, movement: 0}))};
}

test('the lottery card under the 3-2-1 format: 16 rows, "All 16 picks drawn", eight rows a column', () => {
  const context = lotteryContext();
  const now = context.draftLotteryOddsWorkspace({year: '2027', lottery: lottery(16, '3-2-1')});
  assert.equal((now.match(/class="draft-odds-row"/g) || []).length, 16);
  assert.match(now, /<footer class="draft-lottery-note">All 16 picks drawn<\/footer>/);
  assert.match(now, /style="--lottery-rows:8"/);
  const old = context.draftLotteryOddsWorkspace({year: '2026', lottery: lottery(14, 'weighted_14')});
  assert.match(old, /Four picks drawn · Remaining teams follow record order\./, 'the old format keeps its line');
  assert.match(old, /style="--lottery-rows:7"/);
});

test('the reveal counts down from the real number of picks and has no "top four" notice when every pick is drawn', () => {
  const context = lotteryContext();
  const now = context.draftLotteryRevealWorkspace({year: '2027', lottery: lottery(16, '3-2-1')});
  assert.equal((now.match(/data-lottery-pick="/g) || []).length, 16);
  assert.match(now, /<footer class="draft-lottery-note" role="status">16 → 1<\/footer>/);
  assert.doesNotMatch(now, /top four|lottery-jump-notice/);
  const old = context.draftLotteryRevealWorkspace({year: '2026', lottery: lottery(14, 'weighted_14')});
  assert.match(old, /14 → 1|jumped into the top four/);
});

test('16 rows fit the card: eight rows a column (no third column), sharing the height, nothing scrolls', () => {
  const css = read('full-pages.css');
  assert.match(css, /\[data-pages-slot="phase-draft-lottery"\] :is\(\.draft-odds-grid, \.draft-reveal-grid\) \{ grid-template-rows: repeat\(var\(--lottery-rows, 7\), minmax\(0, 1fr\)\) !important; overflow: hidden !important; \}/);
  assert.match(css, /\[data-pages-slot="phase-draft-lottery"\] \.draft-reveal-row \{ height: auto !important; min-height: 0 !important; \}/);
});

test('the year-end slide counts the real lottery field', () => {
  assert.match(read('season-slideshow.js'), /Lottery position \$\{esc\(d\.lottery_position\)\} of \$\{esc\(d\.lottery_teams \?\? 14\)\}/);
});

test('the signing wire says why a free agent left, on a line that wraps', () => {
  assert.match(app, /\$\{kind === "signing" && move\.departure_text \? `<span class="fa-wire-why">\$\{escapeHtml\(sentenceCase\(move\.departure_text\)\)\}<\/span>` : ""\}/);
  assert.match(read('full-pages.css'), /\.fa-wire-row > div > span\.fa-wire-why \{ white-space: normal !important;/);
  const server = fs.readFileSync(path.join(gui, '../app_actions.py'), 'utf8');
  assert.match(server, /"departure_text": details\.get\("departure_text"\)/, 'the wire rows carry it');
});
