// TRADE-DEADLINE: a partner a little short of its price answers the user's offer with a counter-offer. The trade
// window shows the counter in plain words and the full package each side would send (the exact deal that Accept
// executes), with Accept / Decline buttons; nothing extra when there is no counter or the partner already accepts.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');

function extract(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} not found`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next);
}

function readoutIn() {
  const context = {
    state: {home: {save: {user_team: {id: 'gsw'}}}},
    teamLabel: (team) => String(team || '').replace('team_', '').toUpperCase(),
    userTeam: () => 'GSW',
    textValue: (value) => String(value ?? ''),
    escapeHtml: (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    tradeLegalityBadge: () => '', tradeLegalityIssues: () => '',
  };
  vm.createContext(context);
  vm.runInContext(`${extract('tradeReadout')}\n${extract('tradeCounterOffer')}\nthis.tradeReadout = tradeReadout;`, context);
  return (candidate, rounds = []) => {
    context.state.tradeCounterChain = {partner: 'UTA', rounds};
    return context.tradeReadout(candidate);
  };
}

const counter = {
  proposal: {id: 'c', from_team_id: 'gsw', to_team_id: 'team_uta',
    from_assets: [{kind: 'player', label: 'Buddy Hield'}, {kind: 'pick', label: '2029 R2 GSW'}],
    to_assets: [{kind: 'player', label: 'Collin Sexton'}]},
  legality: {status: 'legal'},
  evaluations: [{perspective_team_id: 'team_uta', accepted: true}],
  counter: {text: 'UTA asked for a 2029 second-round pick as well.'},
};

test('a declined offer with a counter shows it in plain words with the full packages', () => {
  const readout = readoutIn();
  const html = readout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_uta', accepted: false}],
    counter_offer: counter});
  assert.match(html, /Partner declines/);
  assert.match(html, /class="trade-counter-offer/);
  assert.match(html, /UTA asked for a 2029 second-round pick as well\./);
  assert.match(html, /GSW sends: Buddy Hield, 2029 R2 GSW/);
  assert.match(html, /UTA sends: Collin Sexton/);
  assert.match(html, /id="acceptCounterTrade"/);
  assert.match(html, /id="declineCounterTrade"/);
});

test('a later round lists the earlier counters and offers Edit; a closed negotiation says so', () => {
  const readout = readoutIn();
  const second = {...counter, counter: {text: 'UTA asked for a 2031 second-round pick as well.', rounds: 2, package: 'b'}};
  const html = readout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_uta', accepted: false}],
    counter_offer: second}, [{package: 'a', text: 'UTA asked for a 2029 second-round pick as well.', round: 1}, {package: 'b', text: second.counter.text, round: 2}]);
  assert.match(html, /Round 1: UTA asked for a 2029 second-round pick as well\./);
  assert.match(html, /Counter-offer \(round 2\):/);
  assert.match(html, /id="editCounterTrade"/);
  const closed = readout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_uta', accepted: false}],
    counter_closed: true}, []);
  assert.match(closed, /No more counters/);
});

test('no counter block when there is none or the partner accepts', () => {
  const readout = readoutIn();
  const declined = readout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_uta', accepted: false}]});
  assert.doesNotMatch(declined, /trade-counter-offer/);
  const accepted = readout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_uta', accepted: true}],
    counter_offer: counter});
  assert.match(accepted, /Accept Trade/);
  assert.doesNotMatch(accepted, /trade-counter-offer/);
});
