const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
function functionSource(name, next) {
  return app.slice(app.indexOf(`function ${name}(`), app.indexOf(`function ${next}(`)).replace(/\nasync\s*$/, '');
}

test('compact prospect rows open reports through the same handler after initial render and sorting', () => {
  const calls = [], listeners = [];
  const scope = { draftProspectCard: id => calls.push(id) };
  vm.createContext(scope);
  vm.runInContext(functionSource('wireDashboardProspectCards', 'wireDashboardStaffCards'), scope);
  const buttons = [{dataset: {draftProspectCard: 'prospect-1'}, addEventListener: (event, handler) => {
      assert.equal(event, 'click');
      listeners.push(handler);
  }}];
  const root = {querySelectorAll: selector => {
    assert.equal(selector, '[data-draft-prospect-card]');
    return buttons;
  }};
  scope.wireDashboardProspectCards(root);
  scope.wireDashboardProspectCards(root);
  assert.equal(listeners.length, 1);
  listeners[0]();
  assert.deepEqual(calls, ['prospect-1']);
  assert.match(functionSource('wireDashboardOverview', 'wireFranchiseJourney'), /wireDashboardProspectCards\(\)/);
  assert.match(functionSource('wireSeasonProspectSort', 'renderDraft'), /wireDashboardProspectCards\(root\)/);
});

test('rotation autosave failures restore the persisted dashboard and report the error', () => {
  assert.match(functionSource('wireRotationMinuteInputs', 'wireDashboardStaffControls'), /await saveRotationMinutes\(\{ quiet: true \}\);[\s\S]*?catch \(error\)[\s\S]*?state\.rotationDraft = \{\};[\s\S]*?state\.rotationLockedPlayerIds\.clear\(\);[\s\S]*?renderDashboard\(\);[\s\S]*?Minutes were not saved/);
});

test('the dashboard Settings dialog exposes a working replay control', () => {
  const scope = {state: {}, renderModal() {}};
  vm.createContext(scope);
  vm.runInContext(functionSource('openSettingsModal', 'openExtensionNegotiation'), scope);
  scope.openSettingsModal();
  assert.match(scope.state.modal.body, /data-replay-tutorial>Replay Tutorial/);
  assert.match(app, /querySelector\("\[data-replay-tutorial\]"\)[\s\S]*?state\.modal = null;[\s\S]*?renderModal\(\);[\s\S]*?startGameTutorial\(true\)/);
});

test('trade searches distinguish unsearched, completed empty, and approved offers', () => {
  const scope = {state: {tradeSearchCompleted: false}, tradeCandidateCard: (_result, index) => `offer-${index}`};
  vm.createContext(scope);
  vm.runInContext(functionSource('tradeResultCards', 'offerCard'), scope);
  assert.match(scope.tradeResultCards([]), /Select assets/);
  scope.state.tradeSearchCompleted = true;
  assert.match(scope.tradeResultCards([]), /No matching offers/);
  assert.doesNotMatch(scope.tradeResultCards([]), /Select assets to find trades/);
  assert.equal(scope.tradeResultCards([{}]), 'offer-0');
  assert.match(app, /state\.tradeResults = data\.candidates \|\| data\.offers \|\| \[\];\s*state\.tradeSearchCompleted = true;/);
  for (const [name, next] of [['clearViewCaches', 'syncDefaultPartner'], ['toggleAsset', 'selectedList'], ['removeAsset', 'assetSpec']]) {
    assert.match(functionSource(name, next), /state\.tradeSearchCompleted = false;/);
  }
});

test('minutes initialize from saved targets and locks, not newer coaching projections', () => {
  const scope = {
    state: {rotationDraft: {}, rotationLockedPlayerIds: new Set()},
    seasonPanelHeader: () => '', isPlayerInjured: () => false,
    seasonFatigueCell: () => '', escapeHtml: String, escapeAttr: String,
    playerInjuryStatusMarkup: () => '', playerHeadshotMarkup: () => '', heightFromRow: () => '',
    clampNumber: (value, min, max) => Math.min(max, Math.max(min, value)),
  };
  vm.createContext(scope);
  vm.runInContext(functionSource('ensureRotationDraft', 'autofillRotationDraft'), scope);
  vm.runInContext(functionSource('seasonMinutesCard', 'seasonMiniRating'), scope);
  const rows = [
    {id: 'curry', name: 'Stephen Curry', rotation_target_minutes: 31, minutes_projection: 33, rotation_user_set: true},
    {id: 'bench', name: 'Bench Player', rotation_target_minutes: 0, minutes_projection: 5},
  ];
  const markup = scope.seasonMinutesCard(rows, true);
  assert.equal(scope.state.rotationDraft.curry, 31);
  assert.equal(scope.state.rotationDraft.bench, 0);
  assert.equal(scope.state.rotationLockedPlayerIds.has('curry'), true);
  assert.match(markup, /data-minute-output="curry">31/);
  assert.match(markup, /data-minute-output="bench">0/);
  scope.state.rotationDraft.departed = 12;
  scope.state.rotationLockedPlayerIds.add('departed');
  scope.ensureRotationDraft(rows);
  assert.equal('departed' in scope.state.rotationDraft, false);
  assert.equal(scope.state.rotationLockedPlayerIds.has('departed'), false);
});

test('quiet minute saves rebuild sliders from the confirmed server rotation', async () => {
  const scope = {
    state: {rotationDraft: {traded: 32, injured: 24}, rotationLockedPlayerIds: new Set(['traded', 'injured']), data: {}, view: 'dashboard'},
    action: async () => ({status: 'updated', dashboard: {rotation: [
      {id: 'traded', rotation_target_minutes: 36, rotation_user_set: true},
      {id: 'injured', rotation_target_minutes: 0, rotation_user_set: false},
    ]}}),
    savePayload: () => ({}), userTeam: () => 'MEM', showToast() {},
    isPlayerInjured: () => false,
  };
  vm.createContext(scope);
  vm.runInContext(functionSource('ensureRotationDraft', 'rebalanceInjuredRotationDraft'), scope);
  scope.rebalanceInjuredRotationDraft = () => {};
  scope.renderDashboard = () => scope.ensureRotationDraft(scope.state.data.dashboard.rotation);
  vm.runInContext(app.slice(app.indexOf('async function saveRotationMinutes('), app.indexOf('function seriesCard(')), scope);
  await scope.saveRotationMinutes({quiet: true});
  assert.equal(scope.state.rotationDraft.traded, 36);
  assert.equal(scope.state.rotationDraft.injured, 0);
  assert.deepEqual([...scope.state.rotationLockedPlayerIds], ['traded']);
});

test('quiet minute saves retain a newer pending edit and surface blocked saves as failures', async () => {
  const scope = {
    state: {rotationDraft: {traded: 32}, rotationLockedPlayerIds: new Set(['traded']), data: {}, view: 'dashboard'},
    action: async () => {
      scope.state.rotationDraft.traded = 35;
      return {status: 'updated', dashboard: {rotation: []}};
    },
    savePayload: () => ({}), userTeam: () => 'MEM', renderDashboard() {}, showToast() {},
  };
  vm.createContext(scope);
  vm.runInContext(app.slice(app.indexOf('async function saveRotationMinutes('), app.indexOf('function seriesCard(')), scope);
  await scope.saveRotationMinutes({quiet: true});
  assert.equal(scope.state.rotationDraft.traded, 35);
  scope.action = async () => ({status: 'blocked', reason: 'Not enough healthy players'});
  await assert.rejects(scope.saveRotationMinutes({quiet: true}), /Not enough healthy players/);
});

test('advancing the calendar refreshes injury substitutions from the current saved plan', () => {
  const scope = {
    state: {rotationDraft: {star: 0}, rotationLockedPlayerIds: new Set(), rotationDraftDate: '2027-02-01',
            data: {dashboard: {current_date: '2027-02-04'}}},
    rebalanceInjuredRotationDraft() {},
  };
  vm.createContext(scope);
  vm.runInContext(functionSource('ensureRotationDraft', 'rebalanceInjuredRotationDraft'), scope);
  scope.ensureRotationDraft([{id: 'star', rotation_target_minutes: 32, rotation_user_set: true}]);
  assert.equal(scope.state.rotationDraft.star, 32);
  assert.equal(scope.state.rotationLockedPlayerIds.has('star'), true);
  scope.state.rotationDraft.star = 35;
  scope.ensureRotationDraft([{id: 'star', rotation_target_minutes: 32, rotation_user_set: true}]);
  assert.equal(scope.state.rotationDraft.star, 35);
});
