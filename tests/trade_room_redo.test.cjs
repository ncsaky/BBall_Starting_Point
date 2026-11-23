// Trade room redo (2026-11-23): the deal tiles, the salary picture and the answer dial. The salary picture must say
// what the engine's salary check says (transactions.salary_matching_issue), so its numbers are pinned to the engine's.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const engine = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/transactions.py'), 'utf8');

function extract(name) {
  const start = app.search(new RegExp(`^function ${name}\\(`, 'm'));
  assert.ok(start >= 0, `${name} not found`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next);
}

function context(extra = {}) {
  const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const ctx = {
    state: {home: {save: {user_team: {id: 'team_okc'}}}, teams: [], tradeAdditionalTeams: []},
    escapeHtml: escape, escapeAttr: escape, textValue: value => String(value ?? ''),
    money: value => `$${Number(value).toFixed(1)}M`, userTeam: () => 'OKC', teamLabel: value => String(value).replace('team_', '').toUpperCase(),
    tradeKnownNumber: value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value) : null,
    tradeLegalityBadge: () => '', tradeLegalityIssues: () => '', frontOfficeReadMarkup: () => '<div class="front-office-read"></div>',
    playerHeadshotMarkup: asset => asset.headshot_url ? `<img src="${asset.headshot_url}">` : '',
    playerNameWithInjuryMarkup: (asset, name) => escape(name), shortSeasonLabel: value => value,
    playerRoleChip: role => `<span class="role-chip">${role}</span>`, performanceBarColor: () => '#3978d4', TRADE_VALUE_SCALE: 120,
    ...extra,
  };
  vm.createContext(ctx);
  vm.runInContext(['tradeSalaryFlow', 'tradeReadout', 'tradeCounterOffer', 'tradeAssetContract', 'tradePickText', 'tradeRatingColor', 'tradeValueBar', 'tradeDealTile'].map(extract).join('\n'), ctx);
  return ctx;
}

const cap = {season: '2026-27', salary_total_millions: 216.9, tax_line_millions: 200.43, hard_cap_millions: 221.69};
const player = (id, salary) => ({kind: 'player', id, salary_by_year: {'2026-27': salary}});

test('the salary picture uses the engine numbers: $7.5M floor, 125% of outgoing plus $5M, tax line, hard cap', () => {
  assert.match(engine, /"salary_floor": 7500000/);
  assert.match(engine, /"incoming_multiplier": 1\.25/);
  assert.match(engine, /plus = min\(float\(salary_config\.get\("incoming_plus", 7_500_000\)\), 5_000_000\)/);
  assert.match(engine, /incoming_salary > floor and incoming_salary > credit \* multiplier \+ plus and after > tax_line/);
  assert.match(engine, /after_total > hard_cap and after_total > current_total \+ 250_000/);
  assert.match(engine, /if after < minimum and after < current:/);
  assert.match(engine, /"minimum_roster": 12/);
  const ctx = context();
  const flow = (sends, receives, overrides = {}) => ctx.tradeSalaryFlow('OKC', {cap: {...cap, ...overrides}, players: Array(15).fill({})}, sends, receives);
  // 23.1 out can take back up to 23.1 * 1.25 + 5 = 33.875 above the tax line.
  assert.equal(flow([player('a', 23.1)], [player('b', 33.8)], {salary_total_millions: 200}).tone, 'good');
  const over = flow([player('a', 23.1)], [player('b', 34.5)]);
  assert.equal(over.tone, 'bad'); assert.match(over.status, /Takes back \$0\.6M too much/);
  // Under the tax after the deal: no matching needed, as in the engine.
  assert.match(flow([player('a', 5)], [player('b', 20)], {salary_total_millions: 150}).status, /Under the tax/);
  // Small incoming salary (at or under $7.5M) always fits the matching rule.
  assert.equal(flow([], [player('b', 7.5)], {salary_total_millions: 205}).tone, 'good');
  // Finishing above the hard cap from below is blocked; matching is checked first, like the engine.
  assert.match(flow([player('a', 10)], [player('b', 15)]).status, /over the hard cap/);
  // Roster minimum.
  assert.match(ctx.tradeSalaryFlow('OKC', {cap, players: Array(12).fill({})}, [player('a', 2)], []).status, /Roster drops to 11/);
  // Unknown salary is never shown as zero.
  assert.equal(flow([{kind: 'player', id: 'x', salary_by_year: {}}], []).status, 'Salary unknown');
});

test('the answer is one word, a dial and one short line; the numbers wait behind Details', () => {
  const ctx = context();
  const waiting = ctx.tradeReadout(null);
  assert.match(waiting, /Not asked yet/); assert.match(waiting, /class="tr-dial is-waiting"/); assert.doesNotMatch(waiting, /tr-dial-needle/);
  const declined = ctx.tradeReadout({legality: {status: 'legal'}, partner_read: {lines: []},
    evaluations: [{perspective_team_id: 'team_atl', accepted: false, net_value: -1.5, acceptance_threshold: 1.5}]});
  assert.match(declined, /Declines/); assert.match(declined, /3\.0 short of their price/);
  assert.match(declined, /--tr-needle:-24\.3deg/); // 50 - 3.0 * 4.5 = 36.5 of 100 on the half-dial
  assert.match(declined, /<details class="tr-details"><summary>Details<\/summary>/);
  assert.doesNotMatch(declined, /id="applyBuiltTrade"/);
  const accepted = ctx.tradeReadout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_atl', accepted: true, net_value: 4, acceptance_threshold: 1}]});
  assert.match(accepted, /Accepts/); assert.match(accepted, /3\.0 above their price/); assert.match(accepted, /id="applyBuiltTrade"[^>]*>Accept Trade/);
  const blocked = ctx.tradeReadout({legality: {status: 'illegal', issues: ['ATL incoming salary exceeds practical matching tolerance.']}, evaluations: []});
  assert.match(blocked, /Not possible/); assert.match(blocked, /ATL incoming salary exceeds/);
});

test('a deal tile shows face, name, position and age, value as a bar, coloured OVR, $X × N, roles on hover', () => {
  const ctx = context();
  const html = ctx.tradeDealTile({kind: 'player', id: 'p1', name: 'Isaiah Hartenstein', headshot_url: '/h.png', position: 'C', age: 28,
    primary_off_role: 'Rollman', primary_def_role: 'Rim Protector', overall: 83.1, trade_value: 67.2,
    salary_by_year: {'2026-27': 23.1, '2027-28': 23.1, '2028-29': 23.1}}, {removeSide: 'from', fresh: true});
  // Taste deck round 2: value first, as a bar with its number; roles move to the hover text; OVR as a whole number.
  for (const piece of ['/h.png', 'Isaiah Hartenstein', 'C · 28', 'title="Rollman / Rim Protector"', '$23.1M × 3', '<strong>67.2</strong>', 'data-remove-side="from"', 'is-new'])
    assert.ok(html.includes(piece), piece);
  assert.match(html, /<b style="color:#[0-9a-f]{6}">83<\/b>/);
  assert.match(html, /class="tr-tile-value"[^>]*><i><b style="width:56\.0%/);
  const pick = ctx.tradeDealTile({kind: 'pick', id: 'k', season: '2027', round: 1, original_team_abbrev: 'NOP', protection_summary: 'top-4 protected',
    label: '2027 R1 NOP (owned by ATL); top-4 protected; NOP keeps this pick if it lands in the protected range; ATL instead receives 2028 R1 NOP', trade_value: 92});
  assert.match(pick, />2027 R1 NOP</); assert.match(pick, /Draft pick · top-4 protected/); assert.match(pick, /title="2027 R1 NOP \(owned by ATL\)/);
});

test('the builder keeps every tool: partner arrows, add team, final offer, ask, counters, four detail pages', () => {
  for (const marker of ['id="tradePartner"', 'data-trade-team-step="-1"', 'id="tradeAddTeam"', 'data-trade-add-team', 'id="tradeFinalOffer"',
    'id="evaluateTrade"', 'id="acceptCounterTrade"', 'id="editCounterTrade"', 'id="declineCounterTrade"', 'data-trade-remove-team',
    'data-trade-destination', '"Assets", "Value", "Payroll", "Team identity"', 'data-trade-sort=', 'data-asset-filter=', 'tradePickTermsMarkup()'])
    assert.ok(app.includes(marker), marker);
  assert.match(app, /state\.tradeVerdictFresh = true/);
  const css = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/trade-room.css'), 'utf8');
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /box-shadow: inset 0 -3px var\(--tr-ink\) !important/); // one thick dark header line
});
