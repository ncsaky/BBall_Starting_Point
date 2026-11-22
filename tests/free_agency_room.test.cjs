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
  // TRADE-VOLUME: his price from you follows the rival bids' rule (today's bar and the best rival bid, BKN $30.4M x 4),
  // so it depends on the length; 1 year cannot beat BKN's bid at any salary (null).
  accept_floor_millions: {guaranteed: 31.0, non_guaranteed: 37.6},
  accept_floor_offer_millions: {guaranteed: 31.0, non_guaranteed: 37.6},
  accept_floor_by_years: {
    guaranteed: {1: null, 2: 33.0, 3: 32.0, 4: 31.0, 5: 31.0},
    non_guaranteed: {1: null, 2: 40.1, 3: 38.9, 4: 37.6, 5: 37.6},
  },
  offer_rule: {mode: 'market', bar: 80, ask_millions: 28.8, preferred_years: 4, best_rival: {team_abbrev: 'BKN', interest: 78.2, aav_millions: 30.4, years: 4}},
  safe_years: 5, sign_bar_today: 80, team_fit_score: 53.5,
};

function builderScope() {
  const scope = {money, signedMoney, escapeHtml, clampNumber: (x, a, b) => Math.max(a, Math.min(b, x)), state: {data: {}, currentSave: 's'}, Number, Math, Object, String};
  vm.createContext(scope);
  vm.runInContext(slice('function freeAgencyRoomState(', 'function ensureFreeAgencySelection('), scope);
  vm.runInContext(slice('function freeAgencyMinimum(', 'function phaseFreeAgencyMarketCard('), scope);
  vm.runInContext(slice('function roundOfferTenth(', 'function freeAgencyOfferBuilderPanel('), scope);
  scope.CONTRACT_PATH_LABELS = {rising: 'Rising', flat: 'Flat', declining: 'Declining'};
  scope.CONTRACT_OPTION_LABELS = {none: 'None', player: 'Player option', team: 'Team option'};
  return scope;
}

// FA-REAL: legality is the engine's quote (free_agent_offer_quote -> cap_ledger.quote); the builder only shows it.
function quoteFor(scope, player, draft, quote) {
  scope.state.freeAgentQuotes ||= {};
  scope.state.freeAgentQuotes[scope.freeAgencyQuoteKey(player, draft)] = quote;
}

test('the cap verdict is the engine quote: pending until it arrives, blocked with its reason, paid with its route', () => {
  const scope = builderScope();
  const {freeAgencyCapVerdict} = scope;
  assert.deepEqual({...freeAgencyCapVerdict(null, {})}, {ok: true, pending: true, limit: '', message: ''});
  const blocked = freeAgencyCapVerdict({ok: false, message: 'CHA has no legal way to pay this.'}, {});
  assert.equal(blocked.ok, false);
  assert.match(blocked.message, /no legal way/);
  const paid = freeAgencyCapVerdict({ok: true, route: 'non_taxpayer_mle', label: 'the full mid-level exception'}, {});
  assert.equal(paid.ok, true);
  assert.equal(paid.limit, 'non_taxpayer_mle');
  assert.match(paid.message, /full mid-level/);
  // Unreviewed waived salary blocks every signing.
  assert.equal(freeAgencyCapVerdict({ok: true}, {blocked_reason: 'Waived salary requires review.'}).ok, false);
  // One cached quote per offer: salary, years, route, salary path, option and guarantee all change the key.
  const key = scope.freeAgencyQuoteKey(miller, {aav: 20, years: 3});
  assert.notEqual(key, scope.freeAgencyQuoteKey(miller, {aav: 20.1, years: 3}));
  assert.notEqual(key, scope.freeAgencyQuoteKey(miller, {aav: 20, years: 3, route: 'cap_room'}));
  assert.notEqual(key, scope.freeAgencyQuoteKey(miller, {aav: 20, years: 3, path: 'flat'}));
  assert.notEqual(key, scope.freeAgencyQuoteKey(miller, {aav: 20, years: 3, option: 'player'}));
  assert.notEqual(key, scope.freeAgencyQuoteKey(miller, {aav: 20, years: 3, guaranteed: false}));
});

test('the verdict uses the salary he needs from you today (the rival bids\' rule), the length, the guarantee and his retirement', () => {
  const {freeAgencyOfferPreview} = builderScope();
  const r = room();
  const at = (aav, extra = {}) => freeAgencyOfferPreview(miller, r, {aav, years: 4, guaranteed: true, ...extra});
  assert.equal(at(30.9).accepts, false, 'one step under his floor');
  assert.match(at(30.9).verdict.detail, /\$31\.0M/);
  assert.equal(at(31.0).accepts, true, 'his floor: above the $28.8M ask, enough to beat BKN');
  assert.equal(at(31.0).verdict.tone, 'yes');
  assert.equal(at(31.0, {guaranteed: false}).accepts, false, 'a non-guaranteed deal needs more');
  assert.equal(at(37.6, {guaranteed: false}).accepts, true);
  assert.equal(at(32.5, {years: 2}).accepts, false, 'a shorter deal needs more');
  assert.equal(at(33.0, {years: 2}).accepts, true);
  const oneYear = at(60, {years: 1});
  assert.equal(oneYear.accepts, false, 'no salary for one year beats the rival bid today');
  assert.match(oneYear.verdict.detail, /No salary wins him from you today: BKN/);
  const veteran = {...miller, safe_years: 2};
  const long = freeAgencyOfferPreview(veteran, r, {aav: 40, years: 3, guaranteed: true});
  assert.equal(long.accepts, false);
  assert.match(long.verdict.detail, /retire after 2 seasons/);
  assert.equal(freeAgencyOfferPreview(veteran, r, {aav: 33, years: 2, guaranteed: true}).accepts, true);
  const scope = builderScope();
  quoteFor(scope, miller, {aav: 70, years: 4}, {ok: false, message: 'Above his maximum salary ($42.7M).', routes: []});
  const blocked = scope.freeAgencyOfferPreview(miller, r, {aav: 70, years: 4, guaranteed: true});
  assert.equal(blocked.cap.ok, false);
  assert.equal(blocked.canSubmit, false);
  assert.equal(blocked.verdict.tone, 'blocked');
  assert.equal(freeAgencyOfferPreview({...miller, signing_blocked_reason: 'stretched'}, r, {aav: 20, years: 1}).canSubmit, false);
});

// CONTRACT-TERMS: a salary path or option other than the usual waits for the engine's answer (its value to him and the
// first-year salary he needs on these terms), then uses it; an option on a one-season deal is blocked.
test('salary path and option: the verdict uses the engine price for these terms', () => {
  const scope = builderScope();
  const r = room();
  const draft = {aav: 31.0, years: 4, guaranteed: true, path: 'flat', option: 'team'};
  const pending = scope.freeAgencyOfferPreview(miller, r, draft);
  assert.equal(pending.verdict.headline, 'Checking his answer…');
  assert.equal(pending.accepts, false);
  quoteFor(scope, miller, draft, {ok: true, label: 'cap room', schedule: [], player_terms: {factor: 0.82, floor_millions: 37.8,
    accepts: false, option_problem: null, path: 'flat', option: 'team', words: 'The same salary every season, team option on the last season',
    effect: 'Flat pay gives him less money than the usual raises; a team option means he may never be paid the last season: he counts it as 18% less than the same first-year salary on the usual terms.'}});
  const answered = scope.freeAgencyOfferPreview(miller, r, draft);
  assert.equal(answered.accepts, false);
  assert.match(answered.verdict.detail, /from \$37\.8M in the first year on these terms/);
  assert.match(answered.verdict.detail, /18% less/);
  assert.match(scope.freeAgencyShapeNote(answered, draft), /counts these terms as 18% less/);
  const usual = scope.freeAgencyOfferPreview(miller, r, {aav: 31.0, years: 4, guaranteed: true, path: 'rising', option: 'none'});
  assert.equal(usual.accepts, true, 'the usual terms use the room floor right away');
  const oneSeason = scope.freeAgencyOfferPreview(miller, r, {aav: 40, years: 1, guaranteed: true, path: 'rising', option: 'player'});
  assert.equal(oneSeason.verdict.tone, 'blocked');
  assert.equal(oneSeason.canSubmit, false);
});

// FA-REAL slice 3: another team's restricted free agent signs only an offer sheet: 2-4 years, guaranteed, his price now,
// and the engine's sheet quote (offer_sheets via free_agent_offer_quote).
test('offer sheet mode: legal lengths, his price now, the reserved payment and the button', () => {
  const scope = builderScope();
  const r = room();
  const rfa = {...miller, id: 'p_rfa', name: 'Young Wing', restricted: {team_abbrev: 'BOS', yours: false},
    accept_floor_by_years: {guaranteed: {1: null, 2: 12.4, 3: 12.4, 4: 12.4, 5: null}, non_guaranteed: {1: null, 2: null, 3: null, 4: null, 5: null}},
    offer_sheet: {min_years: 2, max_years: 4, want_millions: 12.4, routes: ['cap_room', 'non_taxpayer_mle'], words: 'Restricted free agent of BOS.'}};
  const one = scope.freeAgencyOfferPreview(rfa, r, {aav: 13, years: 1, guaranteed: false});
  assert.equal(one.years, 2, 'an offer sheet runs at least two years');
  assert.equal(one.guaranteed, true, 'offer sheets are fully guaranteed');
  assert.equal(scope.freeAgencyOfferPreview(rfa, r, {aav: 13, years: 5}).years, 4, 'and at most four');
  quoteFor(scope, rfa, {aav: 12.0, years: 3}, {ok: true, label: 'the full mid-level exception', routes: [],
    offer_sheet: {player_signs: false, player_reason: 'He wants at least $12.4M a year now.', legal: true}});
  const low = scope.freeAgencyOfferPreview(rfa, r, {aav: 12.0, years: 3});
  assert.equal(low.verdict.headline, "He won't sign this sheet");
  assert.match(low.verdict.detail, /\$12\.4M/);
  quoteFor(scope, rfa, {aav: 12.5, years: 3}, {ok: true, label: 'the full mid-level exception', routes: [],
    offer_sheet: {player_signs: true, legal: true}});
  const good = scope.freeAgencyOfferPreview(rfa, r, {aav: 12.5, years: 3});
  assert.equal(good.verdict.headline, 'He signs the offer sheet');
  assert.match(good.verdict.detail, /BOS then has until the end of the next day to match/);
  assert.equal(good.canSubmit, true);
  scope.escapeAttr = escapeHtml;
  vm.runInContext(slice('function freeAgencyOfferFootMarkup(', '// ---- Signing wire'), scope);
  assert.match(scope.freeAgencyOfferFootMarkup(rfa, good, {legal: true, open: true}), /Sign Offer Sheet/);
  quoteFor(scope, rfa, {aav: 30, years: 3}, {ok: false, message: 'BOS? no: Above the full mid-level.', routes: [],
    offer_sheet: {player_signs: true, legal: false}});
  assert.equal(scope.freeAgencyOfferPreview(rfa, r, {aav: 30, years: 3}).verdict.headline, 'Not a legal offer sheet');
});

test('cap preview uses the ledger by season and the engine schedule (raises off year one) for the contract years', () => {
  const scope = builderScope();
  const r = room({cap_ledger: {season: '2027-28', by_year: [
    {season: '2027-28', cap_payroll_millions: 180.0, tax_payroll_millions: 140.1, holds_millions: 39.9, cap_room_millions: -9.3,
     room_under_tax_millions: 67.3, room_under_first_apron_millions: 75.9},
    {season: '2028-29', cap_payroll_millions: 150, tax_payroll_millions: 150, holds_millions: 0, cap_room_millions: 20.7,
     room_under_tax_millions: 64.7, room_under_first_apron_millions: 73.6},
    {season: '2029-30', cap_payroll_millions: 100, tax_payroll_millions: 100, holds_millions: 0, cap_room_millions: 76.7,
     room_under_tax_millions: 122.2, room_under_first_apron_millions: 131.2},
  ]}});
  quoteFor(scope, miller, {aav: 20, years: 2}, {ok: true, route: 'non_taxpayer_mle', label: 'the full mid-level exception',
    cap_room_after_millions: -29.3, schedule: [
      {season: '2027-28', salary_millions: 20, cap_charge_millions: 20},
      {season: '2028-29', salary_millions: 21, cap_charge_millions: 21}]});
  const preview = scope.freeAgencyOfferPreview(miller, r, {aav: 20, years: 2, guaranteed: true});
  assert.deepEqual(Array.from(preview.seasons, (row) => row.season), ['2027-28', '2028-29', '2029-30']);
  assert.deepEqual(Array.from(preview.seasons, (row) => row.salary), [20, 21, 0], 'the saved schedule: 5% of year one added');
  assert.equal(Math.round(preview.seasons[0].after * 10) / 10, 160.1, 'tax payroll after');
  assert.equal(preview.seasons[0].capRoom, -29.3, 'this season: the engine room after (holds counted)');
  assert.equal(Math.round(preview.seasons[0].taxRoom * 10) / 10, 47.3);
  assert.equal(Math.round(preview.seasons[1].apronRoom * 10) / 10, 52.6);
  assert.equal(preview.total, 41);
  assert.ok(Math.abs(preview.ratio - 20 / 33.0) < 1e-9, 'meter = salary / his price for this length');
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
  // FA-REAL slice 2 (changed): a fourth window, the offseason checklist (stop 1 and signing day).
  assert.deepEqual(Array.from(section.matchAll(/\["(\w+)", "([^"]+)", "([^"]+)"\]/g), (m) => m[1]), ['market', 'selected', 'wire', 'checklist']);
  const commands = slice('function freeAgencyPhaseCommands(', 'function freeAgencyMinimum(');
  // FA-REAL slice 2: stop 1 goes to draft night, then opens free agency (no more exclusive days).
  for (const id of ['reSignToDraft', 'reSignOpenMarket', 'faAdvanceStage', 'faAdvanceDay', 'faAdvanceEnd']) assert.match(commands, new RegExp(id));
  for (const command of ["'resign-day'", "'resign-open'", "'fa-day'", "'fa-end'", "'fa-next'"]) assert.ok(app.includes(`${command}:`), command);
  // No invented interest number survives from the old negotiation modal.
  assert.doesNotMatch(app, /offer \/ Math\.max\(1, ask\) \* 70/);
  assert.doesNotMatch(app, /freeAgentNegotiationBody/);
});
