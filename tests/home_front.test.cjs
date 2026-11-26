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

// ---------- Storylines from the home_storylines action: trade talks that reveal more each round, bidding, streaks,
// key injuries, coaches under pressure.
const talk = (rounds, extra = {}) => ({key: 'hou|sac|p_murray', player: {player_id: 'p_murray', name: 'Keegan Murray', headshot_url: '/m.png', team: 'SAC'}, buyer: 'HOU', buyer_conference: 'West', seller: 'SAC', opened: '2026-11-27', status: 'open', rounds, ...extra});
const round = (date, offer, final_by = []) => ({date, offer: {HOU: offer, SAC: ['Keegan Murray']}, final_by});
const quiet = () => {
  const state = season();
  state.home.league_events.events = [];
  state.data.tradeMarket = {shopped: []};
  state.data.dashboardMorale.players = [];
  return state;
};
const lines = (state, key) => {
  const thread = Array.from(load(state).storylines(state, 'OKC')).find((item) => item.key === key);
  return thread ? {status: thread.status, name: thread.name, closed: thread.closed, steps: Array.from(thread.steps, (step) => `${step.date} ${step.text}`)} : null;
};

test('trade talks reveal a piece at a time: two teams, a hint, the player, the offer, then the end', () => {
  const state = quiet();
  const eason = ['Tari Eason'];
  state.data.homeStories = {date: '2026-12-25', talks: [talk([round('2026-11-27', eason)])]};
  const first = lines(state, 'talks:hou|sac|p_murray');
  assert.deepEqual(first.steps, ['2026-11-27 HOU and SAC opened trade talks']);
  assert.equal(first.name, 'HOU and SAC', 'the player is not named yet');
  assert.doesNotMatch(load(state).markup(), /Keegan Murray/, 'and he is nowhere on the page');

  // Round two: a hint only (his position, and young or veteran), still under the two teams' names.
  state.data.homeStories.talks = [talk([round('2026-11-27', eason), round('2026-12-10', eason)], {player: {player_id: 'p_murray', name: 'Keegan Murray', position: 'PF', age: 23, team: 'SAC'}})];
  const second = lines(state, 'talks:hou|sac|p_murray');
  assert.deepEqual(second.steps, ['2026-11-27 HOU and SAC opened trade talks', '2026-12-10 The talks are about a young forward on SAC']);
  assert.doesNotMatch(load(state).markup(), /Keegan Murray/);

  // Round three: the name. The offer waits one more round.
  state.data.homeStories.talks = [talk([round('2026-11-27', eason), round('2026-12-10', eason), round('2026-12-17', eason)], {player: {player_id: 'p_murray', name: 'Keegan Murray', position: 'C', age: 33, team: 'SAC'}})];
  const third = lines(state, 'player:p_murray');
  assert.deepEqual(third.steps, ['2026-11-27 HOU and SAC opened trade talks', '2026-12-10 The talks are about a veteran center on SAC', '2026-12-17 It is Keegan Murray']);
  assert.equal(third.name, 'Keegan Murray');

  state.data.homeStories.talks = [talk([round('2026-11-27', eason), round('2026-12-10', eason), round('2026-12-17', eason), round('2026-12-20', ['Tari Eason', 'Steven Adams', '2027 R1: HOU receives the more favourable of HOU/BKN'])])];
  assert.equal(lines(state, 'player:p_murray').steps.at(-1), '2026-12-20 HOU has offered Tari Eason and Steven Adams and 1 more');
  assert.equal(lines(state, 'player:p_murray').status, 'Offer made');

  // A falling-out before the name ever came out stays anonymous.
  state.data.homeStories.talks = [talk([round('2026-11-27', eason), round('2026-12-10', eason, ['HOU'])], {status: 'dead', ended: {date: '2026-12-10', final_by: ['HOU']}})];
  const dead = lines(state, 'talks:hou|sac|p_murray');
  assert.equal(dead.steps.at(-1), "2026-12-10 Talks broke off: HOU's final offer was refused");
  assert.equal(dead.status, 'Fell apart');
  assert.equal(dead.closed, true);
  assert.doesNotMatch(load(state).markup(), /Keegan Murray/);

  state.data.homeStories.talks = [talk([round('2026-11-27', eason)], {status: 'closed', outcome: 'traded', closed_date: '2026-11-27'})];
  assert.equal(lines(state, 'player:p_murray').steps.at(-1), '2026-11-27 Done: Keegan Murray to HOU');
});

test('a sale in the open: first only which conference leads, then the team and its offer, then the end', () => {
  const state = quiet();
  const sale = (extra) => ({player: {player_id: 'p_cj', name: 'Cameron Johnson', team: 'DEN'}, seller: 'DEN', started: '2026-12-17', status: 'bidding', decide_by: '2026-12-30', interested: ['LAL'], bids: [{date: '2026-12-17', leader: 'LAL', leader_conference: 'West', offer: {LAL: ['Jarred Vanderbilt', 'Kevon Looney']}}], ...extra});
  state.data.homeStories = {date: '2026-12-25', shopped: [sale({})]};
  assert.deepEqual(lines(state, 'player:p_cj').steps, ['2026-12-17 Put on the market by DEN', '2026-12-17 A team from the West leads the bidding']);
  state.data.homeStories.shopped = [sale({status: 'sold', sold_date: '2026-12-22', winner: 'LAL'})];
  assert.equal(lines(state, 'player:p_cj').steps.at(-1), '2026-12-22 Sold to LAL for Jarred Vanderbilt and Kevon Looney');
  state.data.homeStories.shopped = [sale({status: 'lapsed', bids: []})];
  assert.equal(lines(state, 'player:p_cj').steps.at(-1), '2026-12-30 No deal: DEN kept him');
});

test('streaks, key injuries and coaches under pressure are storylines; minor injuries are not', () => {
  const state = quiet();
  state.data.homeStories = {date: '2026-12-25',
    streaks: [{team: 'MIN', result: 'W', length: 14, since: '2026-11-26'}, {team: 'BOS', result: 'W', length: 9, since: '2026-12-01', ended: '2026-12-23', ended_by: 'MIA'}],
    injuries: [
      {player: {player_id: 'p_jokic', name: 'Nikola Jokic', team: 'DEN'}, start_date: '2026-12-20', return_date: '2027-01-30', returned: false, diagnosis: 'shoulder injury', expected_games_missed: 19},
      {player: {player_id: 'p_minor', name: 'Bradley Beal', team: 'LAC'}, start_date: '2026-12-23', return_date: '2027-01-12', returned: false, diagnosis: 'plantar fasciitis', expected_games_missed: 9},
      {player: {player_id: 'p_young', name: 'Trae Young', team: 'WAS'}, start_date: '2026-12-21', return_date: '2028-05-02', returned: false, diagnosis: 'ACL tear', expected_games_missed: 201},
    ],
    hot_seats: [{team: 'SAC', name: 'Doug Christie', games: 30, wins_vs_expected_per_82: -28.2}]};
  assert.deepEqual(lines(state, 'streak:MIN'), {status: '14 straight wins', name: 'MIN', closed: false, steps: ['2026-11-26 First of 14 straight wins']});
  assert.deepEqual(lines(state, 'streak:BOS').steps, ['2026-12-01 First of 9 straight wins', '2026-12-23 Beaten by MIA']);
  assert.equal(lines(state, 'streak:BOS').status, 'Streak over');
  assert.deepEqual(lines(state, 'player:p_jokic').steps, ['2026-12-20 Out: shoulder injury, about 19 games', '2027-01-30 Expected back']);
  assert.equal(lines(state, 'player:p_jokic').status, 'Out', 'a return date still ahead is not where it stands');
  assert.deepEqual(lines(state, 'player:p_young').steps, ['2026-12-21 Out for the season: ACL tear']);
  assert.equal(lines(state, 'player:p_minor'), null, 'nine games is routine');
  assert.deepEqual(lines(state, 'staff:SAC:head_coach').steps, [' Doug Christie: on pace for 28 fewer wins than expected, 30 games in']);
  assert.equal(lines(state, 'staff:SAC:head_coach').status, 'Hot seat');
});

test('the block shows a mix: at most two of a kind, unless they are yours', () => {
  const state = quiet();
  state.data.homeStories = {date: '2026-12-25', hot_seats: ['SAC', 'ORL', 'MIL', 'DEN'].map((team, index) => ({team, name: `Coach ${index}`, games: 30, wins_vs_expected_per_82: -20 + index})),
    streaks: [{team: 'MIN', result: 'W', length: 14, since: '2026-11-26'}]};
  const html = load(state).markup();
  assert.equal((html.match(/Hot seat/g) || []).length, 2);
  assert.match(html, /14 straight wins/);
});

test('in the offseason the front page leads with the payroll and the roster, and lists the biggest deals', () => {
  const state = quiet();
  state.home.save.phase = 'offseason';
  state.data.statusDashboard.cap_summary = {salary_total_millions: 222, tax_space_millions: -14.5, cap_room_millions: -54.5, hard_cap_space_millions: 7.5, ledger: {empty_roster_spots: 2}};
  state.data.statusDashboard.rotation = [{id: 'p1', name: 'Derrick White', extension_eligible: true, salary_by_year: {a: 1, b: 2}}, {id: 'p2', name: 'Sam Hauser'}];
  state.home.league_events.events = [
    {id: 'x', date: '2027-08-01', kind: 'extension', team_ids: ['team_ind'], player_ids: ['p_h'], details: {player_id: 'p_h', team_id: 'team_ind', aav_millions: 50.7, annual_salary: 50700000, years: 3}, activity_groups: [{subjects: [{id: 'p_h', name: 'Tyrese Haliburton'}]}]},
    {id: 'y', date: '2027-07-03', kind: 'free_agent_signing', team_ids: ['team_mem'], player_ids: ['p_j'], details: {player_id: 'p_j', team_id: 'team_mem', aav_millions: 12, years: 2}, activity_groups: [{subjects: [{id: 'p_j', name: 'Ty Jerome'}]}]},
  ];
  const context = {window: {GameProgress: {PHASES: {offseason: {games: false}}}}, state};
  vm.createContext(context);
  vm.runInContext(read('home-front.js'), context);
  const html = context.window.HomeFront.markup();
  assert.match(html, /class="front is-summer"/);
  assert.match(html, /front-hero is-offseason/);
  assert.match(html, /Payroll<\/small><span class="front-score">\$222\.0M<\/span><span class="front-versus front-loss">\$14\.5M over the tax line/);
  assert.match(html, /Roster<\/small><span class="front-score">2 players<\/span><span class="front-versus ">2 open spots/);
  assert.match(html, /Biggest deals/);
  assert.ok(html.indexOf('Tyrese Haliburton') < html.indexOf('Ty Jerome'), 'largest first');
  assert.match(html, /Can be extended[\s\S]*Derrick White[\s\S]*2 years left/);
  assert.doesNotMatch(html, /Last game|Scores <small>|Against expectation/, 'nothing about games that are not being played');
  assert.match(read('card-pages.js'), /function homeLayout\(\) \{\n\s+return \{full: \{fits: \[1180, 660\], roomy: \[1500, 900\]\}, \.\.\.row\(card\("front", \{bare: true, fill: true\}\)\)\};/, 'Today is the front page all year');
});

test('the storyline data is gathered by a display-only action: stored things only, nothing saved', () => {
  const server = fs.readFileSync(path.join(gui, '../app_actions.py'), 'utf8');
  const payload = server.slice(server.indexOf('def home_storylines_payload('), server.indexOf('def league_efficiency_average('));
  assert.match(server, /if action == "home_storylines":\n\s+return home_storylines_payload\(canonical, save_path\)/);
  assert.match(payload, /if buyer in humans or seller in humans/, 'your own talks are left out');
  assert.match(payload, /save\.get\("team_game_logs"\)/);
  assert.match(payload, /save\.get\("injury_events"\)/);
  assert.match(payload, /staff_win_gap\(/, 'the coach review\'s own measure');
  assert.match(payload, /< days_back\(6\)/, 'no streak or pace without a recent game');
  assert.doesNotMatch(payload, /write_save|save_save|json\.dump|random\./, 'nothing is saved or rolled');
  assert.match(read('home-front.js'), /call\("action", "home_storylines", call\("savePayload"\)\)/);
});

