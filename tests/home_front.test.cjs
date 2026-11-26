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

// ---------- Storylines: threads of things the game already recorded, in date order.
const storyState = () => {
  const state = season();
  const subject = (id, name) => ({subjects: [{id, kind: 'player', name, headshot_url: `/faces/${id}.png`}]});
  state.home.league_events.events = [
    {id: 'a', date: '2026-08-01', kind: 'trade_demand', team_ids: ['team_phi'], player_ids: ['p_brown'], details: {player_id: 'p_brown', team_id: 'team_phi', is_trade_demand: true}, activity_groups: [subject('p_brown', 'Jaylen <b>Brown</b>')]},
    {id: 'b', date: '2026-12-20', kind: 'trade', team_ids: ['team_phi', 'team_bos'], player_ids: ['p_brown', 'p_x'], details: {from_team_id: 'team_phi', to_team_id: 'team_bos', from_assets: [{id: 'p_brown', kind: 'player'}], to_assets: [{id: 'p_x', kind: 'player'}]}},
    {id: 'c', date: '2026-10-20', kind: 'extension', team_ids: ['team_sac'], player_ids: ['p_lavine'], details: {player_id: 'p_lavine', team_id: 'team_sac', reason: 'unresolved'}, activity_groups: [subject('p_lavine', 'Zach LaVine')]},
    {id: 'd', date: '2026-10-21', kind: 'extension', team_ids: ['team_orl'], player_ids: ['p_bane'], details: {player_id: 'p_bane', team_id: 'team_orl', reason: 'unresolved'}, activity_groups: [subject('p_bane', 'Desmond Bane')]},
    {id: 'e', date: '2026-12-01', kind: 'staff_fire', team_ids: ['team_dal'], player_ids: [], details: {slot: 'head_coach', staff_id: 's1', staff_name: 'Dusty May', reason: 'tracking 14 wins below expectations.'}},
    {id: 'f', date: '2026-12-12', kind: 'staff_hire', team_ids: ['team_dal'], player_ids: [], details: {slot: 'head_coach', staff_id: 's2', staff_name: 'New Coach'}},
    {id: 'g', date: '2026-11-01', kind: 'staff_hire', team_ids: ['team_min'], player_ids: [], details: {slot: 'head_coach', staff_name: 'Kept Coach', action: 'retain'}},
  ];
  state.data.tradeMarket = {shopped: [
    {player_id: 'p_lavine', player_name: 'Zach LaVine', team: 'SAC', interested_count: 4, stage: 'bidding war', started: '2026-12-10', decide_by: '2026-12-30'},
    {player_id: 'p_young', player_name: 'Trae Young', team: 'WAS', interested_count: 5, stage: 'taking offers', started: '2026-12-15'},
  ]};
  state.data.dashboardSummaryLeaders.award_races = {MVP: [
    {rank: 1, previous_week_rank: 2, player_id: 'p_g', player_name: 'Giannis', team_abbrev: 'MIA'},
    {rank: 2, previous_week_rank: 1, player_id: 'p_w', player_name: 'Wembanyama', team_abbrev: 'SAS'},
  ]};
  state.data.dashboardMorale.players = [
    {player: {id: 'p1', name: 'Ajay Mitchell'}, morale: {overall: 41, role_satisfaction: 30, contract_satisfaction: 60, team_confidence: 70}},
    {player: {id: 'p2', name: 'Chet Holmgren'}, morale: {overall: 80, role_satisfaction: 85, contract_satisfaction: 60, team_confidence: 70}},
  ];
  return state;
};

test('storylines: a thread follows one person or job from its start to its end, in date order', () => {
  const state = storyState();
  const threads = Array.from(load(state).storylines(state, 'OKC'));
  const by = Object.fromEntries(threads.map((thread) => [thread.key, thread]));
  const steps = (key) => Array.from(by[key].steps, (step) => `${step.date} ${step.text}`);
  assert.deepEqual(steps('player:p_brown'), ['2026-08-01 Asked out of PHI', '2026-12-20 Traded to BOS'], 'the demand, then where he went');
  assert.equal(by['player:p_brown'].closed, true);
  assert.equal(by['player:p_brown'].status, 'Traded');
  assert.deepEqual(steps('player:p_lavine'), ['2026-10-20 Extension talks with SAC stalled', '2026-12-10 Bidding war, 4 teams']);
  assert.equal(by['player:p_lavine'].status, 'Bidding war');
  assert.deepEqual(steps('staff:DAL:head_coach'), ['2026-12-01 Fired Dusty May (tracking 14 wins below expectations)', '2026-12-12 Hired New Coach']);
  assert.equal(by['staff:DAL:head_coach'].status, 'Filled');
  assert.equal(by['staff:MIN:head_coach'], undefined, 'a coach kept is not a story, and a hire with no firing starts none');
  assert.match(steps('award:MVP')[0], /Giannis took the lead from Wembanyama this week/);
});

test('storylines: routine things alone are not stories; your own players come first', () => {
  const state = storyState();
  const threads = Array.from(load(state).storylines(state, 'OKC'));
  const keys = threads.map((thread) => thread.key);
  assert.ok(!keys.includes('player:p_bane'), 'talks that stalled and nothing since');
  assert.ok(!keys.includes('player:p_young'), 'on the market and nothing else: the market list already shows him');
  assert.ok(!keys.includes('player:p2'), 'a content player');
  assert.equal(threads[0].key, 'player:p1', 'the unhappy player on your team leads');
  assert.match(threads[0].steps[0].text, /Unhappy with his role right now \(30 of 100\)/);
  assert.equal(threads[0].steps[0].date, '', 'the game keeps no history of morale, so the step has no date');
  assert.equal(threads[0].mine, true);
});

test('storylines on the page: dated steps, escaped names, a decision date only while it is ahead', () => {
  const state = storyState();
  const html = load(state).markup();
  assert.match(html, /<h2>Storylines<\/h2>/);
  assert.match(html, /Jaylen &lt;b&gt;Brown&lt;\/b&gt;/);
  assert.match(html, /<time>Now<\/time><span>Unhappy with his role/);
  assert.match(html, /Bidding war, 4 teams, decision by 2026-12-30/);
  state.home.save.current_date = '2027-01-05';
  assert.doesNotMatch(load(state).markup(), /decision by/);
  const empty = season();
  empty.data.tradeMarket = {shopped: []};
  assert.doesNotMatch(load(empty).markup(), /<h2>Storylines<\/h2>/, 'no block when there is no story');
});

