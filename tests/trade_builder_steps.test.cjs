// The Trade Builder in three steps (UI polish pass, 2026-11-26; the user: "the checkbox list of assets and the page
// showing the assets that have been selected should be separate, and then the what-it-does section is still
// separate from that"): pick assets, the deal, what it does (in sections).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const between = (source, from, to) => source.slice(source.indexOf(from), source.indexOf(to, source.indexOf(from)));
const builder = between(app, 'function renderTradeBuilder(root) {', 'function tradePartnerPicker(');

test('three numbered steps; the second and third open only once something is in the deal', () => {
  assert.match(builder, /<nav class="tr-steps" aria-label="Trade steps">\$\{step\("pick", 1, "Pick assets"\)\}\$\{step\("deal", 2, "The deal"\)\}\$\{step\("effect", 3, "What it does"\)\}/);
  assert.match(builder, /\$\{target !== "pick" && empty \? "disabled" : ""\}/);
  assert.match(builder, /const view = empty \? "pick" : state\.tradeView;/);
  assert.match(builder, /data-trade-view="deal" \$\{empty \? "disabled" : ""\}>The deal ›/, 'the way on from step 1');
  assert.match(builder, /data-trade-view="effect">What it does ›/, 'the way on from step 2');
});

test('step 1 is only the lists: both teams side by side, nothing else to scroll past', () => {
  const pick = between(builder, 'body.innerHTML = view === "pick"', ': view === "deal" ?');
  assert.match(builder, /participants\.map\(row => assetColumn\(`\$\{row\.team\} gives`, row\.payload, row\.side, row\.team/, 'one list a team');
  assert.match(builder, /row\.side === "to" \? \{tabs: tradePartnerPicker\(row\.team, row\.payload\)\}/, 'the partner is chosen at the head of its list');
  assert.match(pick, /class="trade-builder-layout tr-builder tr-page-pick/);
  assert.doesNotMatch(pick, /tradeDealSide|tradeReadout|evaluateTrade/);
  // The lists scroll (the user's earlier choice): the pager stays hidden, so rows must never be hidden by paging.
  assert.doesNotMatch(builder, /fitTradeAssetPages\(/);
  assert.match(read('glass-clear.css'), /#modalRoot \.tr-pager \{ display: none !important; \}/);
});

test('step 2 is the deal: each side in a box that takes the height, its salary check, the answer and Ask', () => {
  const deal = between(builder, '<div class="trade-builder-layout tr-builder tr-page-deal', '<div class="trade-builder-layout tr-builder tr-page-effect');
  assert.match(deal, /participants\.map\(row => tradeDealSide\(row, participants, fresh\)\)/);
  assert.match(deal, /id="tradeRead">\$\{tradeReadout\(candidate\)\}/);
  assert.match(deal, /id="evaluateTrade"/);
  assert.doesNotMatch(deal, /assetColumn\(|tr-lower-tabs|data-trade-page="/);
  const css = read('popups.css');
  assert.match(css, /\.tr-builder\.tr-page-deal \.tr-tiles \{ max-height: none !important;/, 'room for a dozen assets a side');
  assert.match(css, /\.tr-builder\.tr-page-deal \.tr-side \{ height: 100% !important;/);
});

test('with three or more teams step 1 shows one list at a time, chosen from the strip', () => {
  assert.match(builder, /const lists = multi\s*\? `<div class="tr-pick-bar"><div class="tr-strip">\$\{strip\}<\/div><\/div>\$\{assetColumn\(`\$\{current\.team\} gives`/);
});

test('step 3 is in sections: the team, on the court, the money; one at a time', () => {
  const page = between(app, 'function tradeEffectPage(participants, candidate, multi) {', 'function tradePickParticipants() {');
  assert.match(page, /\[\["team", "The team"\], \["court", "On the court"\], \["money", "The money"\]\]/);
  assert.match(page, /class="tr-effect-teams" role="tablist"/, 'whose team to look at');
  assert.match(page, /tab === "team" \? tradeEffectTeam\(viewed\.team\)/);
  assert.match(page, /tradeIdentityPage\(\{openMinutes: true\}\)/);
  assert.match(page, /tradeEffectMoney\(participants, viewed, candidate, multi\)/);
  const money = between(app, 'function tradeEffectMoney(', 'function tradeEffectPage(');
  assert.match(money, /tradePayrollAnimation\(participants, viewed\.team\)/);
  assert.match(money, /tradeSalaryGauge\(tradeSalaryFlow\(row\.team, row\.payload, row\.selected, tradeReceivedAssets\(row\.team, participants\)\)/, 'each team\'s salary check');
  assert.match(money, /tradeSegmentedValueBoard\(candidate/);
});

test('the maps are one pair that fades between before and after', () => {
  const maps = between(app, 'function tradeIdentityPage(options = {}) {', 'async function loadTradeIdentity(');
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
  const ratings = between(app, 'const TRADE_EFFECT_RATINGS = [', 'function tradeEffectMoney(');
  for (const id of ['overall', 'offense', 'defense', 'depth', 'spacing', 'rebounding', 'rim_protection']) assert.match(ratings, new RegExp(`\\["${id}", `), id);
  assert.doesNotMatch(ratings, /efg|four_factors|morale|chemistry|net_rating|wins/i, 'no four factors, morale or wins: the game has no forecast of them');
  assert.match(ratings, /action\("trade_team_impact", \{\.\.\.savePayload\(\), \.\.\.request\}\)/);
  assert.match(ratings, /asset\.kind !== "player"\) continue;/, 'picks do not move a team\'s ratings');
  assert.match(ratings, /Working out the change…/);
  assert.match(ratings, /class="tr-effect-heroes"/, 'the four headline ratings lead the section');
  const server = fs.readFileSync(path.join(gui, '../app_actions.py'), 'utf8');
  const payload = between(server, 'def trade_team_impact_payload(', 'def league_efficiency_average(');
  assert.match(server, /if action == "trade_team_impact":\n\s+return trade_team_impact_payload\(canonical, save_path, payload\)/);
  assert.match(payload, /before = team_identity_report\(active, save\)/);
  assert.match(payload, /after = team_identity_report\(hypothetical, save\)/);
  assert.match(payload, /if not str\(key\)\.startswith\("_"\)/, 'the copy drops the caches that index the real rosters');
  assert.match(payload, /team_rotation_projection\(hypothetical, save, team_id, integer=False\)/, 'the coach\'s minutes for the new roster');
  assert.doesNotMatch(payload, /write_save|save_save|dump\(|json\.dump/, 'nothing is saved');
});
