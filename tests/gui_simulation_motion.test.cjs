const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');

test('streamed regular-season results update records and conference ranks without mutating the snapshot', () => {
  const start = app.indexOf('function standingsAfterProgressGame(');
  const end = app.indexOf('\nfunction applyStandingsGameProgress', start);
  assert.ok(start >= 0 && end > start);
  const context = {};
  vm.createContext(context);
  vm.runInContext(app.slice(start, end), context);

  const snapshot = {standings: [
    {team:{id:'team_a',conference:'East',abbrev:'AAA'},wins:10,losses:10,games:20,points_for:2100,points_against:2100,point_diff:0,win_pct:0.5},
    {team:{id:'team_b',conference:'East',abbrev:'BBB'},wins:10,losses:10,games:20,points_for:2120,points_against:2100,point_diff:20,win_pct:0.5},
    {team:{id:'team_c',conference:'West',abbrev:'CCC'},wins:15,losses:5,games:20,points_for:2200,points_against:2100,point_diff:100,win_pct:0.75},
  ]};
  const result = context.standingsAfterProgressGame(snapshot, {
    game_id:'game-1',home_team_id:'team_a',away_team_id:'team_b',home_score:110,away_score:100,
  });
  const rows = result.snapshot.standings;
  const teamA = rows.find((row) => row.team.id === 'team_a');
  const teamB = rows.find((row) => row.team.id === 'team_b');
  assert.equal(teamA.wins, 11);
  assert.equal(teamB.losses, 11);
  assert.equal(teamA.points_for, 2210);
  assert.equal(teamB.points_against, 2210);
  assert.equal(result.previousRanks.get('team_a'), 2);
  assert.equal(result.nextRanks.get('team_a'), 1);
  assert.equal(result.nextRanks.get('team_c'), 1);
  assert.equal(snapshot.standings[0].wins, 10);
  assert.equal(snapshot.standings[0].points_for, 2100);
});

test('progress presentation updates each game once and keeps minute sliders in place while sorting', () => {
  assert.match(app, /simulationProcessedGames\.has\(gameId\)[\s\S]*?simulationProcessedGames\.add\(gameId\)/);
  assert.match(app, /event\.phase !== "regular_season"/);
  assert.match(app, /row\.style\.gridRow = String\(index \+ 2\)/);
  assert.match(app, /normalizeMinutesDomOrder\(input\.closest\("\.season-minutes-table"\)\)/);
  assert.match(app, /function updateRotationDuringSimulation\(rotation\)/);
  assert.match(app, /GameSimulation\.reducedMotion\(\)/);
  const css = fs.readFileSync(path.join(gui, 'card-board.css'), 'utf8');
  assert.match(css, /\.season-row-motion\.down\s*\{\s*color:#a13b43;/);
  assert.match(css, /@media \(prefers-reduced-motion:reduce\)/);
});

test('team signal and opponent cards consume live progress and expose animated score feedback', () => {
  assert.match(app, /if \(event\.team_signals\) updateTeamSignalsDuringSimulation\(event\.team_signals\)/);
  assert.match(app, /if \(event\.opponent\) updateOpponentDuringSimulation\(event\.opponent\)/);
  assert.match(app, /data-team-signal-key/);
  assert.match(app, /season-opponent-result-header/);
  const css = fs.readFileSync(path.join(gui, 'card-board.css'), 'utf8');
  assert.match(css, /transition:width 420ms ease,background-color 420ms ease/);
  assert.match(css, /season-simulation-result > b/);

  const start = app.indexOf('function simulationOpponentResult(');
  const end = app.indexOf('\nfunction showSimulationOpponentResult', start);
  assert.ok(start >= 0 && end > start);
  const context = {};
  vm.createContext(context);
  vm.runInContext(app.slice(start, end), context);
  const homeWin = context.simulationOpponentResult({game:{
    game_id:'game-1',home_team_id:'team_user',away_team_id:'team_away',home_score:112,away_score:108,
  }}, 'team_user');
  assert.deepEqual(JSON.parse(JSON.stringify(homeWin)), {result:'W',score:112,opponentScore:108,opponentId:'team_away'});
  const awayLoss = context.simulationOpponentResult({game:{
    game_id:'game-2',home_team_id:'team_home',away_team_id:'team_user',home_score:107,away_score:99,
  }}, 'team_user');
  assert.deepEqual(JSON.parse(JSON.stringify(awayLoss)), {result:'L',score:99,opponentScore:107,opponentId:'team_home'});
  assert.equal(context.simulationOpponentResult({game:{game_id:'other',home_team_id:'x',away_team_id:'y',home_score:99,away_score:98}}, 'team_user'), null);
});

test('month-boundary progress replaces the stale calendar snapshot before rendering the new month', () => {
  const assign = app.indexOf('if (event.calendar) state.data.dashboardCalendar = event.calendar;');
  const render = app.indexOf('renderCalendar(week, {team:userTeam(),dataKey:\'dashboardCalendar\'})', assign);
  assert.ok(assign >= 0 && render > assign);
  assert.match(app, /if \(dateChanged\) state\.calendarMonth = event\.date\.slice\(0,7\)/);
});
