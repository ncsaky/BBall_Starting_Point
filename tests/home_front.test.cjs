// Home › Today as a front page (UI polish pass, 2026-11-26): what it shows comes from data the game already holds.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

const team = (abbrev, conference, wins, losses, diff = 0) => ({team_abbrev: abbrev, team_id: `team_${abbrev.toLowerCase()}`, team: {abbrev, conference}, wins, losses, games: wins + losses, win_pct: wins / Math.max(1, wins + losses), point_diff: diff});

function load(state) {
  const context = {window: {}, state};
  vm.createContext(context);
  vm.runInContext(read('home-front.js'), context);
  return context.window.HomeFront;
}

const season = () => ({
  currentSave: 'save_1',
  home: {
    save: {current_date: '2026-12-25', user_team: {abbrev: 'OKC'}, pending_counts: {user_trade_offers: 2}},
    league_events: {events: [{id: 'e1', date: '2026-12-17', kind: 'trade', headline: 'HOU and CHA <swap> players'}]},
  },
  data: {
    statusDashboard: {
      last_games: [{date: '2026-12-25', result: 'W', points: 131, opponent_points: 96, opponent_team_id: 'team_sas', is_home: true, game_id: 'g9'}],
      next_games: [{date: '2026-12-28', opponent_team: 'PHI', is_home: true}],
      health_summary: {unavailable_player_ids: ['p1']},
      rotation: [{id: 'p1', name: 'Ajay Mitchell'}, {id: 'p2', name: 'Chet Holmgren'}],
    },
    dashboardStandings: {standings: [team('OKC', 'West', 26, 5, 200), team('MIN', 'West', 24, 7, 90), team('GSW', 'West', 20, 11, 30), team('PHI', 'East', 16, 12, 5), team('HOU', 'West', 10, 18, -40), team('BOS', 'East', 3, 2, 9)]},
    dashboardTrends: {roster_ranks: [['okc', 1], ['min', 2], ['gsw', 6], ['phi', 4], ['hou', 1], ['bos', 3]].map(([id, rank]) => ({team_id: `team_${id}`, rank}))},
    dashboardCalendar: {games: [
      {date: '2026-12-25', status: 'simulated', away_team: 'SAS', away_score: 96, home_team: 'OKC', home_score: 131, game_id: 'g9'},
      {date: '2026-12-23', status: 'simulated', away_team: 'OKC', away_score: 124, home_team: 'PHX', home_score: 116, game_id: 'g8'},
      {date: '2026-12-28', status: 'scheduled', away_team: 'PHI', home_team: 'OKC'},
    ]},
    dashboardMorale: {team_morale: {overall: 98}, owner_confidence: 55, fan_confidence: 73, players: [{morale: {overall: 60}}, {morale: {overall: 72}}]},
    dashboardOffers: {offer_count: 2},
    dashboardSummaryLeaders: {fields: [{key: 'points', label: 'PTS', leaders: [{player_id: 'a', player_name: 'Anthony Edwards', team_abbrev: 'MIN', value: 29.2}, {player_id: 'b', player_name: 'Giannis Antetokounmpo', team_abbrev: 'MIA', value: 27.1}]}]},
    tradeMarket: {shopped: [{player_name: 'Trae Young', team: 'WAS', overall: 77.2, interested_count: 5, stage: 'taking offers'}]},
  },
});

test('the table: seeds by conference, games behind the leader, and a league rank by record', () => {
  const front = load(season());
  const league = front.table(season());
  const by = Object.fromEntries(Array.from(league, (row) => [row.abbrev, row]));
  assert.equal(by.OKC.seed, 1);
  assert.equal(by.MIN.seed, 2);
  assert.equal(by.MIN.behind, 2);
  assert.equal(by.HOU.seed, 4);
  assert.equal(by.PHI.seed, 2, 'BOS (3-2) has the better record in the East');
  assert.equal(by.OKC.leagueRank, 1);
});

test('against expectation: record rank against roster rank, only after ten games and a gap of four places', () => {
  const state = season();
  const front = load(state);
  const found = front.surprises(state, front.table(state));
  assert.deepEqual(Array.from(found.under, (row) => row.abbrev), ['HOU'], 'the best roster with the worst record');
  assert.deepEqual(Array.from(found.over, (row) => row.abbrev), [], 'nobody is four places above their roster');
  assert.ok(!Array.from(found.under).some((row) => row.abbrev === 'BOS'), 'five games is too few to judge');
});

test('the page: your team now, then the league, the table and the market; text is escaped; every line leads somewhere', () => {
  const html = load(season()).markup();
  assert.match(html, /Last game/);
  assert.match(html, /131–96/);
  assert.match(html, /data-front-box="g9"/, 'the last game opens its box score');
  assert.match(html, /Next game/);
  assert.match(html, /1 out/);
  assert.match(html, /data-front-player="p1"[^>]*>Ajay Mitchell/);
  assert.match(html, /Locker room[\s\S]*<b>66<\/b>/, 'the average of the players');
  assert.match(html, /HOU and CHA &lt;swap&gt; players/, 'escaped');
  assert.match(html, /Scores <small>[^<]*<\/small>/);
  assert.equal((html.match(/class="front-scoreline"/g) || []).length, 1, 'only the latest day that was played');
  assert.match(html, /data-front-go="standings">West/);
  assert.match(html, /Against expectation/);
  assert.match(html, /data-front-offers><b>2<\/b> offers waiting/);
  assert.match(html, /Trae Young <i>77<\/i>/);
  assert.match(html, /5 teams interested/);
  assert.match(html, /Anthony Edwards[\s\S]*29\.2[\s\S]*Antetokounmpo <i>27\.1<\/i>/);
  assert.match(html, /data-front-cols="3"/);
});

test('with no table yet (before the season) the middle column lists the games ahead; with nothing it is left out', () => {
  const state = season();
  state.data.dashboardStandings = null;
  state.data.dashboardTrends = null;
  let html = load(state).markup();
  assert.match(html, /Coming up/);
  assert.doesNotMatch(html, /Against expectation/);
  state.data.statusDashboard.next_games = [];
  html = load(state).markup();
  assert.match(html, /data-front-cols="2"/);
});

test('the front page is wired in, and its numbers come from the game', () => {
  assert.match(read('index.html'), /<script src="\/home-front\.js\?v=[^"]+" defer><\/script>/);
  assert.match(read('index.html'), /href="\/home-front\.css\?v=/);
  const server = fs.readFileSync(path.join(gui, '../app_actions.py'), 'utf8');
  assert.match(server, /"roster_ranks": \[/, 'every team’s roster rank, from team_identity_report');
  assert.match(server, /"headshot_url": item\.get\("headshot_url"\)/, 'the leaders carry their faces');
  const source = read('home-front.js');
  assert.doesNotMatch(source, /Math\.random|eval\(/);
  assert.match(source, /call\("loadTradeMarket", true\)/, 'the market is asked for, once a game day');
});

test('the front page sheet touches only full-size pages and reads the shared values', () => {
  const css = read('home-front.css');
  for (const rule of css.split('\n').filter((line) => /\{/.test(line) && !/^\s*(\/\*|@|--|[a-z-]+:)/.test(line) && !line.startsWith(' '))) {
    assert.match(rule, /\.is-full/, rule.slice(0, 90));
  }
  assert.doesNotMatch(css.replace(/rgba?\([^)]*\)/g, ''), /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d|#[0-9a-f]{3,8}\b/i);
});
