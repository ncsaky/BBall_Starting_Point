// The Trade Builder in two pages (UI polish pass, 2026-11-26): "The deal" (pick what goes each way, see whether it
// is legal, ask) and "What it does" (what the trade would mean for a team, from numbers the game computes).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const between = (source, from, to) => source.slice(source.indexOf(from), source.indexOf(to, source.indexOf(from)));
const builder = between(app, 'function renderTradeBuilder(root) {', 'function tradePartnerPicker(');

test('the Builder has two numbered pages; the second opens only once something is in the deal', () => {
  assert.match(builder, /<nav class="tr-steps" aria-label="Trade pages">/);
  assert.match(builder, /data-trade-view="pick"[^>]*><i>1<\/i>The deal/);
  assert.match(builder, /data-trade-view="deal"[^>]*\$\{empty \? "disabled" : ""\}><i>2<\/i>What it does/);
  assert.match(builder, /const view = empty \? "pick" : state\.tradeView;/);
});

test('the deal page: both teams\' lists side by side, the deal with its salary check, the answer and Ask', () => {
  const deal = between(builder, 'body.innerHTML = view === "pick"', '<div class="trade-builder-layout tr-builder tr-page-effect');
  assert.match(builder, /participants\.map\(row => assetColumn\(`\$\{row\.team\} gives`, row\.payload, row\.side, row\.team/, 'one list a team');
  assert.match(builder, /row\.side === "to" \? \{tabs: tradePartnerPicker\(row\.team, row\.payload\)\}/, 'the partner is chosen at the head of its list');
  assert.match(deal, /<section class="tr-dock">/);
  assert.match(deal, /tradeDealSide\(row, participants, fresh, \{plain: !multi\}\)/, 'each side: what it gives and the salary check');
  assert.match(deal, /id="tradeRead">\$\{tradeReadout\(candidate\)\}/);
  assert.match(deal, /id="evaluateTrade"/);
  assert.doesNotMatch(deal, /tr-lower-tabs|data-trade-page="/, 'no tabs to hunt through');
  // The lists scroll (the user's earlier choice): the pager stays hidden, so rows must never be hidden by paging here.
  assert.doesNotMatch(builder, /fitTradeAssetPages\(/);
  assert.match(read('glass-clear.css'), /#modalRoot \.tr-pager \{ display: none !important; \}/);
});

test('with three or more teams the deal page shows one list at a time, chosen from the strip', () => {
  assert.match(builder, /const lists = multi\s*\? `<div class="tr-pick-bar"><div class="tr-strip">\$\{strip\}<\/div><\/div>\$\{assetColumn\(`\$\{current\.team\} gives`/);
});

test('the effect page: ratings before and after, one pair of maps that fades, the payroll and the values', () => {
  const page = between(app, 'function tradeEffectPage(participants, candidate, multi) {', 'function tradePickParticipants() {');
  assert.match(page, /class="tr-effect-teams" role="tablist"/, 'whose team to look at');
  assert.match(page, /tradeEffectRatings\(viewed\.team\)/);
  assert.match(page, /tradeIdentityPage\(\)/);
  assert.match(page, /tradePayrollAnimation\(participants, viewed\.team\)/);
  assert.match(page, /tradeSegmentedValueBoard\(candidate/);
  const maps = between(app, 'function tradeIdentityPage() {', 'async function loadTradeIdentity(');
  assert.match(maps, /class="trade-identity-fade" data-fade="\$\{fade\}"/);
  assert.match(maps, /<section class="is-before"><h4>Before the trade<\/h4>/);
  assert.match(maps, /<section class="is-after"><h4>After the trade<\/h4>/);
  assert.match(maps, /\[\["before", "Before"\], \["auto", "Fade"\], \["after", "After"\]\]/);
  const css = read('popups.css');
  assert.match(css, /\.trade-identity-comparison > section \{ grid-area: 1 \/ 1 !important;/, 'the two maps share one place');
  assert.match(css, /@keyframes tr-fade-before/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/, 'no movement when the system asks for none');
});

test('the ratings come from the game; nothing it cannot forecast is shown', () => {
  const ratings = between(app, 'const TRADE_EFFECT_RATINGS = [', 'function tradeEffectPage(');
  for (const id of ['overall', 'offense', 'defense', 'depth', 'spacing', 'rebounding', 'rim_protection']) assert.match(ratings, new RegExp(`\\["${id}", `), id);
  assert.doesNotMatch(ratings, /efg|four_factors|morale|chemistry|net_rating|wins/i, 'no four factors, morale or wins: the game has no forecast of them');
  assert.match(ratings, /action\("trade_team_impact", \{\.\.\.savePayload\(\), \.\.\.request\}\)/);
  assert.match(ratings, /asset\.kind !== "player"\) continue;/, 'picks do not move a team\'s ratings');
  assert.match(ratings, /Working out the change…/);
  const server = fs.readFileSync(path.join(gui, '../app_actions.py'), 'utf8');
  const payload = between(server, 'def trade_team_impact_payload(', 'def league_efficiency_average(');
  assert.match(server, /if action == "trade_team_impact":\n\s+return trade_team_impact_payload\(canonical, save_path, payload\)/);
  assert.match(payload, /before = team_identity_report\(active, save\)/);
  assert.match(payload, /after = team_identity_report\(hypothetical, save\)/);
  assert.match(payload, /if not str\(key\)\.startswith\("_"\)/, 'the copy drops the caches that index the real rosters');
  assert.match(payload, /team_rotation_projection\(hypothetical, save, team_id, integer=False\)/, 'the coach\'s minutes for the new roster');
  assert.doesNotMatch(payload, /write_save|save_save|dump\(|json\.dump/, 'nothing is saved');
});
