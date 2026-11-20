// Free-agency room: the offer builder's verdict and cap preview mirror the engine's signing rules; the market table
// filters, sorts and flags rival bids from engine numbers; the room opens once as one row of windows.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const board = fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8');
const slice = (from, to) => {
  const start = app.indexOf(from);
  const end = app.indexOf(to, start + 1);
  assert.ok(start >= 0 && end > start, `missing app.js section ${from}`);
  return app.slice(start, end);
};

const money = (value) => (value === undefined || value === null || value === '' ? '' : `$${Number(value).toFixed(1)}M`);
const signedMoney = (value) => `$${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(1)}M`;
const escapeHtml = (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function room(overrides = {}) {
  return {
    phase: 'free_agency',
    state: {day: 2, day_count: 5, status: 'active'},
    team: {id: 'team_cha', abbrev: 'CHA'},
    signing_season: '2027-28',
    roster_count: 13,
    cap: {salary_total_millions: 140.1, tax_space_millions: 67.3, hard_cap_space_millions: 89.3, max_offer_aav_millions: 67.3},
    cap_by_year: {
      '2026-27': {salary_total_millions: 160, tax_space_millions: 40, hard_cap_space_millions: 62, tax_line_millions: 200, hard_cap_millions: 222},
      '2027-28': {salary_total_millions: 140.1, tax_space_millions: 67.3, hard_cap_space_millions: 89.3, tax_line_millions: 207.4, hard_cap_millions: 229.4},
      '2028-29': {salary_total_millions: 150, tax_space_millions: 64.7, hard_cap_space_millions: 87.4, tax_line_millions: 214.7, hard_cap_millions: 237.4},
      '2029-30': {salary_total_millions: 100, tax_space_millions: 122.2, hard_cap_space_millions: 145.7, tax_line_millions: 222.2, hard_cap_millions: 245.7},
    },
    offer_rules: {minimum_aav_millions: 1.9, allow_tax_exceed: false, max_years: 5, options_available: false, blocked_reason: null},
    candidates: [],
    active_offers: [],
    ...overrides,
  };
}
const miller = {
  id: 'p_miller', name: 'Brandon Miller', position: 'SF', age: 24, ratings: {overall: 66.4, offense: 65.4, defense: 65.7},
  ask_millions: 28.8, offer_count: 4, highest_offer: {team_abbrev: 'BKN', aav_millions: 30.4, years: 4, interest_score: 78.2},
  accept_floor_millions: {guaranteed: 13.545000000000002, non_guaranteed: 16.254},
  accept_floor_offer_millions: {guaranteed: 13.6, non_guaranteed: 16.3},
  safe_years: 5, sign_bar_today: 80, team_fit_score: 53.5,
};

function builderScope() {
  const scope = {money, signedMoney, escapeHtml, clampNumber: (x, a, b) => Math.max(a, Math.min(b, x)), state: {data: {}, currentSave: 's'}, Number, Math, Object, String};
  vm.createContext(scope);
  vm.runInContext(slice('function freeAgencyRoomState(', 'function ensureFreeAgencySelection('), scope);
  vm.runInContext(slice('function freeAgencyMinimum(', 'function phaseFreeAgencyMarketCard('), scope);
  vm.runInContext(slice('function roundOfferTenth(', 'function freeAgencyOfferBuilderPanel('), scope);
  return scope;
}

test('cap check mirrors the engine rule: minimum always allowed, tax room binds in free agency, hard cap always', () => {
  const {freeAgencyCapCheck} = builderScope();
  const rules = {minimum_aav_millions: 1.9, allow_tax_exceed: false};
  const cap = {tax_space_millions: 10, hard_cap_space_millions: 30};
  assert.equal(freeAgencyCapCheck(rules, cap, 10).ok, true);
  const overTax = freeAgencyCapCheck(rules, cap, 10.1);
  assert.equal(overTax.ok, false);
  assert.equal(overTax.limit, 'tax');
  assert.equal(freeAgencyCapCheck({...rules, allow_tax_exceed: true}, cap, 25).ok, true, 're-signing may exceed the tax');
  assert.equal(freeAgencyCapCheck({...rules, allow_tax_exceed: true}, cap, 30.1).limit, 'hard');
  // League minimum (with the engine's 0.05 tolerance) is allowed even with no room at all.
  const broke = {tax_space_millions: -5, hard_cap_space_millions: -2};
  assert.equal(freeAgencyCapCheck(rules, broke, 1.9).ok, true);
  assert.equal(freeAgencyCapCheck(rules, broke, 1.95).ok, true);
  assert.equal(freeAgencyCapCheck(rules, broke, 2.0).ok, false);
  // Unreviewed waived salary blocks every signing, the minimum included.
  assert.equal(freeAgencyCapCheck({...rules, blocked_reason: 'Waived salary requires review.'}, cap, 1.9).ok, false);
});

test('the verdict uses the salary he needs from you (not his market ask), the guarantee and his retirement', () => {
  const {freeAgencyOfferPreview} = builderScope();
  const r = room();
  const at = (aav, extra = {}) => freeAgencyOfferPreview(miller, r, {aav, years: 4, guaranteed: true, ...extra});
  assert.equal(at(13.5).accepts, false, 'one step under his floor');
  assert.match(at(13.5).verdict.detail, /\$13\.6M/);
  assert.equal(at(13.6).accepts, true, 'his floor, well below the $28.8M market ask');
  assert.equal(at(13.6).verdict.tone, 'yes');
  assert.equal(at(13.6, {guaranteed: false}).accepts, false, 'a non-guaranteed deal needs more');
  assert.equal(at(16.3, {guaranteed: false}).accepts, true);
  const veteran = {...miller, safe_years: 2};
  const long = freeAgencyOfferPreview(veteran, r, {aav: 20, years: 3, guaranteed: true});
  assert.equal(long.accepts, false);
  assert.match(long.verdict.detail, /retire after 2 seasons/);
  assert.equal(freeAgencyOfferPreview(veteran, r, {aav: 20, years: 2, guaranteed: true}).accepts, true);
  const blocked = at(70);
  assert.equal(blocked.cap.ok, false);
  assert.equal(blocked.canSubmit, false);
  assert.equal(blocked.verdict.tone, 'blocked');
  assert.equal(freeAgencyOfferPreview({...miller, signing_blocked_reason: 'stretched'}, r, {aav: 20, years: 1}).canSubmit, false);
});

test('cap preview starts at the signing season and adds a flat salary for the contract years only', () => {
  const {freeAgencyOfferPreview} = builderScope();
  const preview = freeAgencyOfferPreview(miller, room(), {aav: 20, years: 2, guaranteed: true});
  assert.deepEqual(Array.from(preview.seasons, (row) => row.season), ['2027-28', '2028-29', '2029-30'], 'the finished season is not charged');
  assert.deepEqual(Array.from(preview.seasons, (row) => row.salary), [20, 20, 0]);
  assert.equal(preview.seasons[0].after, 160.1);
  assert.equal(Math.round(preview.seasons[0].taxRoom * 10) / 10, 47.3);
  assert.equal(Math.round(preview.seasons[1].hardRoom * 10) / 10, 67.4);
  assert.equal(preview.total, 40);
  assert.ok(Math.abs(preview.ratio - 20 / 13.545) < 1e-9, 'meter = salary / his price (the engine player score)');
});

test('the offer draft starts at his ask within the legal range, at most four years and never past retirement', () => {
  const scope = builderScope();
  const r = room();
  const draft = scope.freeAgencyOfferDraft(miller, r);
  assert.equal(draft.aav, 28.8);
  assert.equal(draft.years, 4);
  assert.equal(draft.guaranteed, true);
  const star = scope.freeAgencyOfferDraft({...miller, id: 'star', ask_millions: 90, safe_years: 2}, r);
  assert.equal(star.aav, 67.3, 'capped at the largest legal offer');
  assert.equal(star.years, 2);
  assert.equal(scope.freeAgencyOfferDraft(miller, r), draft, 'one draft per player, kept while browsing');
});

test('market: mood compares the best rival bid with today\'s bar; filters and sorting use engine fields', () => {
  const scope = {money, escapeHtml, clampNumber: (x, a, b) => Math.max(a, Math.min(b, x)), state: {
    data: {}, freeAgentShortlistIds: ['p_b'], freeAgentMarketScope: 'market', freeAgentMarketSort: {key: 'ask_millions', direction: 'desc'},
    freeAgentMarketFilters: {search: '', position: 'all', minOverall: '', maxAge: '', afford: false},
  }};
  vm.createContext(scope);
  vm.runInContext(slice('function freeAgencyRoomState(', 'function ensureFreeAgencySelection('), scope);
  vm.runInContext(slice('function freeAgencyMinimum(', 'function phaseFreeAgencyMarketCard('), scope);
  vm.runInContext(slice('function freeAgencyMyOfferIds(', 'function freeAgencyMoodCell('), scope);
  vm.runInContext(slice('function sortFreeAgencyCandidates(', '// ---- Offer builder'), scope);
  assert.equal(scope.freeAgencyMood(miller).label, 'Weighing bids');
  assert.equal(scope.freeAgencyMood({...miller, sign_bar_today: 78}).tone, 'hot');
  assert.equal(scope.freeAgencyMood({...miller, highest_offer: null}).label, 'No bids');
  assert.equal(scope.freeAgencyMood(miller, true).label, 'Your rights');
  const players = [
    {...miller},
    {...miller, id: 'p_b', name: 'Old Guard', position: 'PG/SG', age: 35, ask_millions: 9, offer_count: 0, highest_offer: null, accept_floor_offer_millions: {guaranteed: 80}},
    {...miller, id: 'p_c', name: 'Young Big', position: 'C', age: 21, ask_millions: 4, ratings: {overall: 50}},
  ];
  const r = room({candidates: players, user_offer_history: [{player_id: 'p_c', accepted: false}]});
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_miller', 'p_b', 'p_c']);
  scope.state.freeAgentMarketFilters.position = 'SG';
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_b'], 'dual positions match either');
  scope.state.freeAgentMarketFilters = {search: '', position: 'all', minOverall: '', maxAge: '30', afford: true};
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_miller', 'p_c'], 'age and "fits our room" filters');
  scope.state.freeAgentMarketFilters = {search: '', position: 'all', minOverall: '', maxAge: '', afford: false};
  scope.state.freeAgentMarketScope = 'bids';
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_miller', 'p_c']);
  scope.state.freeAgentMarketScope = 'offers';
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_c'], 'turned-down offers count as my offers');
  scope.state.freeAgentMarketScope = 'shortlist';
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_b']);
  scope.state.freeAgentMarketScope = 'market';
  scope.state.freeAgentMarketSort = {key: 'age', direction: 'asc'};
  assert.deepEqual(Array.from(scope.freeAgencyMarketRows(r), (p) => p.id), ['p_c', 'p_miller', 'p_b']);
});

test('free agency opens the market, the offer builder and the signing wire together, once, in one row', () => {
  const scope = {state: {data: {freeagency: room()}, home: {save: {phase: 'free_agency'}}}, dashboardPhaseKind: () => 'free_agency'};
  vm.createContext(scope);
  vm.runInContext(slice('function clipboardEntryLayout(', 'function seasonalClipboardCards('), scope);
  const layout = scope.clipboardEntryLayout();
  assert.deepEqual(JSON.parse(JSON.stringify(layout.rows)), [['phase-free_agency-market', 'phase-free_agency-selected', 'phase-free_agency-wire']]);
  const cardBoardScope = {window: {}, structuredClone};
  vm.createContext(cardBoardScope);
  vm.runInContext(board, cardBoardScope);
  const {arrangeEntryRows, entryLayoutDue} = cardBoardScope.window.CardBoard;
  const card = (width) => ({x: 0, y: 0, width, height: 740, scale: 1, minScale: .72, visible: false});
  const cards = {'phase-free_agency-market': card(756), 'phase-free_agency-selected': card(440), 'phase-free_agency-wire': card(220)};
  arrangeEntryRows(cards, layout.rows, {clientWidth: 1440, clientHeight: 840, scrollLeft: 0, scrollTop: 0});
  const [market, builder, wire] = Object.values(cards);
  assert.ok(market.visible && builder.visible && wire.visible);
  assert.equal(market.y, builder.y);
  assert.ok(market.x + market.width * market.scale <= builder.x && builder.x + builder.width * builder.scale <= wire.x, 'side by side, no overlap');
  assert.ok(market.scale >= .95, `readable at 1440 wide (${market.scale})`);
  // Once: a reload in the same phase keeps the saved arrangement.
  assert.equal(entryLayoutDue(layout, {phaseCards: ['phase-free_agency-market']}, false), false);
  assert.equal(entryLayoutDue(layout, {phaseCards: ['phase-free_agency-market']}, true), true);
});

test('free-agency windows: three cards, no leftover controls/payroll/cap windows, day controls in the top bar', () => {
  const section = slice('    free_agency: [', '    fantasy_draft: [');
  assert.deepEqual(Array.from(section.matchAll(/\["(\w+)", "([^"]+)", "([^"]+)"\]/g), (m) => m[1]), ['market', 'selected', 'wire']);
  const commands = slice('function freeAgencyPhaseCommands(', 'function freeAgencyMinimum(');
  for (const id of ['reSignAdvanceDay', 'reSignOpenMarket', 'faAdvanceStage', 'faAdvanceDay', 'faAdvanceEnd']) assert.match(commands, new RegExp(id));
  for (const command of ["'resign-day'", "'resign-open'", "'fa-day'", "'fa-end'", "'fa-next'"]) assert.ok(app.includes(`${command}:`), command);
  // No invented interest number survives from the old negotiation modal.
  assert.doesNotMatch(app, /offer \/ Math\.max\(1, ask\) \* 70/);
  assert.doesNotMatch(app, /freeAgentNegotiationBody/);
});
