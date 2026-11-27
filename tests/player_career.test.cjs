// A player's first tab (UI polish pass, 2026-11-27): his career, his contract as one row, things to watch and his
// projected overall by age; the heat maps on a tab of their own. And League > Storylines.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

function load(state = {}, extra = {}) {
  const context = {window: {}, state, ...extra};
  vm.createContext(context);
  vm.runInContext(read('player-career.js'), context);
  return context.window.PlayerCareer;
}

const career = [
  {season: '2025-26', team_abbrevs: ['OKC'], games: 60, mpg: 30, ppg: 30, rpg: 5, apg: 6, spg: 1.5, bpg: 0.5, topg: 2, fg_pct: 50, fg3_pct: 40, ft_pct: 90, playoffs: {games: 10, mpg: 40, ppg: 28, rpg: 6, apg: 7, spg: 2, bpg: 1, topg: 3, fg_pct: 45, fg3_pct: 35, ft_pct: 88}},
  {season: '2024-25', team_abbrevs: ['LAC', 'OKC'], games: 20, mpg: 18, ppg: 9, rpg: 2, apg: 2, spg: 0.5, bpg: 0.1, topg: 1, fg_pct: 40, fg3_pct: 30, ft_pct: 80},
];

test('career rows: oldest season first, a career line weighted by games; per 36 scales the counting numbers only', () => {
  const page = load();
  const game = page.careerRows(career, 'regular', 'game');
  assert.deepEqual(Array.from(game.rows, (row) => row.season), ['2024-25', '2025-26']);
  assert.equal(game.total.games, 80);
  assert.equal(game.total.counting[0].toFixed(2), ((9 * 20 + 30 * 60) / 80).toFixed(2), 'points a game, by games');
  assert.equal(game.total.shooting[0].toFixed(1), ((40 * 20 + 50 * 60) / 80).toFixed(1));
  const per36 = page.careerRows(career, 'regular', 'per36');
  assert.equal(per36.rows[0].counting[0].toFixed(1), '18.0', '9 points in 18 minutes is 18 per 36');
  assert.equal(per36.rows[1].counting[0].toFixed(1), '36.0');
  assert.equal(per36.rows[1].shooting[0], 50, 'a percentage is not scaled');
  assert.equal(per36.total.counting[0].toFixed(2), ((18 * 20 * 18 + 36 * 60 * 30) / (20 * 18 + 60 * 30)).toFixed(2), 'by minutes');
});

test('playoffs show only the seasons he played in them; none says so', () => {
  const page = load();
  const playoffs = page.careerRows(career, 'playoffs', 'game');
  assert.deepEqual(Array.from(playoffs.rows, (row) => [row.season, row.games, row.counting[0]]), [['2025-26', 10, 28]]);
  page.view.scope = 'playoffs';
  assert.match(page.careerTable([career[1]]), /No playoff games yet\./);
  page.view.scope = 'regular';
  const html = page.careerTable(career);
  assert.match(html, /<th scope="row">24-25<\/th>\s*<td class="pp-team">2 teams<\/td>/, 'a season with two teams says so');
  assert.match(html, /<tr class="is-career"><th scope="row">Career<\/th>/);
});

test('the contract is one row, a season a column, then the first year he is a free agent and the total', () => {
  const page = load();
  const html = page.contractRow({salary_seasons: [{season: '2026-27', salary_millions: 40.8}, {season: '2027-28', salary_millions: 61}, {season: '2028-29', salary_millions: null}, {season: '2029-30', salary_millions: null}]});
  assert.match(html, /<small>26-27<\/small><b>\$40\.8M<\/b>/);
  assert.match(html, /<small>28-29<\/small><b>Free agent<\/b>/);
  assert.doesNotMatch(html, /29-30/, 'only the first free year');
  assert.match(html, /<small>2 seasons<\/small><b>\$101\.8M<\/b>/);
  assert.match(page.contractRow({salary_seasons: []}), /No contract\./);
});

test('things to watch: the storylines about him, then plain facts; text is escaped', () => {
  const state = {home: {save: {current_date: '2026-12-25', user_team: {abbrev: 'OKC'}}}, data: {statusDashboard: {rotation: [{id: 'p1', extension_eligible: true}]}}};
  const threads = [
    {kind: 'player', id: 'p1', closed: false, steps: [{date: '2026-08-01', text: 'Asked out of <PHI>'}, {date: '', text: 'On the market'}]},
    {kind: 'player', id: 'p2', closed: false, steps: [{date: '2026-08-02', text: 'Someone else'}]},
  ];
  const page = load(state, {HomeFront: {storylines: () => threads}, declineWatchApplies: (row) => Number(row.decline_watch?.per_year) <= -0.1, formatDashboardShortDate: (iso) => `d${iso.slice(5)}`});
  const html = page.watch({player_id: 'p1', salary_seasons: [{season: '2026-27', salary_millions: 5}], decline_watch: {per_year: -0.43}, upside_remaining: 0, injury_body_map: {expected_games_total: 30, typical_games_total: 22}});
  assert.match(html, /<time>d08-01<\/time><span>Asked out of &lt;PHI&gt;<\/span>/);
  assert.match(html, /<time>Now<\/time><span>On the market<\/span>/);
  assert.doesNotMatch(html, /Someone else/);
  assert.match(html, /In the last season of his contract/);
  assert.match(html, /Can sign an extension now/);
  assert.match(html, /Ratings expected to slip about 0\.4 a year/);
  assert.match(html, /class="is-bad"><time>Health<\/time><span>About 30 games a season lost to injury \(a typical player: 22\)/);
  assert.match(page.watch({player_id: 'p9', salary_seasons: [{season: 'a', salary_millions: 1}, {season: 'b', salary_millions: 1}]}), /Nothing out of the ordinary\./);
});

test('projected overall by age: the middle line, its range, ages along the bottom; nothing when there is no data', () => {
  const page = load();
  const html = page.outlookChart([{age: 28, overall: 94.9, low: 94.9, high: 94.9}, {age: 29, overall: 94.6, low: 93.8, high: 95.2}, {age: 30, overall: 93.4, low: 92, high: 94.5}]);
  assert.match(html, /<svg class="pp-outlook-chart"/);
  assert.match(html, /class="pp-band"/);
  assert.match(html, /aria-label="Projected overall from 94\.9 at age 28 to 93\.4 at age 30"/);
  assert.equal((html.match(/class="pp-dot"/g) || []).length, 3);
  assert.match(page.outlookChart([]), /No projection for this player\./);
});

test('the page is wired in: career first on a page, the heat maps on their own tab, the projection from the game', () => {
  const app = read('app.js');
  assert.match(app, /const careerFirst = !detail\.is_prospect && Boolean\(globalThis\.CardPages\?\.enabled\?\.\(\)\) && Boolean\(globalThis\.PlayerCareer\);/, 'prospects and the floating card keep their page');
  assert.match(app, /data-page-title="Career, Contract & Outlook"[^>]*>\s*\$\{globalThis\.PlayerCareer\.page\(detail\)\}/);
  assert.match(app, /class="player-card-page player-card-page--overview player-card-page--hotspots" data-player-page="\$\{pageOffset \+ 1\}" data-page-title="Hotspots"/);
  assert.match(app, /data-player-page="\$\{pageOffset \+ 1 \+ careerShift\}" data-page-title="Ratings & Profiles"/);
  assert.match(read('index.html'), /<script src="\/player-career\.js\?v=[^"]+" defer><\/script>/);
  const server = fs.readFileSync(path.join(gui, '../app_actions.py'), 'utf8');
  const payload = server.slice(server.indexOf('def player_outlook_payload('), server.indexOf('def home_storylines_payload('));
  assert.match(server, /if action == "player_outlook":\n\s+return player_outlook_payload\(canonical, save_path, str\(payload\.get\("player_id"\) or ""\)\)/);
  assert.match(payload, /ability_projection\(active, player, start, start \+ 5\)/, 'the same scenario model the extension page shows');
  assert.doesNotMatch(payload, /write_save|save_save|json\.dump|random\./);
  assert.match(read('player-career.js'), /call\("action", "player_outlook", \{\.\.\.\(call\("savePayload"\) \|\| \{\}\), player_id: id\}\)/);
});

test('the extension page has a close state: a no within a tenth of his price is amber, and still a no', () => {
  const app = read('app.js');
  assert.match(app, /return preview\?\.verdict\?\.tone === "no" && Number\.isFinite\(preview\.price\) && Number\(preview\.ratio\) >= 0\.9 && Number\(preview\.ratio\) < 1;/);
  assert.match(app, /fa-verdict-\$\{preview\.verdict\.tone\}\$\{extensionVerdictClose\(preview\) \? " is-close" : ""\}/);
  assert.match(app, /extensionVerdictClose\(preview\) \? "Close, but he says no" : verdict\.headline/);
  assert.match(read('extension-window.css'), /\.fa-verdict-no\.is-close \.fa-verdict-line > strong::before \{ background: var\(--gm-warn\) !important; \}/);
});

// ---------- League > Storylines
function loadFront(state) {
  const context = {window: {}, state};
  vm.createContext(context);
  vm.runInContext(read('home-front.js'), context);
  return context.window.HomeFront;
}
const storyState = () => ({
  currentSave: 's', home: {save: {current_date: '2026-12-25', user_team: {abbrev: 'OKC'}}, league_events: {events: []}},
  data: {homeStories: {date: '2026-12-25',
    streaks: [{team: 'MIN', result: 'W', length: 14, since: '2026-11-26'}, {team: 'OKC', result: 'W', length: 7, since: '2026-12-10'}],
    hot_seats: [{team: 'SAC', name: 'Doug <Christie>', games: 30, wins_vs_expected_per_82: -28}],
    talks: [
      {key: 'a|b|star', player: {player_id: 'star', name: 'Star Player', overall: 92, position: 'SF', age: 27}, buyer: 'LAL', seller: 'DEN', opened: '2026-12-01', status: 'open', rounds: [{date: '2026-12-01', offer: {LAL: ['x']}}, {date: '2026-12-10', offer: {LAL: ['x']}}, {date: '2026-12-17', offer: {LAL: ['x']}}]},
      {key: 'c|d|bench', player: {player_id: 'bench', name: 'Bench Player', overall: 70, position: 'PG', age: 25}, buyer: 'UTA', seller: 'CLE', opened: '2026-12-01', status: 'open', rounds: [{date: '2026-12-01', offer: {UTA: ['y']}}, {date: '2026-12-10', offer: {UTA: ['y']}}, {date: '2026-12-17', offer: {UTA: ['y']}}]},
    ]}},
});

test('a star leads a deep-bench player when both rumors are at the same stage', () => {
  const state = storyState();
  const threads = Array.from(loadFront(state).storylines(state, 'OKC'));
  const star = threads.find((entry) => entry.key === 'player:star'), bench = threads.find((entry) => entry.key === 'player:bench');
  assert.ok(star.score > bench.score);
  assert.ok(threads.indexOf(star) < threads.indexOf(bench));
});

test('the Storylines page lists every storyline, filters them, and shows the chosen one\'s whole history', () => {
  const state = storyState();
  const front = loadFront(state);
  let html = front.storiesPage();
  assert.equal((html.match(/class="stories-row[ "]/g) || []).length, 5);
  assert.match(html, /data-story-filter="all" aria-selected="true">All<small>5<\/small>/);
  assert.match(html, /data-story-filter="mine" aria-selected="false">Your team<small>1<\/small>/);
  assert.match(html, /data-story-filter="streak"[^>]*>Streaks<small>2<\/small>/);
  assert.doesNotMatch(html, /data-story-filter="injury"/, 'no filter for a kind with nothing in it');
  assert.match(html, /Doug &lt;Christie&gt;/, 'escaped');
  // The first row is chosen by default: yours (the winning streak).
  assert.match(html, /<article class="stories-detail"[^>]*><header class="stories-detail-head">[\s\S]*<h2>OKC<\/h2>/);
  front.board.key = 'player:star';
  html = front.storiesPage();
  assert.match(html, /<h2>Star Player<\/h2>/);
  assert.equal((html.match(/<li class="/g) || []).length, 3, 'every step of it, not the last three only');
  assert.match(html, /class="is-latest"><time>2026-12-17<\/time><span>It is Star Player<\/span>/);
  assert.match(html, /class="stories-open" data-front-player="star">His page/);
  front.board.filter = 'staff';
  html = front.storiesPage();
  assert.equal((html.match(/class="stories-row[ "]/g) || []).length, 1);
  front.board.filter = 'all'; front.board.key = '';
});

test('the Storylines page is a League tab, and a storyline on Home opens it there', () => {
  assert.match(read('card-pages.js'), /\{id: "storylines", group: "league", label: "Storylines", layout: \(\) => \(\{full: \{fits: \[1100, 600\], roomy: \[1500, 900\]\}, \.\.\.row\(card\("storylines", \{bare: true, fill: true\}\)\)\}\)\}/);
  assert.match(read('card-board.js'), /\["storylines", "\.season-stories-panel", "Storylines"\]/);
  assert.match(read('app.js'), /season-stories-panel">\$\{globalThis\.CardPages\?\.enabled\?\.\(\) \? globalThis\.HomeFront\?\.storiesPage\?\.\(\)/);
  const source = read('home-front.js');
  assert.match(source, /const action = `data-front-story="\$\{esc\(entry\.key\)\}"`;/);
  assert.match(source, /board\.key = story\.dataset\.frontStory; globalThis\.CardPages\?\.go\?\.\("storylines"\); paintStories\(\);/);
  assert.match(source, /<h2><button type="button" data-front-go="storylines">Storylines<\/button><\/h2>/);
});
