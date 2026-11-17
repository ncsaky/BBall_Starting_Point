// PO01: the playoff "league leaders" list becomes a sortable Playoff Stats table.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const css = fs.readFileSync(path.join(gui, 'card-board.css'), 'utf8');

function loadTable(stateOverrides = {}) {
  const escape = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const scope = {
    state: {data: {playoffs: {series: [], play_in: {}}, playoffLeaders: {leaders: []}}, ...stateOverrides},
    escapeHtml: escape,
    escapeAttr: escape,
    teamLabel: (team) => team?.abbrev || team,
    teamLogoSrc: (team) => `/logos/${team}.svg`,
    playoffBracket: () => '<div class="bracket"></div>',
    playerHeadshotMarkup: (row, className) => (row.is_prospect
      ? `<span class="player-headshot-frame prospect"><svg class="${className}"></svg></span>`
      : row.headshot_url ? `<span class="player-headshot-frame"><img class="${className}" src="${row.headshot_url}"></span>` : ''),
    wireDashboardPlayerCards: () => {},
  };
  vm.createContext(scope);
  const start = app.indexOf('function playoffDashboardWorkspace()');
  const end = app.indexOf('function draftDashboardWorkspace()');
  assert.ok(start >= 0 && end > start, 'playoff workspace slice found');
  vm.runInContext(`${app.slice(start, end)}\nglobalThis.cols = PLAYOFF_STATS_COLUMNS; globalThis.limit = PLAYOFF_STATS_LIMIT;`, scope);
  return scope;
}

const rows = [
  {player_id: 'a', player_name: 'Ana Guard', team_abbrev: 'BOS', games: 6, minutes_per_game: 35.2, points_per_game: 24.5, rebounds_per_game: 4.1, assists_per_game: 7.3, steals_per_game: 1.5, blocks_per_game: 0.2, fg3m_per_game: 3.1, fg_pct: 46.2, fg3_pct: 38.0, ft_pct: 91.0, headshot_url: 'https://img/a.png'},
  {player_id: 'b', player_name: 'Ben Center', team_abbrev: 'DEN', games: 4, minutes_per_game: 30.0, points_per_game: 28.0, rebounds_per_game: 12.5, assists_per_game: 2.0, steals_per_game: 0.5, blocks_per_game: 2.5, fg3m_per_game: 0, fg_pct: 61.0, fg3_pct: null, ft_pct: 70.0, player: {headshot_url: 'https://img/b.png'}},
  {player_id: 'c', player_name: 'Émile Wing', team_abbrev: 'ATL', games: 5, minutes_per_game: 20.0, points_per_game: 9.0, rebounds_per_game: 3.0, assists_per_game: 1.0, steals_per_game: 0.8, blocks_per_game: 0.4, fg3m_per_game: 1.2, fg_pct: 40.0, fg3_pct: 35.0, ft_pct: null},
];

test('columns cover the playoff line with per-game counting stats and shooting percentages', () => {
  const scope = loadTable();
  assert.deepEqual([...scope.cols].map((column) => column.label), ['Player', 'Team', 'GP', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG%', '3P%', 'FT%']);
  assert.ok(scope.cols.filter((column) => !column.text && column.key !== 'games' && !column.key.endsWith('_pct')).every((column) => column.key.endsWith('_per_game')));
  assert.ok(scope.limit >= 300, 'the card asks for every playoff player, not a top-nine list');
  assert.match(app, /action\("playoff_leaders", \{ \.\.\.savePayload\(\), stat: "points", limit: PLAYOFF_STATS_LIMIT \}\)/);
  assert.doesNotMatch(app, /playoffLeaderStat|data-playoff-leader-stat/);
  assert.match(app, /\["leaders", "\.phase-leaders-panel", "Playoff Stats"\]/);
});

test('default order is points per game, high to low', () => {
  const scope = loadTable();
  assert.deepEqual(scope.playoffStatsOrderedRows(rows, undefined).map((row) => row.player_id), ['b', 'a', 'c']);
  assert.deepEqual(scope.playoffStatsOrderedRows(rows, {key: 'bogus', direction: 'up'}).map((row) => row.player_id), ['b', 'a', 'c']);
});

test('any column sorts, header clicks toggle direction, and empty values stay last', () => {
  const scope = loadTable();
  let sort = scope.nextPlayoffStatsSort(undefined, 'assists_per_game');
  assert.deepEqual({...sort}, {key: 'assists_per_game', direction: 'desc'});
  assert.deepEqual(scope.playoffStatsOrderedRows(rows, sort).map((row) => row.player_id), ['a', 'b', 'c']);
  sort = scope.nextPlayoffStatsSort(sort, 'assists_per_game');
  assert.equal(sort.direction, 'asc');
  assert.deepEqual(scope.playoffStatsOrderedRows(rows, sort).map((row) => row.player_id), ['c', 'b', 'a']);
  // Ben has no three-point attempts: no percentage, bottom in both directions.
  for (const direction of ['desc', 'asc']) {
    assert.equal(scope.playoffStatsOrderedRows(rows, {key: 'fg3_pct', direction}).at(-1).player_id, 'b');
  }
  // Text columns start A-Z and ignore accents.
  sort = scope.nextPlayoffStatsSort(sort, 'player');
  assert.deepEqual({...sort}, {key: 'player', direction: 'asc'});
  assert.deepEqual(scope.playoffStatsOrderedRows(rows, sort).map((row) => row.player_id), ['a', 'b', 'c']);
  assert.deepEqual(scope.playoffStatsOrderedRows(rows, {key: 'team', direction: 'asc'}).map((row) => row.team_abbrev), ['ATL', 'BOS', 'DEN']);
});

test('table markup: sortable buttons with aria-sort, sorted-column cells, portraits and player-card links', () => {
  const scope = loadTable();
  const html = scope.playoffStatsTable(rows, {key: 'rebounds_per_game', direction: 'desc'});
  const headers = [...html.matchAll(/<th scope="col"[^>]*aria-sort="(\w+)"><button type="button" data-playoff-stats-sort="([\w]+)"/g)];
  assert.equal(headers.length, 13, 'every column header is a keyboard-reachable sort button');
  assert.deepEqual(headers.filter(([, aria]) => aria !== 'none').map(([, aria, key]) => [aria, key]), [['descending', 'rebounds_per_game']]);
  assert.equal((html.match(/playoff-stats-col-rebounds_per_game is-sorted/g) || []).length, 4, 'header plus every row cell is marked sorted');
  assert.match(html, /data-dashboard-player-card="b"[^>]*>.*?src="https:\/\/img\/b\.png"/);
  assert.match(html, /class="player-headshot-frame prospect"/, 'players without a portrait get the blank placeholder');
  const firstRow = html.slice(html.indexOf('<tbody>'));
  assert.match(firstRow, /^<tbody><tr data-playoff-stats-player="b">/);
  assert.match(firstRow, /<td class="playoff-stats-col-games">4<\/td>/, 'games played shows whole numbers');
  assert.match(firstRow, /<td class="playoff-stats-col-fg3_pct">—<\/td>/, 'no attempts shows a dash, not 0.0');
  assert.match(firstRow, /<td class="playoff-stats-col-points_per_game">28\.0<\/td>/);
});

test('workspace renders the table in the existing leaders card slot, with an empty state', () => {
  const scope = loadTable();
  const empty = scope.playoffDashboardWorkspace();
  assert.match(empty, /<aside class="phase-leaders-panel playoff-stats-panel" data-playoff-stats>/);
  assert.match(empty, /Playoff stats appear after the first playoff game\./);
  const filled = loadTable({data: {playoffs: {series: []}, playoffLeaders: {leaders: rows}}, playoffStatsSort: {key: 'ft_pct', direction: 'desc'}}).playoffDashboardWorkspace();
  assert.match(filled, /aria-sort="descending"><button type="button" data-playoff-stats-sort="ft_pct"/);
});

test('table styling follows the shared table preferences', () => {
  const block = css.slice(css.indexOf('/* Playoff Stats card'));
  assert.ok(block.length > 100);
  assert.match(block, /thead th \{[^}]*border-bottom:1px solid var\(--season-line\)[^}]*font-size:8px; font-weight:700;/, 'small bold header with a rule');
  assert.match(block, /tbody tr:first-child > :is\(th,td\) \{ border-top:1px solid var\(--season-soft-line\); \}/, 'second rule makes the double header border');
  assert.match(block, /tbody tr:nth-child\(even\) \{ background-color:#eef1f3; \}/, 'alternating rows');
  assert.match(block, /tbody tr:is\(:hover,:focus-within\) \{ background-color:#dce8f2; \}/, 'whole-row hover');
  assert.match(block, /tbody :is\(th,td\)\.is-sorted \{ background-color:/, 'sorted column shading');
  assert.match(block, /\.player-headshot-frame \{[^}]*position:absolute; left:2px; bottom:0;[^}]*height:100%;/, 'portrait sits on the row bottom and fills its height');
});
