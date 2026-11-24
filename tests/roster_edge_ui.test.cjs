// FA-REAL slice 4: the opening-roster window (two-way places, camp deals, guarantees, a two-way move counts toward the
// cut) and the free-agency builder's other ways to add a player (two-way, camp invite, sign-and-trade).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const slice = (from, to) => {
  const start = app.indexOf(from);
  const end = app.indexOf(to, start + 1);
  assert.ok(start >= 0 && end > start, `missing app.js section ${from}`);
  return app.slice(start, end);
};
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const scope = () => {
  const context = {
    state: {hydrating: false, home: {save: {phase: 'preseason', current_date: '2027-10-12'}}, data: {}},
    escapeHtml: escape, escapeAttr: escape,
    money: (value) => `$${Number(value || 0).toFixed(1)}M`,
    compactPos: (value) => value, shortDate: (value) => String(value || '').slice(5),
    playerHeadshotMarkup: () => '', shortSeasonLabel: (value) => value, teamLabel: (value) => value,
    clipboardLegalActions: () => new Set(['free_agent_signings']),
    ratingInkColor: () => '#226ca8', clampNumber: (v, lo, hi) => Math.min(hi, Math.max(lo, v)),
  };
  vm.createContext(context);
  return context;
};

test('a camp deal moved to a two-way place counts toward the cut', () => {
  const context = scope();
  vm.runInContext(slice('function cutdownReleaseCost(', 'function cutdownContractCell('), context);
  const room = {current_count: 17, target_count: 15, players: [
    {player_id: 'a', name: 'A', waiver: {remaining_cost_millions: 0}},
    {player_id: 'b', name: 'B', waiver: {remaining_cost_millions: 0}},
    {player_id: 'c', name: 'C', waiver: {remaining_cost_millions: 1}}]};
  const summary = context.cutdownSelectionSummary(room, {a: 'waive', b: 'twoway'});
  assert.equal(summary.after, 15);
  assert.equal(summary.ready, true);
  assert.equal(summary.moving, 1);
  assert.match(summary.names.join(' '), /B \(to two-way\)/);
});

test('the opening-roster window shows the two-way places, their games and open places', () => {
  const context = scope();
  vm.runInContext(slice('function cutdownGuaranteeCell(', 'function cutdownQuoteCell('), context);
  vm.runInContext(slice('function cutdownTwoWayRows(', 'function cutdownQuoteCell('), context);
  const roles = () => '<span class="season-minute-roles"></span>';
  const html = context.cutdownTwoWayRows({roster: {two_way_limit: 3, two_ways: [
    {player_id: 'p', name: 'Young Guard', position: 'PG', age: 22, overall: 48, active_games: 12, active_limit: 50,
     seasons: [{season: '2027-28', salary_millions: 0.7}], convert: {ok: false, reason: 'No standard roster spot'}}]}}, roles);
  // Taste deck round 3: rows of the opening-roster table under a section row, with a Details drop-down.
  assert.match(html, /Two-way places · 1 \/ 3 · 2 open/);
  // Round 9: games used moved to the row's hover (the Guaranteed cell stays empty for two-way places).
  assert.match(html, /active for 12 of the 50 NBA games/);
  assert.match(html, /outside your 15 standard spots and the salary cap/);
  assert.match(html, /No free agent is eligible/);
  assert.match(html, /data-two-way-convert="p" disabled/);
  const open = context.cutdownTwoWayRows({roster: {two_way_limit: 3, two_ways: []}, two_way_candidates: [
    {player_id: 'fa', name: 'Free Agent', position: 'SF', age: 20, overall: 53.3, pay_millions: 0.679}]}, roles);
  assert.match(open, /3 open/);
  assert.match(open, /data-two-way-sign="fa"/);
  const camp = context.cutdownGuaranteeCell({contract_kind: 'camp', guarantee: {kind: 'camp', words: 'Camp deal: not guaranteed'}});
  assert.match(camp, /Camp deal/);
});

test('the builder offers a two-way, a camp invite and a sign-and-trade with the engine reasons', () => {
  const context = scope();
  vm.runInContext(slice('function freeAgencyOtherDealsMarkup(', 'function freeAgencySignAndTradeMarkup('), context);
  const html = context.freeAgencyOtherDealsMarkup({id: 'x', name: 'X', roster_edge: {
    two_way: {ok: true, pay_millions: 0.703, two_years: true},
    camp: {ok: false, reason: 'You already have 6 camp deals.'},
    sign_and_trade: {available: true, role: 'receiver', rights_abbrev: 'DEN'}}});
  assert.match(html, /Two-way contract/);
  assert.match(html, /data-fa-two-way="2"/);
  assert.match(html, /data-fa-camp-invite disabled/);
  assert.match(html, /You already have 6 camp deals/);
  assert.match(html, /Ask DEN/);
});

test('two-way qualifying offers in the stop-1 checklist', () => {
  const context = scope();
  context.state.home.save.current_date = '2027-06-20';
  vm.runInContext(slice('function offseasonItemActions(', 'function offseasonChecklistTable('), context);
  const html = context.offseasonItemActions({kind: 'two_way_qualifying_offer', player_id: 'p', status: 'pending', deadline: '2027-06-29'}, true);
  assert.match(html, /data-offseason-twqo="tender"/);
  assert.match(html, /data-offseason-twqo="none"/);
});
