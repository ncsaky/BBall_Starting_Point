// Contract extension builder (no invented interest numbers; the price, limits and cap table come from the payload),
// plus the free-agency polish: wire dates never after today, "Fits our room" counts roster spots, and the Assistant GM
// phone tucks away from open windows.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const slice = (from, to) => {
  const start = app.indexOf(from);
  const end = app.indexOf(to, start + 1);
  assert.ok(start >= 0 && end > start, `missing app.js section ${from}`);
  return app.slice(start, end);
};

function scope(extra = {}) {
  const context = {
    money: (v) => (v === undefined || v === null || v === '' ? '' : `$${Number(v).toFixed(1)}M`),
    contractLabel: (salary, years) => (Number(salary) > 0 ? `$${Number(salary).toFixed(1)}M${Number(years) > 0 ? ` × ${Number(years)}` : ''}` : '—'),
    salaryMarksMarkup: (marks) => marks.map((m) => `<button ${m.attr}="${m.attrValue ?? m.value}">${m.label}</button>`).join(''),
    positionSalaryMarks: () => {},
    signedMoney: (v) => `$${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(1)}M`,
    escapeHtml: (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'),
    escapeAttr: (v) => String(v ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;'),
    clampNumber: (v, a, b) => Math.max(a, Math.min(b, v)),
    roundOfferTenth: (v) => Math.round(Number(v || 0) * 10) / 10,
    shortSeasonLabel: (s) => { const m = String(s || '').match(/(\d{4})-(\d{2,4})/); return m ? `${m[1].slice(-2)}-${m[2].slice(-2)}` : s; },
    extensionAnalysisPanel: () => '<section class="extension-analysis"></section>',
    state: { data: { freeagency: {} } },
    ...extra,
  };
  vm.createContext(context);
  return context;
}

function candidate(overrides = {}) {
  const rule = (line) => ({ line_millions: line, bracket_millions: line * 0.0333, rates: [1.5, 1.75, 2.5, 3.25], step_after: 0.5, repeater: false });
  return {
    player_id: 'p1', name: 'Michael Porter Jr.', eligible: true, eligibility_reason: null, safe_years: 4, preferred_years: 4,
    start_season: '2027-28', projected_aav_millions: 21.55, market_ask_millions: 21.55, ask_share: 0.8931,
    security_premium_pct: { guaranteed: 0, non_guaranteed: 20 },
    accept_line_millions: { guaranteed: 19.2458, non_guaranteed: 23.095 }, accept_offer_millions: { guaranteed: 19.3, non_guaranteed: 23.1 },
    max_aav_by_years: { 1: 110.07, 2: 110.07, 3: 110.07, 4: 110.07 },
    current_contract_seasons: [{ season: '2026-27', salary: 40810000 }],
    cap_table: [
      { season: '2026-27', salary_total_millions: 160.11, tax_space_millions: 40.29, hard_cap_space_millions: 61.59, tax_rule: rule(207.4), payout_share_if_under_millions: 3.02, player_salary_millions: 40.81 },
      { season: '2027-28', salary_total_millions: 200.0, tax_space_millions: 7.4, hard_cap_space_millions: 29.4, tax_rule: rule(214.7), payout_share_if_under_millions: 0.99, player_salary_millions: 0 },
      { season: '2028-29', salary_total_millions: 46.41, tax_space_millions: 168.29, hard_cap_space_millions: 191.09, tax_rule: rule(222.2), payout_share_if_under_millions: 0.18, player_salary_millions: 0 },
    ],
    ...overrides,
  };
}

const room = { offer_rules: { minimum_aav_millions: 1.8, max_years: 5, accept_margin_millions: 0.001 } };

test('extension preview follows the payload price, term limit and hard-cap limit', () => {
  const s = scope();
  vm.runInContext(slice('function extensionCandidate(', 'function extensionVerdictMarkup('), s);
  const c = candidate();
  assert.equal(s.extensionOfferPreview(c, room, { years: 4, aav: 19.2, guaranteed: true }).verdict.tone, 'no');
  assert.match(s.extensionOfferPreview(c, room, { years: 4, aav: 19.2, guaranteed: true }).verdict.detail, /from \$19\.3M in the first season/);
  assert.equal(s.extensionOfferPreview(c, room, { years: 4, aav: 19.3, guaranteed: true }).verdict.tone, 'yes');
  assert.equal(s.extensionOfferPreview(c, room, { years: 4, aav: 19.3, guaranteed: false }).verdict.tone, 'no', 'non-guaranteed costs more');
  const tooLong = s.extensionOfferPreview(c, room, { years: 5, aav: 25, guaranteed: true });
  assert.equal(tooLong.verdict.tone, 'no'); assert.equal(tooLong.canSubmit, false); assert.match(tooLong.verdict.detail, /retire after 4/);
  const capped = s.extensionOfferPreview(c, room, { years: 2, aav: 110.1, guaranteed: true });
  assert.equal(capped.verdict.tone, 'blocked'); assert.equal(capped.canSubmit, false);
  assert.equal(s.extensionOfferCeiling(110.07), 110.0);
  const closed = s.extensionOfferPreview(candidate({ eligible: false, eligibility_reason: 'Extensions are closed until the next window (preseason to January 15).' }), room, { years: 2, aav: 25 });
  assert.equal(closed.verdict.tone, 'blocked'); assert.match(closed.verdict.detail, /closed/);
});

test('extension cap table applies the offer from its start season and charges the game tax rule', () => {
  const s = scope();
  vm.runInContext(slice('function extensionCandidate(', 'function extensionVerdictMarkup('), s);
  const preview = s.extensionOfferPreview(candidate(), room, { years: 2, aav: 25, guaranteed: true });
  assert.deepEqual(preview.seasons.map((row) => row.salary), [0, 25, 25]);
  const next = preview.seasons[1];
  assert.equal(next.after, 225); assert.ok(Math.abs(next.taxRoom - -17.6) < 1e-9);
  // 225 against a 214.7 line: one full bracket (7.15M) at 1.50, the rest (3.15M) at 1.75.
  const bracket = 214.7 * 0.0333;
  assert.ok(Math.abs(next.taxBill - (bracket * 1.5 + (10.3 - bracket) * 1.75)) < 1e-9);
  assert.equal(next.payoutShare, 0); assert.equal(next.lostShare, 0.99, 'going over the line gives up the payout share');
  assert.equal(preview.seasons[2].payoutShare, 0.18);
  assert.match(preview.verdict.detail, /over the tax in 27-28/);
  assert.equal(s.extensionLuxuryTax(200, { line_millions: 207.4, bracket_millions: 6.9, rates: [1.5] }), 0);
});

test('extension page shows the engine numbers and no invented interest bars', () => {
  const s = scope();
  vm.runInContext(slice('const CONTRACT_PATH_LABELS', 'function freeAgencyQuoteKey('), s);
  vm.runInContext(slice('function extensionCandidate(', 'function extensionDeparturePanel('), s);
  const html = s.extensionNegotiationPage({ ...room, candidates: [candidate()] }, 'p1');
  assert.match(html, /Signs with you from/);
  assert.match(html, /\$19\.3M/);
  assert.match(html, /Market ask/);
  assert.match(html, /Longest deal/);
  assert.match(html, /Will He Sign\?/);
  assert.match(html, /Cap Position With This Extension/);
  assert.match(html, /Tax room/); assert.match(html, /Hard-cap room/); assert.match(html, /Tax \/ payout/);
  assert.match(html, /role="radiogroup"/);
  assert.match(html, /data-extension-offer-form/);
  assert.doesNotMatch(html, /Interest|Team direction|Player timeline/);
  assert.doesNotMatch(app, /\["Team direction",64\]/);
});

test('CONTRACT-TERMS: extension salary path and option change the schedule, the limit and his price', () => {
  const s = scope();
  vm.runInContext(slice('const CONTRACT_PATH_LABELS', 'function freeAgencyQuoteKey('), s);
  vm.runInContext(slice('function extensionCandidate(', 'function extensionDeparturePanel('), s);
  const factors = { rising: { none: { 2: 1.04 }, team: { 2: 0.85 } }, flat: { none: { 2: 1 }, player: { 2: 1.07 } } };
  const c = candidate({ terms_factors: factors, max_raise_pct: 8, first_year_limit_millions: 30,
    max_aav_by_path: { rising: { 1: 28, 2: 27 }, flat: { 1: 29, 2: 29 }, declining: { 1: 29, 2: 29 } } });
  const rising = s.extensionOfferPreview(c, room, { years: 2, aav: 20, guaranteed: true, path: 'rising', option: 'none' });
  assert.deepEqual(rising.seasons.map((row) => row.salary), [0, 20, 21.6]);
  assert.equal(rising.maximum, 27);
  assert.ok(rising.price < 19.3, 'a rising deal is worth more to him: a lower first-season price');
  assert.match(rising.verdict.detail, /counts it as 4% more/);
  const team = s.extensionOfferPreview(c, room, { years: 2, aav: 20, guaranteed: true, path: 'rising', option: 'team' });
  assert.equal(team.verdict.tone, 'no'); assert.ok(team.price > 22);
  const oneYearOption = s.extensionOfferPreview(c, room, { years: 1, aav: 25, guaranteed: true, path: 'flat', option: 'player' });
  assert.equal(oneYearOption.verdict.tone, 'blocked'); assert.equal(oneYearOption.canSubmit, false);
  const html = s.extensionNegotiationPage({ ...room, candidates: [c] }, 'p1');
  assert.match(html, /Salary path/); assert.match(html, /Option on the last season/);
  assert.match(html, /data-extension-path-choice="declining"/); assert.match(html, /data-extension-option-choice="team"/);
  assert.doesNotMatch(html, /Extensions in this game have no player or team options/);
});

test('signing wire never dates an applied move after today and names other years', () => {
  const s = scope();
  vm.runInContext(slice('function freeAgencyWireDate(', 'function shortSeasonLabel('), s);
  const future = s.freeAgencyWireDate('2027-07-03', '2027-06-27');
  assert.equal(future.date, '2027-06-27'); assert.equal(future.label, '06/27'); assert.match(future.title, /recorded for 2027-07-03/);
  assert.equal(s.freeAgencyWireDate('2027-06-26', '2027-06-27').label, '06/26');
  assert.equal(s.freeAgencyWireDate('2026-07-03', '2027-07-01').label, '07/03/26');
  assert.equal(s.freeAgencyWireDate('2027-07-03', '').label, '07/03');
});

test('"Fits our room" needs an open roster spot as well as the price', () => {
  const s = scope();
  vm.runInContext(slice('function freeAgencyMinimum(', 'function phaseFreeAgencyMarketCard('), s);
  const player = { accept_floor_offer_millions: { guaranteed: 10 } };
  const base = { offer_rules: { minimum_aav_millions: 1.9, season_roster_maximum: 15 }, cap: { max_offer_aav_millions: 20 } };
  assert.equal(s.freeAgencyPlayerFitsRoom(player, { ...base, roster_count: 14 }), true);
  assert.equal(s.freeAgencyPlayerFitsRoom(player, { ...base, roster_count: 15 }), false);
  assert.equal(s.freeAgencyPlayerFitsRoom(player, { ...base, roster_count: 17 }), false);
  assert.equal(s.freeAgencyPlayerFitsRoom({ accept_floor_offer_millions: { guaranteed: 25 } }, { ...base, roster_count: 12 }), false);
  assert.equal(s.freeAgencyOpenRosterSpots({ ...base, roster_count: 12 }), 3);
});

test('Assistant GM phone tucks away from open windows and expands on hover or focus', () => {
  const phone = fs.readFileSync(path.join(gui, 'assistant-phone.js'), 'utf8');
  const css = fs.readFileSync(path.join(gui, 'assistant-phone.css'), 'utf8');
  assert.match(phone, /function coversOpenWindow\(phone\)/);
  assert.match(phone, /\.card-board-window/);
  assert.match(phone, /classList\.toggle\("is-tucked"/);
  assert.match(css, /\.assistant-gm-phone\.is-tucked:not\(:hover\):not\(:focus-within\)\s*\{[^}]*scale:/);
});
